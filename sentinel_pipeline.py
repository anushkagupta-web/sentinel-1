#!/usr/bin/env python3
"""
Sentinel Pipeline v3 — Tiered extraction of last-modified dates from URLs.

Tiers:
  1: HTTP HEAD/GET (Last-Modified header)
  2: Portal metadata APIs (GitHub, Wikipedia, CKAN, Socrata, Eurostat, FEMA, OECD)
  3: Playwright (JS rendering) + BS4 parse + Mistral validation
  4: Groq compound browser automation (self-validated)
"""

import asyncio
import csv
import json
import logging
import os
import re
import ssl
import sys
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, unquote

import aiohttp
import certifi
from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

SSL_CTX = ssl.create_default_context(cafile=certifi.where())
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG = logging.getLogger("sentinel")

# Try importing playwright (optional but recommended)
try:
    from playwright.async_api import async_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False
    LOG.warning("Playwright not installed — Tier 3 JS rendering disabled. Run: pip install playwright && playwright install chromium")

# ── Models ──────────────────────────────────────────────────────────────────

@dataclass
class Result:
    dcid: str
    prov_id: str = ""
    url: str = ""
    method: str = ""
    last_modified: Optional[datetime] = None
    raw_timestamp: str = ""
    is_verified: Optional[bool] = None
    verification_confidence: float = 0.0
    verification_reasoning: str = ""
    suggested_timestamp: str = ""
    status: str = "pending"
    error: str = ""
    check_time: datetime = field(default_factory=datetime.now)


# ── Date Parsing ────────────────────────────────────────────────────────────

DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y",
    "%d %B %Y", "%d %b %Y", "%B %Y", "%b %Y",
    "%a, %d %b %Y %H:%M:%S GMT", "%a, %d %b %Y %H:%M:%S %Z",
]

CLEAN_PREFIXES = re.compile(
    r"^(?:Last\s+)?(?:Updated|Modified|Revised)\s*[:\-]?\s*", re.I
)


def parse_date(s: str) -> Optional[datetime]:
    if not s:
        return None
    s = CLEAN_PREFIXES.sub("", " ".join(s.split())).strip()
    try:
        return dateutil_parser.parse(s, fuzzy=True)
    except (ValueError, TypeError, OverflowError):
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    try:
        v = float(re.sub(r"[^\d.]", "", s))
        if v > 1e12:
            return datetime.fromtimestamp(v / 1000)
        elif v > 1e9:
            return datetime.fromtimestamp(v)
    except (ValueError, OSError, OverflowError):
        pass
    return None


def is_reasonable_date(dt: datetime) -> bool:
    return dt is not None and 2015 <= dt.year <= datetime.now().year + 1


# ── Generic Portal URL Detection ───────────────────────────────────────────

GENERIC_ROOTS = {
    "www.google.com", "www.wikidata.org", "datacommons.org", "www.datacommons.org",
    "rbi.org.in", "www.rbi.org.in", "s2geometry.io", "www.google.com",
}


def is_generic_portal(url: str) -> bool:
    parsed = urlparse(url)
    return (parsed.hostname in GENERIC_ROOTS and parsed.path.rstrip("/") in ("", "/"))


# ── HTTP Fetch Helper ───────────────────────────────────────────────────────

async def _fetch(session: aiohttp.ClientSession, method: str, url: str,
                 timeout: int = 20, **kwargs) -> Optional[aiohttp.ClientResponse]:
    t = aiohttp.ClientTimeout(total=timeout)
    for ssl_val in (None, False):
        try:
            resp = await getattr(session, method)(url, timeout=t, ssl=ssl_val, allow_redirects=True, **kwargs)
            return resp
        except aiohttp.ClientConnectorCertificateError:
            if ssl_val is False:
                return None
            LOG.debug(f"SSL failed for {url}, retrying without verification")
        except Exception as e:
            LOG.debug(f"{method.upper()} failed for {url}: {e}")
            return None
    return None


# ── Tier 1: HTTP HEAD + GET Range Fallback ──────────────────────────────────

async def tier1_http_head(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    for method, extra in [("head", {}), ("get", {"headers": {"Range": "bytes=0-0"}})]:
        resp = await _fetch(session, method, url, timeout=10, **extra)
        if resp:
            lm = resp.headers.get("Last-Modified")
            if lm:
                dt = parse_date(lm)
                if dt and is_reasonable_date(dt):
                    return lm
    return None


# ── Tier 2: Portal APIs (Registry Pattern) ─────────────────────────────────

async def _handle_eurostat(session, url, match):
    dataset_id = match.group(1)
    api_url = f"https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/dataflow/ESTAT/{dataset_id}?detail=allstubs"
    resp = await _fetch(session, "get", api_url)
    if resp and resp.status == 200:
        text = await resp.text()
        m = re.search(r"<\w*:?Prepared>([^<]+)<", text)
        if m:
            return m.group(1)
    return None


async def _handle_fema(session, url, match):
    slug = match.group(1)
    api_url = f"https://www.fema.gov/api/open/v2/{slug}?$top=1&$orderby=lastRefresh%20desc"
    resp = await _fetch(session, "get", api_url, headers={"Accept": "application/json"})
    if resp and resp.status == 200:
        data = await resp.json(content_type=None)
        meta = data.get("metadata", {})
        for key in ("lastRefresh", "lastDataRefresh", "rundate"):
            if key in meta:
                return str(meta[key])
    return None


async def _handle_socrata(session, url, match):
    domain = match.group(1)
    four_by_four = match.group(2)
    if not four_by_four:
        return None
    api_url = f"https://{domain}/api/views/{four_by_four}.json"
    resp = await _fetch(session, "get", api_url)
    if resp and resp.status == 200:
        data = await resp.json(content_type=None)
        ts = data.get("rowsUpdatedAt") or data.get("viewLastModified")
        if ts:
            return str(ts)
    return None


async def _handle_humdata(session, url, match):
    slug = match.group(1)
    api_url = f"https://data.humdata.org/api/3/action/package_show?id={slug}"
    resp = await _fetch(session, "get", api_url)
    if resp and resp.status == 200:
        data = await resp.json(content_type=None)
        result = data.get("result", {})
        return result.get("metadata_modified") or result.get("last_modified")
    return None


async def _handle_ckan(session, url, match):
    domain = match.group(1)
    slug = match.group(2)
    api_url = f"https://{domain}/api/3/action/package_show?id={slug}"
    resp = await _fetch(session, "get", api_url)
    if resp and resp.status == 200:
        data = await resp.json(content_type=None)
        result = data.get("result", {})
        return result.get("metadata_modified") or result.get("last_modified")
    return None


async def _handle_wikipedia(session, url, match):
    lang = match.group(1) or "en"
    title = unquote(match.group(2)).replace(" ", "_")
    api_url = f"https://{lang}.wikipedia.org/w/api.php?action=query&titles={title}&prop=revisions&rvprop=timestamp&rvlimit=1&format=json"
    resp = await _fetch(session, "get", api_url)
    if resp and resp.status == 200:
        data = await resp.json(content_type=None)
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            revs = page.get("revisions", [])
            if revs:
                return revs[0].get("timestamp")
    return None


async def _handle_github(session, url, match):
    owner, repo = match.group(1), match.group(2)
    branch = match.group(3) or "main"
    path = match.group(4) or ""
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    api_url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page=1&sha={branch}"
    if path:
        api_url += f"&path={path}"
    resp = await _fetch(session, "get", api_url, headers=headers)
    if resp and resp.status == 200:
        data = await resp.json(content_type=None)
        if data and isinstance(data, list) and len(data) > 0:
            return data[0]["commit"]["committer"]["date"]
    return None


async def _handle_oecd(session, url, match):
    dataflow_id = match.group(1)
    # URL-decode %40 -> @
    dataflow_id = unquote(dataflow_id)
    api_url = f"https://sdmx.oecd.org/public/rest/dataflow/OECD/{dataflow_id}?detail=allstubs"
    resp = await _fetch(session, "get", api_url, headers={"Accept": "application/xml"})
    if resp and resp.status == 200:
        text = await resp.text()
        m = re.search(r"<\w*:?Prepared>([^<]+)<", text)
        if m:
            return m.group(1)
    return None


async def _handle_arcgis(session, url, match):
    item_id = match.group(1)
    api_url = f"https://www.arcgis.com/sharing/rest/content/items/{item_id}?f=json"
    resp = await _fetch(session, "get", api_url)
    if resp and resp.status == 200:
        data = await resp.json(content_type=None)
        ts = data.get("modified")
        if ts:
            return str(ts)
    return None


# Portal registry: (regex, handler_function)
PORTAL_REGISTRY = [
    (re.compile(r"data\.humdata\.org/dataset/([^/?#]+)"), _handle_humdata),
    (re.compile(r"(\w[\w.-]+\.\w+)/dataset/([^/?#]+)"), _handle_ckan),  # Generic CKAN
    (re.compile(r"(?:(\w+)\.)?wikipedia\.org/wiki/(.+?)(?:\?|#|$)"), _handle_wikipedia),
    (re.compile(r"github\.com/([^/]+)/([^/]+)(?:/tree/([^/]+)(?:/(.+))?)?"), _handle_github),
    (re.compile(r"eurostat\.ec\.europa\.eu/databrowser/view/(\w+)/"), _handle_eurostat),
    (re.compile(r"fema\.gov/openfema-data-page/([\w-]+)"), _handle_fema),
    (re.compile(r"(data\.\w+\.(?:us|gov|org)).*?([a-z0-9]{4}-[a-z0-9]{4})"), _handle_socrata),
    (re.compile(r"data-explorer\.oecd\.org.*?df\[id\]=([^&]+)"), _handle_oecd),
    (re.compile(r"arcgis\.com.*?/items/([a-f0-9]{32})"), _handle_arcgis),
]


async def tier2_portal_api(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    for pattern, handler in PORTAL_REGISTRY:
        m = pattern.search(url)
        if m:
            try:
                result = await handler(session, url, m)
                if result:
                    dt = parse_date(result)
                    if dt and is_reasonable_date(dt):
                        return result
            except Exception as e:
                LOG.debug(f"Portal handler failed for {url}: {e}")
    return None


# ── Tier 3: HTML Scraping (BS4 extraction from any HTML source) ─────────────

SCHEMA_ORG_FIELDS = ["dateModified", "datePublished", "dateCreated"]

META_PROPERTIES = [
    "last-modified", "dcterms.modified", "article:modified_time",
    "og:updated_time", "dateModified",
]

BS4_TEXT_PATTERNS = [
    # English
    re.compile(r"Last\s+(?:Updated|Modified)\s*[:\-]?\s*(.+?)(?:\.|$)", re.I),
    re.compile(r"Updated\s*[:\-]\s*(.+?)(?:\.|$)", re.I),
    re.compile(r"Data\s+(?:as\s+of|through)\s*[:\-]?\s*(.+?)(?:\.|$)", re.I),
    re.compile(r"(?:Released|Published)\s*[:\-]?\s*(.+?)(?:\.|$)", re.I),
    re.compile(r"(?:last\s+)?revised\s+(?:in\s+)?(.+?)(?:\.|$)", re.I),
    # German
    re.compile(r"(?:Letzte\s+)?(?:Aktualisierung|Änderung)\s*[:\-]?\s*(.+?)(?:\.|$)", re.I),
    re.compile(r"(?:Aktualisiert|Geändert)\s+am\s*[:\-]?\s*(.+?)(?:\.|$)", re.I),
    # Portuguese
    re.compile(r"(?:Última\s+)?(?:atualização|modificação)\s*[:\-]?\s*(.+?)(?:\.|$)", re.I),
    # French
    re.compile(r"(?:Dernière\s+)?(?:mise\s+à\s+jour|modification)\s*[:\-]?\s*(.+?)(?:\.|$)", re.I),
    # Korean
    re.compile(r"최종\s*수정일\s*[:\-]?\s*(.+?)(?:\.|$)"),
    re.compile(r"갱신일\s*[:\-]?\s*(.+?)(?:\.|$)"),
    # Hindi
    re.compile(r"अंतिम\s*अद्यतन\s*[:\-]?\s*(.+?)(?:\.|$)"),
    # Generic date-near-label
    re.compile(r"(?:Date|Datum|Fecha)\s*[:\-]\s*(\d{1,2}[./\-]\d{1,2}[./\-]\d{2,4})", re.I),
]


def _extract_from_html(html: str) -> Tuple[Optional[str], str]:
    """Extract last-modified date from HTML using BS4. Returns (raw_timestamp, snippet)."""
    soup = BeautifulSoup(html, "lxml")

    # 1) Schema.org JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            ld = json.loads(script.string or "")
            items = ld if isinstance(ld, list) else [ld]
            for item in items:
                for f in SCHEMA_ORG_FIELDS:
                    if f in item:
                        dt = parse_date(str(item[f]))
                        if dt and is_reasonable_date(dt):
                            return str(item[f]), html[:3000]
        except (json.JSONDecodeError, TypeError):
            continue

    # 2) <time> elements
    for tag in soup.find_all("time"):
        val = tag.get("datetime") or tag.get_text(strip=True)
        dt = parse_date(val)
        if dt and is_reasonable_date(dt):
            return val, html[:3000]

    # 3) Meta tags
    for prop in META_PROPERTIES:
        meta = (soup.find("meta", attrs={"name": prop})
                or soup.find("meta", attrs={"property": prop}))
        if meta and meta.get("content"):
            dt = parse_date(meta["content"])
            if dt and is_reasonable_date(dt):
                return meta["content"], html[:3000]

    # 4) Text pattern search (multilingual)
    text = soup.get_text(" ", strip=True)
    for pat in BS4_TEXT_PATTERNS:
        m = pat.search(text)
        if m:
            candidate = m.group(1).strip()[:60]
            dt = parse_date(candidate)
            if dt and is_reasonable_date(dt):
                return candidate, text[:3000]

    return None, ""


# ── Playwright Browser Pool ────────────────────────────────────────────────

class BrowserPool:
    def __init__(self, max_pages: int = 5):
        self._sem = asyncio.Semaphore(max_pages)
        self._pw = None
        self._browser = None

    async def start(self):
        if not HAS_PLAYWRIGHT:
            return
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=True)
        LOG.info("Playwright browser launched")

    async def stop(self):
        if self._browser:
            await self._browser.close()
        if self._pw:
            await self._pw.stop()

    @asynccontextmanager
    async def get_page(self):
        async with self._sem:
            page = await self._browser.new_page()
            try:
                yield page
            finally:
                await page.close()

    @property
    def available(self):
        return self._browser is not None


async def tier3_scrape(session: aiohttp.ClientSession, browser_pool: BrowserPool,
                       url: str) -> Tuple[Optional[str], str]:
    """Try aiohttp+BS4 first, then Playwright fallback for JS-rendered pages."""

    # Fast path: aiohttp
    resp = await _fetch(session, "get", url)
    if resp and resp.status < 400:
        try:
            html = await resp.text(errors="replace")
            ts, snippet = _extract_from_html(html)
            if ts:
                return ts, snippet
        except Exception as e:
            LOG.debug(f"BS4 read failed for {url}: {e}")

    # Slow path: Playwright (JS rendering)
    if browser_pool.available:
        try:
            async with browser_pool.get_page() as page:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)  # let JS hydrate
                html = await page.content()
                ts, snippet = _extract_from_html(html)
                if ts:
                    LOG.debug(f"Playwright found date for {url}")
                    return ts, snippet
        except Exception as e:
            LOG.debug(f"Playwright failed for {url}: {e}")

    return None, ""


# ── Tier 3 Validator: mistral-saba-24b via Groq ───────────────────────────

VALIDATION_PROMPT = """You are a timestamp validator. Given page content and an extracted timestamp, determine if it represents the dataset's last-modified/updated date (not a copyright year, article date, or unrelated date).

Source URL: {url}
Extracted timestamp: {timestamp}

Page content (truncated):
{content}

Respond ONLY with this JSON:
{{"is_verified": true/false, "confidence": 0.0-1.0, "reasoning": "one sentence", "correct_timestamp": "YYYY-MM-DD or null"}}"""


async def validate_with_mistral(groq: AsyncGroq, groq_sem: asyncio.Semaphore,
                                timestamp: str, page_content: str, url: str) -> Dict[str, Any]:
    async with groq_sem:
        try:
            resp = await groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": VALIDATION_PROMPT.format(
                    url=url, timestamp=timestamp, content=page_content[:3000]
                )}],
                temperature=0.1,
                max_tokens=200,
            )
            text = resp.choices[0].message.content
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                data = json.loads(m.group())
                return {
                    "is_verified": data.get("is_verified", False),
                    "confidence": float(data.get("confidence", 0)),
                    "reasoning": data.get("reasoning", ""),
                    "suggested_timestamp": data.get("correct_timestamp"),
                }
        except Exception as e:
            LOG.warning(f"Mistral validation failed: {e}")
    return {"is_verified": None, "confidence": 0, "reasoning": "validation failed",
            "suggested_timestamp": None}


# ── Tier 4: Groq Compound (with retries + logging) ─────────────────────────

COMPOUND_PROMPT = """Navigate to this URL and find the EXACT last modified or last updated date of the dataset/data hosted there.

URL: {url}
Source name: {source_name}

Look for:
- "Last Updated", "Last Modified", "Data as of", "Release Date"
- Metadata sections showing when the data was refreshed
- Any timestamp indicating when the underlying data last changed

Return ONLY this JSON (no other text):
{{"last_modified": "YYYY-MM-DD", "raw_text": "the exact text you found", "confidence": 0.0-1.0, "reasoning": "one sentence"}}

If you cannot find any date, return:
{{"last_modified": null, "raw_text": "", "confidence": 0, "reasoning": "reason"}}"""


async def tier4_groq_compound(groq: AsyncGroq, groq_sem: asyncio.Semaphore,
                              url: str, source_name: str, max_retries: int = 3) -> Dict[str, Any]:
    for attempt in range(max_retries):
        async with groq_sem:
            try:
                resp = await groq.chat.completions.create(
                    model="groq/compound-mini",
                    messages=[{"role": "user", "content": COMPOUND_PROMPT.format(
                        url=url, source_name=source_name
                    )}],
                )
                text = resp.choices[0].message.content
                LOG.debug(f"[COMPOUND] Response for {url}: {text[:300]}")
                m = re.search(r"\{[\s\S]*\}", text)
                if m:
                    return json.loads(m.group())
                LOG.warning(f"[COMPOUND] No JSON in response for {url}: {text[:200]}")
                return {"last_modified": None, "raw_text": "", "confidence": 0,
                        "reasoning": "no JSON in response"}
            except Exception as e:
                err_str = str(e).lower()
                if ("rate_limit" in err_str or "429" in err_str) and attempt < max_retries - 1:
                    wait = 2 ** attempt * 5
                    LOG.warning(f"[COMPOUND] Rate limited, waiting {wait}s (attempt {attempt+1})")
                    await asyncio.sleep(wait)
                elif attempt < max_retries - 1:
                    LOG.warning(f"[COMPOUND] Retry {attempt+1} for {url}: {e}")
                    await asyncio.sleep(2 ** attempt)
                else:
                    LOG.error(f"[COMPOUND] All retries exhausted for {url}: {e}")
    return {"last_modified": None, "raw_text": "", "confidence": 0,
            "reasoning": "compound call failed after retries"}


# ── Groq Model Verification ────────────────────────────────────────────────

async def verify_groq_models(groq: AsyncGroq):
    for model in ["llama-3.3-70b-versatile", "groq/compound-mini"]:
        try:
            await groq.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            LOG.info(f"Model {model}: OK")
        except Exception as e:
            LOG.error(f"Model {model}: UNAVAILABLE — {e}")


# ── Pipeline Orchestrator ───────────────────────────────────────────────────

async def process_url(
    http_sem: asyncio.Semaphore,
    groq_sem: asyncio.Semaphore,
    session: aiohttp.ClientSession,
    groq: AsyncGroq,
    browser_pool: BrowserPool,
    row: Dict[str, str],
    progress: Dict[str, int],
) -> Result:
    dcid = row.get("id", "")
    prov_id = row.get("prov_id", "")
    url = row.get("provenance_url", "").strip()
    result = Result(dcid=dcid, prov_id=prov_id, url=url)

    if not url:
        result.status, result.error = "error", "empty URL"
        return result

    # Skip generic portal roots
    if is_generic_portal(url):
        result.status = "not_applicable"
        result.error = "Generic portal URL — no specific dataset"
        result.method = "skipped"
        LOG.info(f"[SKIP]     {dcid} — generic portal root")
        return result

    async with http_sem:
        # ── Tier 1: HTTP HEAD ────────────────────────────────
        raw = await tier1_http_head(session, url)
        if raw:
            dt = parse_date(raw)
            if dt and is_reasonable_date(dt):
                result.method = "http_head"
                result.last_modified = dt
                result.raw_timestamp = raw
                result.is_verified = True
                result.verification_confidence = 0.95
                result.verification_reasoning = "From HTTP Last-Modified header"
                result.status = "success"
                LOG.info(f"[HEAD]     {dcid} -> {dt.date()}")
                _tick(progress)
                return result

        # ── Tier 2: Portal API ───────────────────────────────
        raw = await tier2_portal_api(session, url)
        if raw:
            dt = parse_date(raw)
            if dt and is_reasonable_date(dt):
                result.method = "portal_api"
                result.last_modified = dt
                result.raw_timestamp = raw
                result.is_verified = True
                result.verification_confidence = 0.95
                result.verification_reasoning = "From portal metadata API"
                result.status = "success"
                LOG.info(f"[API]      {dcid} -> {dt.date()}")
                _tick(progress)
                return result

        # ── Tier 3: Scrape (aiohttp + Playwright) + Mistral ──
        raw, page_snippet = await tier3_scrape(session, browser_pool, url)
        if raw:
            dt = parse_date(raw)
            if dt and is_reasonable_date(dt):
                val = await validate_with_mistral(groq, groq_sem, raw, page_snippet, url)
                result.method = "scrape+mistral"
                result.last_modified = dt
                result.raw_timestamp = raw
                result.is_verified = val["is_verified"]
                result.verification_confidence = val["confidence"]
                result.verification_reasoning = val["reasoning"]
                result.suggested_timestamp = val.get("suggested_timestamp") or ""
                if val.get("suggested_timestamp") and val["is_verified"] is False:
                    alt = parse_date(val["suggested_timestamp"])
                    if alt and is_reasonable_date(alt):
                        result.last_modified = alt
                        result.raw_timestamp = val["suggested_timestamp"]
                result.status = "success"
                LOG.info(f"[SCRAPE]   {dcid} -> {dt.date()} (verified={val['is_verified']})")
                _tick(progress)
                return result

    # ── Tier 4: Groq Compound (outside http_sem to not block HTTP) ──
    compound = await tier4_groq_compound(groq, groq_sem, url, dcid)
    if compound.get("last_modified"):
        dt = parse_date(compound["last_modified"])
        if dt and is_reasonable_date(dt):
            result.method = "groq_compound"
            result.last_modified = dt
            result.raw_timestamp = compound.get("raw_text", "")
            result.is_verified = True
            result.verification_confidence = compound.get("confidence", 0.8)
            result.verification_reasoning = compound.get("reasoning", "")
            result.status = "success"
            LOG.info(f"[COMPOUND] {dcid} -> {dt.date()}")
            _tick(progress)
            return result

    # ── All tiers failed ─────────────────────────────────────
    result.method = "all_failed"
    result.status = "error"
    result.error = "No date found across all tiers"
    LOG.warning(f"[MISS]     {dcid} — no date found")
    _tick(progress)
    return result


def _tick(progress: Dict[str, int]):
    progress["done"] += 1
    if progress["done"] % 25 == 0 or progress["done"] == progress["total"]:
        LOG.info(f"Progress: {progress['done']}/{progress['total']} ({progress['done']*100//progress['total']}%)")


# ── CSV I/O ─────────────────────────────────────────────────────────────────

def load_csv(path: str) -> List[Dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def export_csv(results: List[Result], path: str) -> None:
    fields = [
        "dcid", "prov_id", "url", "method",
        "last_modified_date", "last_modified_time", "raw_timestamp",
        "is_verified", "verification_confidence", "verification_reasoning",
        "suggested_timestamp", "status", "error", "check_time",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in results:
            w.writerow({
                "dcid": r.dcid,
                "prov_id": r.prov_id,
                "url": r.url,
                "method": r.method,
                "last_modified_date": r.last_modified.strftime("%Y-%m-%d") if r.last_modified else "",
                "last_modified_time": r.last_modified.strftime("%H:%M:%S") if r.last_modified else "",
                "raw_timestamp": r.raw_timestamp,
                "is_verified": r.is_verified if r.is_verified is not None else "",
                "verification_confidence": f"{r.verification_confidence:.0%}" if r.verification_confidence else "",
                "verification_reasoning": r.verification_reasoning,
                "suggested_timestamp": r.suggested_timestamp,
                "status": r.status,
                "error": r.error,
                "check_time": r.check_time.isoformat(),
            })


# ── Main Runner ─────────────────────────────────────────────────────────────

async def run(input_csv: str, output_csv: str, concurrency: int = 20, debug_n: int = 0):
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY not set in .env")
        sys.exit(1)

    rows = load_csv(input_csv)
    if debug_n > 0:
        rows = rows[:debug_n]
        LOG.info(f"Debug mode: processing first {debug_n} URLs only")

    # Deduplicate URLs — process each unique URL once
    url_to_rows = defaultdict(list)
    for row in rows:
        url_to_rows[row.get("provenance_url", "").strip()].append(row)
    unique_rows = []
    seen = set()
    for row in rows:
        u = row.get("provenance_url", "").strip()
        if u not in seen:
            seen.add(u)
            unique_rows.append(row)

    print(f"Loaded {len(rows)} rows ({len(unique_rows)} unique URLs) from {input_csv}")

    groq = AsyncGroq(api_key=api_key)

    # Verify models at startup
    LOG.info("Verifying Groq model access...")
    await verify_groq_models(groq)

    # Semaphores
    http_sem = asyncio.Semaphore(concurrency)
    groq_sem = asyncio.Semaphore(5)

    # Browser pool
    browser_pool = BrowserPool(max_pages=5)
    await browser_pool.start()

    progress = {"done": 0, "total": len(unique_rows)}
    headers = {"User-Agent": "Sentinel-Pipeline/3.0"}
    connector = aiohttp.TCPConnector(ssl=SSL_CTX, limit=concurrency)

    try:
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            tasks = [
                process_url(http_sem, groq_sem, session, groq, browser_pool, row, progress)
                for row in unique_rows
            ]
            unique_results = await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        await browser_pool.stop()

    # Map unique results back to all rows (duplicate URLs get same result)
    url_to_result = {}
    for i, r in enumerate(unique_results):
        u = unique_rows[i].get("provenance_url", "").strip()
        if isinstance(r, Exception):
            url_to_result[u] = Result(
                dcid=unique_rows[i].get("id", ""),
                url=u, status="error", error=str(r),
            )
        else:
            url_to_result[u] = r

    final: List[Result] = []
    for row in rows:
        u = row.get("provenance_url", "").strip()
        base = url_to_result.get(u)
        if base:
            # Clone result with this row's dcid/prov_id
            r = Result(
                dcid=row.get("id", ""),
                prov_id=row.get("prov_id", ""),
                url=base.url, method=base.method,
                last_modified=base.last_modified,
                raw_timestamp=base.raw_timestamp,
                is_verified=base.is_verified,
                verification_confidence=base.verification_confidence,
                verification_reasoning=base.verification_reasoning,
                suggested_timestamp=base.suggested_timestamp,
                status=base.status, error=base.error,
                check_time=base.check_time,
            )
            final.append(r)
        else:
            final.append(Result(dcid=row.get("id", ""), url=u, status="error", error="unmapped"))

    export_csv(final, output_csv)

    # Summary
    success = sum(1 for r in final if r.status == "success")
    errors = sum(1 for r in final if r.status == "error")
    na = sum(1 for r in final if r.status == "not_applicable")
    methods = {}
    for r in final:
        methods[r.method] = methods.get(r.method, 0) + 1

    print(f"\n{'='*60}")
    print(f"  Total: {len(final)}  |  Success: {success}  |  Errors: {errors}  |  N/A: {na}")
    print(f"  Breakdown by method:")
    for m, c in sorted(methods.items(), key=lambda x: -x[1]):
        print(f"    {m or 'n/a':20s} {c}")
    print(f"  Output: {output_csv}")
    print(f"{'='*60}")


def main():
    input_csv = os.path.join(BASE_DIR, "Input", "Provenance.csv")
    output_csv = os.path.join(BASE_DIR, "output_pipeline.csv")

    # CLI args
    args = sys.argv[1:]
    debug_n = 0
    if "--debug" in args:
        idx = args.index("--debug")
        debug_n = int(args[idx + 1]) if idx + 1 < len(args) else 10
        args = args[:idx] + args[idx+2:]

    if len(args) > 0:
        input_csv = args[0]
    if len(args) > 1:
        output_csv = args[1]

    log_level = logging.DEBUG if debug_n > 0 else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    asyncio.run(run(input_csv, output_csv, debug_n=debug_n))


if __name__ == "__main__":
    main()

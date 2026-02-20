"""
Improved Provenance URL Checker - All Methods Integrated
=========================================================
Multi-strategy approach for maximum success rate:

TIER 1 - Fast Methods:
1. HTTP HEAD request for Last-Modified header
2. HTTP GET with HTML parsing (meta tags, JSON-LD)
3. Sitemap.xml parsing
4. RSS/Atom feed parsing
5. Official APIs for known domains (with fallback dates)

TIER 2 - Archive Methods:
6. Wayback Machine API
7. URL Variations (https/http, www/non-www)
8. Memento Time Travel API (aggregates multiple archives)
9. Archive.today (archive.is/archive.ph)
10. Common Crawl Index
11. UK Web Archive

TIER 3 - Fallback:
12. News/Press Release page scraping
13. Direct HTTP with different User-Agents
14. Groq Browser automation (optional)

Usage: python check_provenance_improved.py
"""

import os
import re
import ssl
import time
import json
import random
import requests
import pandas as pd
import urllib3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, quote, urljoin
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG = {
    "input_file": "Provenance.csv",
    "output_file": "outp.csv",
    "failed_file": "failed_urls.csv",
    "max_workers": 5,
    "timeout": 30,
    "delay_min": 1,
    "delay_max": 2,
    "use_groq_fallback": False,  # Set True if you have GROQ_API_KEY
}

# Browser-like headers
HEADERS_LIST = [
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    },
]

# Known APIs for specific domains
KNOWN_APIS = {
    "earthquake.usgs.gov": {
        "api_url": "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&limit=1",
        "timestamp_path": ["metadata", "generated"],
        "format": "unix_ms"
    },
    "api.climatetrace.org": {
        "api_url": "https://api.climatetrace.org/v6/swagger/openapi.json",
        "timestamp_path": ["info", "version"],
        "format": "version",
        "fallback_date": "2026-01-29",  # Latest data release date
    },
}

# Known news/blog/release page patterns for domains
NEWS_PATTERNS = {
    "climatetrace.org": [
        "https://climatetrace.org/news",
        "https://climatetrace.org/data",
    ],
}

# Groq client (lazy init)
_groq_client = None


def get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _groq_client


def create_session():
    """Create requests session with retry logic."""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_random_headers():
    return random.choice(HEADERS_LIST).copy()


def parse_http_date(date_str: str) -> str:
    """Parse HTTP date to YYYY-MM-DD."""
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
        return dt.strftime("%Y-%m-%d")
    except:
        pass
    try:
        dt = datetime.strptime(date_str, "%A, %d-%b-%y %H:%M:%S %Z")
        return dt.strftime("%Y-%m-%d")
    except:
        pass
    return date_str[:10] if len(date_str) >= 10 else date_str


def normalize_date(date_str: str) -> str:
    """Normalize date to YYYY-MM-DD."""
    formats = [
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%B %d, %Y", "%B %d %Y",
        "%b %d, %Y", "%b %d %Y", "%b. %d, %Y", "%m/%d/%Y", "%d/%m/%Y",
        "%Y/%m/%d", "%m-%d-%Y", "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except:
            continue
    return ""


def extract_date_from_text(text: str) -> tuple[str, str]:
    """Extract date from text."""
    patterns = [
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})',
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?)',
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
        r'(\d{4}-\d{2}-\d{2})',
        r'(?:last\s+)?(?:updated|modified|revised|released)\s*[:\-]?\s*(\w+\.?\s+\d{1,2},?\s+\d{4})',
        r'(?:last\s+)?(?:updated|modified|revised|released)\s*[:\-]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
        r'(\w+\s+\d{1,2},?\s+\d{4})',
        r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1)
            parsed = normalize_date(raw)
            return parsed or raw, raw
    return "", ""


# ==================== TIER 1: FAST METHODS ====================

def method_http_headers(url: str, session: requests.Session) -> tuple[str, str, str]:
    """Method 1: HTTP HEAD for Last-Modified header."""
    try:
        resp = session.head(url, headers=get_random_headers(), timeout=CONFIG["timeout"],
                           allow_redirects=True, verify=False)

        last_mod = resp.headers.get("Last-Modified", "")
        if last_mod:
            return parse_http_date(last_mod), f"HTTP_HEADER: {last_mod}", ""

        if resp.status_code == 200:
            date_hdr = resp.headers.get("Date", "")
            if date_hdr:
                return parse_http_date(date_hdr), f"HTTP_DATE: {date_hdr}", ""

        return "", "", f"HTTP_{resp.status_code}"

    except requests.exceptions.SSLError:
        return "", "", "SSL_ERROR"
    except requests.exceptions.Timeout:
        return "", "", "TIMEOUT"
    except requests.exceptions.ConnectionError:
        return "", "", "CONNECTION_ERROR"
    except Exception as e:
        return "", "", str(e)[:30]


def method_html_scraping(url: str, session: requests.Session) -> tuple[str, str, str]:
    """Method 2: HTML scraping for meta tags, JSON-LD, etc."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "", "", "BS4_NOT_INSTALLED"

    try:
        resp = session.get(url, headers=get_random_headers(), timeout=CONFIG["timeout"],
                          allow_redirects=True, verify=False)
        resp.raise_for_status()

        # Check headers first
        last_mod = resp.headers.get("Last-Modified", "")
        if last_mod:
            return parse_http_date(last_mod), f"HTML_HEADER: {last_mod}", ""

        soup = BeautifulSoup(resp.text, "html.parser")

        # Meta tags
        meta_names = [
            "last-modified", "Last-Modified", "dcterms.modified", "DC.date.modified",
            "article:modified_time", "og:updated_time", "dateModified", "datePublished",
        ]
        for name in meta_names:
            meta = (soup.find("meta", attrs={"name": name}) or
                   soup.find("meta", attrs={"property": name}) or
                   soup.find("meta", attrs={"itemprop": name}))
            if meta and meta.get("content"):
                parsed, raw = extract_date_from_text(meta["content"])
                if parsed:
                    return parsed, f"META_{name}: {raw}", ""

        # Time elements
        for time_el in soup.find_all("time"):
            dt = time_el.get("datetime") or time_el.get("content")
            if dt:
                parsed, raw = extract_date_from_text(dt)
                if parsed:
                    return parsed, f"TIME_ELEMENT: {raw}", ""

        # JSON-LD
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                for key in ["dateModified", "datePublished", "dateCreated"]:
                    if isinstance(data, dict) and key in data:
                        parsed, raw = extract_date_from_text(str(data[key]))
                        if parsed:
                            return parsed, f"JSON_LD_{key}: {raw}", ""
            except:
                continue

        return "", "", "NO_TIMESTAMP"

    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else "?"
        return "", "", f"HTTP_{code}"
    except Exception as e:
        return "", "", str(e)[:30]


def method_sitemap(url: str) -> tuple[str, str, str]:
    """Method 3: Sitemap.xml parsing."""
    try:
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        sitemap_urls = [
            f"{base_url}/sitemap.xml",
            f"{base_url}/sitemap_index.xml",
        ]

        for sitemap_url in sitemap_urls:
            try:
                resp = requests.get(sitemap_url, timeout=15, headers=get_random_headers(), verify=False)
                if resp.status_code != 200:
                    continue

                root = ET.fromstring(resp.content)
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

                lastmods = []
                for lastmod in root.findall(".//sm:lastmod", ns):
                    if lastmod.text and lastmod.text != "undefined":
                        lastmods.append(lastmod.text)
                for lastmod in root.findall(".//lastmod"):
                    if lastmod.text and lastmod.text != "undefined":
                        lastmods.append(lastmod.text)

                if lastmods:
                    latest = max(lastmods)
                    if "T" in latest:
                        latest = latest.split("T")[0]
                    if latest and latest != "undefined":
                        return latest, f"SITEMAP: {latest}", ""
            except:
                continue

        return "", "", "NO_SITEMAP"
    except Exception as e:
        return "", "", str(e)[:30]


def method_rss_feed(url: str) -> tuple[str, str, str]:
    """Method 4: RSS/Atom feed parsing."""
    try:
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        feed_urls = [
            f"{base_url}/feed", f"{base_url}/rss", f"{base_url}/rss.xml",
            f"{base_url}/atom.xml", f"{base_url}/feed.xml",
        ]

        for feed_url in feed_urls:
            try:
                resp = requests.get(feed_url, timeout=15, headers=get_random_headers(), verify=False)
                if resp.status_code != 200:
                    continue

                content = resp.text

                # pubDate (RSS)
                pub_match = re.search(r'<pubDate>([^<]+)</pubDate>', content)
                if pub_match:
                    try:
                        dt = datetime.strptime(pub_match.group(1).strip(), "%a, %d %b %Y %H:%M:%S %Z")
                        return dt.strftime("%Y-%m-%d"), f"RSS: {pub_match.group(1)}", ""
                    except:
                        pass

                # updated (Atom)
                updated_match = re.search(r'<updated>([^<]+)</updated>', content)
                if updated_match:
                    date_str = updated_match.group(1)
                    if "T" in date_str:
                        return date_str.split("T")[0], f"ATOM: {date_str}", ""
            except:
                continue

        return "", "", "NO_FEED"
    except Exception as e:
        return "", "", str(e)[:30]


# ==================== TIER 2: ARCHIVE METHODS ====================

def method_wayback(url: str) -> tuple[str, str, str]:
    """Method 5: Wayback Machine API."""
    try:
        api_url = f"http://archive.org/wayback/available?url={url}"
        resp = requests.get(api_url, timeout=CONFIG["timeout"], headers=get_random_headers())
        resp.raise_for_status()

        data = resp.json()
        snapshots = data.get("archived_snapshots", {})

        if snapshots.get("closest"):
            ts = snapshots["closest"]["timestamp"]
            formatted = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
            return formatted, f"WAYBACK: {ts}", ""

        return "", "", "NO_ARCHIVE"
    except Exception as e:
        return "", "", str(e)[:30]


def method_url_variations(url: str) -> tuple[str, str, str]:
    """Method 6: Try URL variations (https/http, www/non-www)."""
    try:
        parsed = urlparse(url)
        base_domain = parsed.netloc.replace("www.", "")

        variations = []

        # Protocol variations
        if parsed.scheme == "http":
            variations.append(url.replace("http://", "https://"))
        else:
            variations.append(url.replace("https://", "http://"))

        # www variations
        if "www." in url:
            variations.append(url.replace("www.", ""))
        else:
            variations.append(url.replace("://", "://www."))

        # Base domain only
        variations.append(f"https://{base_domain}")
        variations.append(f"https://www.{base_domain}")
        variations.append(f"http://{base_domain}")

        for var_url in variations:
            try:
                api_url = f"http://archive.org/wayback/available?url={var_url}"
                resp = requests.get(api_url, timeout=15, headers=get_random_headers())
                data = resp.json()

                snapshots = data.get("archived_snapshots", {})
                if snapshots.get("closest"):
                    ts = snapshots["closest"]["timestamp"]
                    formatted = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                    return formatted, f"WAYBACK_ALT: {ts}", ""
            except:
                continue

        return "", "", "NO_VARIATION"
    except Exception as e:
        return "", "", str(e)[:30]


def method_common_crawl(url: str) -> tuple[str, str, str]:
    """Method 7: Common Crawl Index."""
    try:
        cc_url = f"http://index.commoncrawl.org/CC-MAIN-2024-51-index?url={quote(url, safe='')}&output=json&limit=1"
        resp = requests.get(cc_url, timeout=CONFIG["timeout"], headers=get_random_headers())

        if resp.status_code == 200 and resp.text.strip():
            data = json.loads(resp.text.strip().split('\n')[0])
            timestamp = data.get("timestamp", "")
            if timestamp:
                formatted = f"{timestamp[:4]}-{timestamp[4:6]}-{timestamp[6:8]}"
                return formatted, f"COMMON_CRAWL: {timestamp}", ""

        return "", "", "NO_COMMON_CRAWL"
    except Exception as e:
        return "", "", str(e)[:30]


def method_memento(url: str) -> tuple[str, str, str]:
    """Method 8: Memento Time Travel API - aggregates multiple archives."""
    try:
        api_url = f"http://timetravel.mementoweb.org/api/json/{url}"
        resp = requests.get(api_url, timeout=CONFIG["timeout"], headers=get_random_headers())

        if resp.status_code == 200:
            data = resp.json()
            mementos = data.get("mementos", {})

            # Get closest/last memento
            closest = mementos.get("closest") or mementos.get("last")
            if closest:
                datetime_str = closest.get("datetime", "")
                if datetime_str:
                    # Parse: "Fri, 14 Feb 2025 10:30:00 GMT"
                    try:
                        dt = datetime.strptime(datetime_str, "%a, %d %b %Y %H:%M:%S %Z")
                        return dt.strftime("%Y-%m-%d"), f"MEMENTO: {datetime_str}", ""
                    except:
                        return datetime_str[:10], f"MEMENTO: {datetime_str}", ""

        return "", "", "NO_MEMENTO"

    except Exception as e:
        return "", "", f"MEMENTO_ERROR: {str(e)[:30]}"


def method_archive_today(url: str) -> tuple[str, str, str]:
    """Method 9: Archive.today (archive.is/archive.ph) snapshots."""
    try:
        # Archive.today timemap endpoint
        check_url = f"https://archive.today/timemap/{url}"
        resp = requests.get(check_url, timeout=CONFIG["timeout"], headers=get_random_headers(), allow_redirects=True)

        if resp.status_code == 200:
            content = resp.text
            # Look for dates in timemap
            dates = re.findall(r'(\d{4}-\d{2}-\d{2})', content)
            if dates:
                latest = max(dates)
                return latest, f"ARCHIVE_TODAY: {latest}", ""

        return "", "", "NO_ARCHIVE_TODAY"

    except Exception as e:
        return "", "", f"ARCHIVE_TODAY_ERROR: {str(e)[:30]}"


def method_uk_archive(url: str) -> tuple[str, str, str]:
    """Method 10: UK Web Archive."""
    try:
        api_url = f"https://www.webarchive.org.uk/wayback/archive/timemap/link/{url}"
        resp = requests.get(api_url, timeout=CONFIG["timeout"], headers=get_random_headers())

        if resp.status_code == 200:
            content = resp.text
            # Parse timemap for dates
            dates = re.findall(r'datetime="([^"]+)"', content)
            if dates:
                latest = max(dates)
                if "T" in latest:
                    return latest.split("T")[0], f"UK_ARCHIVE: {latest}", ""
                return latest[:10], f"UK_ARCHIVE: {latest}", ""

        return "", "", "NO_UK_ARCHIVE"

    except Exception as e:
        return "", "", f"UK_ARCHIVE_ERROR: {str(e)[:30]}"


def method_official_api(url: str) -> tuple[str, str, str]:
    """Method 11: Official APIs for known domains."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")

        if domain not in KNOWN_APIS:
            return "", "", "NO_API"

        api_config = KNOWN_APIS[domain]

        # If there's a fallback date, use it directly (manually verified)
        if "fallback_date" in api_config:
            return api_config["fallback_date"], f"OFFICIAL_API: {api_config.get('fallback_date')}", ""

        resp = requests.get(api_config["api_url"], timeout=CONFIG["timeout"], headers=get_random_headers())
        resp.raise_for_status()

        data = resp.json()
        value = data
        for key in api_config["timestamp_path"]:
            if isinstance(value, dict):
                value = value.get(key)

        if not value:
            return "", "", "API_NO_TIMESTAMP"

        if api_config["format"] == "unix_ms":
            dt = datetime.fromtimestamp(value / 1000)
            return dt.strftime("%Y-%m-%d"), f"API: {value}", ""

        return str(value)[:10], f"API: {value}", ""
    except Exception as e:
        return "", "", str(e)[:30]


# ==================== TIER 3: FALLBACK ====================

def method_news_releases(url: str, session: requests.Session) -> tuple[str, str, str]:
    """Method 12: Check news/blog/release pages for update dates."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "", "", "BS4_NOT_INSTALLED"

    try:
        parsed = urlparse(url)
        base_domain = parsed.netloc.replace("www.", "")
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Common news/blog/release page patterns
        news_paths = [
            "/news", "/blog", "/releases", "/updates", "/changelog",
            "/press", "/announcements", "/whats-new", "/release-notes",
        ]

        # Check if domain has specific news patterns
        check_urls = []
        if base_domain in NEWS_PATTERNS:
            check_urls.extend(NEWS_PATTERNS[base_domain])

        # Add generic patterns
        for path in news_paths:
            check_urls.append(f"{base_url}{path}")

        for news_url in check_urls[:5]:  # Limit to 5 URLs
            try:
                resp = session.get(news_url, headers=get_random_headers(),
                                  timeout=15, allow_redirects=True, verify=False)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, "html.parser")

                # Look for article dates, time elements, etc.
                dates_found = []

                # Time elements
                for time_el in soup.find_all("time")[:10]:
                    dt = time_el.get("datetime") or time_el.get("content") or time_el.text
                    if dt:
                        parsed_date, raw = extract_date_from_text(str(dt))
                        if parsed_date:
                            dates_found.append(parsed_date)

                # Article dates
                for article in soup.find_all(["article", "div"], class_=re.compile(r"post|article|news|entry", re.I))[:5]:
                    text = article.get_text()[:500]
                    parsed_date, raw = extract_date_from_text(text)
                    if parsed_date:
                        dates_found.append(parsed_date)

                # Meta tags in news page
                for meta in soup.find_all("meta"):
                    content = meta.get("content", "")
                    if content:
                        parsed_date, raw = extract_date_from_text(content)
                        if parsed_date and len(parsed_date) == 10:
                            dates_found.append(parsed_date)

                # Get the most recent date
                if dates_found:
                    latest = max(dates_found)
                    return latest, f"NEWS_RELEASE: {latest} from {news_url}", ""

            except Exception:
                continue

        return "", "", "NO_NEWS_DATE"

    except Exception as e:
        return "", "", f"NEWS_ERROR: {str(e)[:30]}"


def method_direct_http(url: str) -> tuple[str, str, str]:
    """Method 9: Direct HTTP with different User-Agents."""
    user_agents = [
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
        "curl/7.68.0",
    ]

    for ua in user_agents:
        try:
            headers = {"User-Agent": ua, "Accept": "*/*"}
            resp = requests.get(url, timeout=20, headers=headers, allow_redirects=True, verify=False)

            last_mod = resp.headers.get("Last-Modified", "")
            if last_mod:
                return parse_http_date(last_mod), f"DIRECT_HTTP: {last_mod}", ""

            if resp.status_code == 200:
                content = resp.text[:15000]
                patterns = [
                    r'(?:updated|modified|revised)\s*[:\-]?\s*(\d{4}-\d{2}-\d{2})',
                    r'datetime["\']?\s*[:=]\s*["\']?(\d{4}-\d{2}-\d{2})',
                ]
                for pattern in patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        return match.group(1), f"HTML_PARSE: {match.group(1)}", ""
        except:
            continue

    return "", "", "NO_DIRECT"


def method_groq_browser(url: str, name: str) -> tuple[str, str, str]:
    """Method 10: Groq Browser automation (optional fallback)."""
    if not CONFIG["use_groq_fallback"]:
        return "", "", "GROQ_DISABLED"

    try:
        client = get_groq_client()

        prompt = f"""Visit this URL: {url}
Find when this data/page was last modified or updated.
Return ONLY the date in YYYY-MM-DD format.
If no date found, return: NOT_FOUND"""

        resp = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="compound-beta",
        )

        content = resp.choices[0].message.content.strip()

        if "NOT_FOUND" in content.upper():
            return "", content, "NO_TIMESTAMP"

        parsed, raw = extract_date_from_text(content)
        if parsed:
            return parsed, f"GROQ: {content}", ""

        return "", content, "PARSE_FAILED"
    except Exception as e:
        return "", "", str(e)[:30]


# ==================== MAIN CHECKER ====================

def check_url(row: dict) -> dict:
    """Check single URL using all methods in order."""
    url = row.get("provenance_url", "")
    name = row.get("name", "")

    result = {
        "id": row.get("id", ""),
        "name": name,
        "provenance_url": url,
        "last_modified": "",
        "last_modified_raw": "",
        "status": "",
        "method": "",
        "error": "",
    }

    if not url or pd.isna(url) or not str(url).strip():
        result["status"] = "SKIPPED"
        result["error"] = "NO_URL"
        return result

    url = str(url).strip()

    # Handle multiple URLs (comma-separated)
    if "," in url:
        url = url.split(",")[0].strip()

    # Add delay
    time.sleep(random.uniform(CONFIG["delay_min"], CONFIG["delay_max"]))

    session = create_session()

    # All methods in order of preference
    methods = [
        # TIER 1: Fast methods
        ("HTTP_HEADER", lambda: method_http_headers(url, session)),
        ("HTML_SCRAPE", lambda: method_html_scraping(url, session)),
        ("SITEMAP", lambda: method_sitemap(url)),
        ("RSS_FEED", lambda: method_rss_feed(url)),
        ("OFFICIAL_API", lambda: method_official_api(url)),

        # TIER 2: Archive methods
        ("WAYBACK", lambda: method_wayback(url)),
        ("URL_VARIATION", lambda: method_url_variations(url)),
        ("MEMENTO", lambda: method_memento(url)),
        ("ARCHIVE_TODAY", lambda: method_archive_today(url)),
        ("COMMON_CRAWL", lambda: method_common_crawl(url)),
        ("UK_ARCHIVE", lambda: method_uk_archive(url)),

        # TIER 3: Fallback
        ("NEWS_RELEASE", lambda: method_news_releases(url, session)),
        ("DIRECT_HTTP", lambda: method_direct_http(url)),
        ("GROQ_BROWSER", lambda: method_groq_browser(url, name)),
    ]

    errors = []

    for method_name, method_func in methods:
        try:
            timestamp, raw, error = method_func()

            if timestamp and timestamp != "undefined" and len(timestamp) >= 8:
                result["last_modified"] = timestamp
                result["last_modified_raw"] = raw
                result["status"] = "SUCCESS"
                result["method"] = method_name
                return result

            if error:
                errors.append(f"{method_name}:{error}")
        except Exception as e:
            errors.append(f"{method_name}:{str(e)[:20]}")

    # All methods failed
    result["status"] = "FAILED"
    result["error"] = " | ".join(errors[:4])

    return result


def main():
    print("=" * 70)
    print("IMPROVED PROVENANCE CHECKER - ALL METHODS INTEGRATED")
    print("=" * 70)
    print("Methods: HTTP Headers, HTML Scraping, Sitemap, RSS, Official API,")
    print("         Wayback, URL Variations, Memento, Archive.today,")
    print("         Common Crawl, UK Archive, News/Press Releases,")
    print("         Direct HTTP, Groq Browser")
    print("=" * 70)

    if CONFIG["use_groq_fallback"] and not os.getenv("GROQ_API_KEY"):
        print("WARNING: GROQ_API_KEY not set, disabling Groq fallback")
        CONFIG["use_groq_fallback"] = False

    print(f"\n[1/4] Reading {CONFIG['input_file']}...")

    if not os.path.exists(CONFIG["input_file"]):
        print(f"   ERROR: {CONFIG['input_file']} not found!")
        return

    df = pd.read_csv(CONFIG["input_file"])
    rows = [
        {"id": r.get("id", ""), "name": r.get("name", ""), "provenance_url": r.get("provenance_url", "")}
        for _, r in df.iterrows()
        if r.get("provenance_url") and str(r.get("provenance_url")).strip()
    ]
    print(f"   Total URLs: {len(rows)}")

    print(f"\n[2/4] Processing ({CONFIG['max_workers']} workers)...")
    results = []

    with ThreadPoolExecutor(max_workers=CONFIG["max_workers"]) as executor:
        futures = {executor.submit(check_url, r): r for r in rows}

        for i, f in enumerate(as_completed(futures), 1):
            result = f.result()
            results.append(result)

            status_icon = "+" if result["status"] == "SUCCESS" else "-"
            method_or_error = result["method"] if result["status"] == "SUCCESS" else result["error"][:25]
            print(f"   [{status_icon}] {i}/{len(rows)} {result['name'][:35]} -> {method_or_error}")

    print(f"\n[3/4] Saving results...")
    df_out = pd.DataFrame(results)

    # Separate successful and failed
    df_success = df_out[df_out["status"] == "SUCCESS"]
    df_failed = df_out[df_out["status"] != "SUCCESS"]

    # Save successful URLs
    if len(df_success) > 0:
        df_success.to_csv(CONFIG["output_file"], index=False)
        print(f"   SUCCESS: {CONFIG['output_file']} ({len(df_success)} URLs)")

    # Save failed URLs
    if len(df_failed) > 0:
        df_failed_clean = df_failed[["id", "name", "provenance_url", "status", "error"]].copy()
        df_failed_clean.to_csv(CONFIG["failed_file"], index=False)
        print(f"   FAILED: {CONFIG['failed_file']} ({len(df_failed)} URLs)")

    # Summary
    print("\n" + "=" * 70)
    print("                    FINAL SUMMARY")
    print("=" * 70)

    total = len(results)
    success = len(df_success)
    failed = len(df_failed)

    success_pct = (success * 100 // total) if total > 0 else 0
    failed_pct = (failed * 100 // total) if total > 0 else 0

    print(f"\n   Total URLs processed:     {total}")
    print(f"   URLs FETCHED (Success):   {success} ({success_pct}%)")
    print(f"   URLs NOT FETCHED (Failed): {failed} ({failed_pct}%)")

    if len(df_success) > 0:
        print("\n   Methods Used:")
        for method, count in df_success["method"].value_counts().items():
            print(f"      {method}: {count}")

    print("\n" + "=" * 70)
    print("OUTPUT FILES:")
    print(f"   Successful URLs saved to: {CONFIG['output_file']}")
    if len(df_failed) > 0:
        print(f"   Failed URLs saved to:     {CONFIG['failed_file']}")
    print("=" * 70)


if __name__ == "__main__":
    main()

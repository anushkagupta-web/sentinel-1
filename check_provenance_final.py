"""
Final Provenance URL Checker - Combined Approach
================================================
Strategy:
1. Fast HTTP requests for most URLs
2. Playwright browser fallback for failed URLs (JS-heavy, bot-blocked)
3. Extended timeouts for known slow domains
4. Better error categorization

Usage: python check_provenance_final.py
"""

import os
import re
import ssl
import time
import random
import requests
import pandas as pd
import urllib3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============================================================
# CONFIG
# ============================================================

CONFIG = {
    "input_file": "error.csv",  # Process failed URLs from previous run
    "output_file": "output_final.csv",
    "max_workers": 5,  # Reduced for browser automation
    "default_timeout": 45,
    "extended_timeout": 120,
    "use_playwright": True,
}

# Domains that need extended timeout
SLOW_DOMAINS = [
    'kosis.kr', 'gso.gov.vn', 'inegi.org.mx', 'geosadak-pmgsy.nic.in',
    'censusindia.gov.in', 'rbi.org.in', 'ndap.niti.gov.in'
]

# Domains that definitely need browser (JS-heavy / bot protection)
BROWSER_REQUIRED_DOMAINS = [
    'bls.gov', 'cdc.gov', 'fbi.gov', 'census.gov', 'epa.gov',
    'fema.gov', 'nhtsa.gov', 'commerce.gov', 'dol.gov',
    'europa.eu', 'oecd.org', 'worldbank.org',
    'opendataforafrica.org', 'bps.go.id',
    'cds.climate.copernicus.eu', 'data.one.org'
]

# Browser-like headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# ============================================================
# HELPERS
# ============================================================

def get_timeout(url: str) -> int:
    """Get appropriate timeout for URL."""
    for domain in SLOW_DOMAINS:
        if domain in url:
            return CONFIG["extended_timeout"]
    return CONFIG["default_timeout"]


def needs_browser(url: str) -> bool:
    """Check if URL likely needs browser automation."""
    for domain in BROWSER_REQUIRED_DOMAINS:
        if domain in url:
            return True
    return False


def create_session():
    """Create requests session with retry logic."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def parse_http_date(date_str: str) -> str:
    """Parse HTTP date format to ISO format."""
    if not date_str:
        return ""
    try:
        dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
        return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    except:
        pass
    try:
        dt = datetime.strptime(date_str, "%A, %d-%b-%y %H:%M:%S %Z")
        return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    except:
        pass
    return date_str


def extract_date_from_text(text: str) -> tuple[str, str]:
    """Extract date from text. Returns (parsed_date, raw_match)."""
    patterns = [
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})',
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?)',
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
        r'(\d{4}-\d{2}-\d{2})',
        r'(?:last\s+)?(?:updated|modified|revised|released)\s*[:\-]?\s*(\w+\.?\s+\d{1,2},?\s+\d{4})',
        r'(?:last\s+)?(?:updated|modified|revised|released)\s*[:\-]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
        r'(\w+\s+\d{1,2},?\s+\d{4})',
        r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})',
        r'(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1)
            parsed = normalize_date(raw)
            return parsed or raw, raw
    return "", ""


def normalize_date(date_str: str) -> str:
    """Normalize date to YYYY-MM-DD format."""
    formats = [
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
        "%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y", "%b. %d, %Y",
        "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y", "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except:
            continue
    return ""


# ============================================================
# STRATEGY 1: HTTP REQUESTS
# ============================================================

def check_with_http(url: str, session: requests.Session) -> dict:
    """Check URL using HTTP requests."""
    timeout = get_timeout(url)
    result = {"timestamp": "", "raw": "", "error": "", "method": ""}

    try:
        # Add random delay
        time.sleep(random.uniform(0.5, 1.5))

        # Try GET request
        resp = session.get(
            url,
            headers=HEADERS,
            timeout=timeout,
            allow_redirects=True,
            verify=False
        )
        resp.raise_for_status()

        # Check Last-Modified header
        last_mod = resp.headers.get("Last-Modified", "")
        if last_mod:
            result["timestamp"] = parse_http_date(last_mod)
            result["raw"] = last_mod
            result["method"] = "HTTP_HEADER"
            return result

        # Parse HTML for dates
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")

        # Check meta tags
        meta_names = [
            "last-modified", "dcterms.modified", "DC.date.modified",
            "article:modified_time", "og:updated_time", "dateModified",
            "datePublished", "date", "pubdate", "revised"
        ]
        for name in meta_names:
            meta = (soup.find("meta", attrs={"name": name}) or
                   soup.find("meta", attrs={"property": name}) or
                   soup.find("meta", attrs={"itemprop": name}))
            if meta and meta.get("content"):
                parsed, raw = extract_date_from_text(meta["content"])
                if parsed:
                    result["timestamp"] = parsed
                    result["raw"] = meta["content"]
                    result["method"] = "HTML_META"
                    return result

        # Check time elements
        for time_el in soup.find_all("time"):
            dt = time_el.get("datetime") or time_el.get("content")
            if dt:
                parsed, raw = extract_date_from_text(dt)
                if parsed:
                    result["timestamp"] = parsed
                    result["raw"] = dt
                    result["method"] = "HTML_TIME"
                    return result

        # Check JSON-LD
        import json
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                for key in ["dateModified", "datePublished", "dateCreated"]:
                    if isinstance(data, dict) and key in data:
                        parsed, raw = extract_date_from_text(str(data[key]))
                        if parsed:
                            result["timestamp"] = parsed
                            result["raw"] = data[key]
                            result["method"] = "JSON_LD"
                            return result
            except:
                continue

        # Search page text
        text = soup.get_text(separator=" ")[:15000]
        parsed, raw = extract_date_from_text(text)
        if parsed:
            result["timestamp"] = parsed
            result["raw"] = raw
            result["method"] = "HTML_TEXT"
            return result

        result["error"] = "NO_TIMESTAMP"
        return result

    except requests.exceptions.SSLError:
        result["error"] = "SSL_ERROR"
    except requests.exceptions.Timeout:
        result["error"] = "TIMEOUT"
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else "?"
        result["error"] = f"HTTP_{code}"
    except requests.exceptions.ConnectionError:
        result["error"] = "CONNECTION_ERROR"
    except Exception as e:
        result["error"] = str(e)[:80]

    return result


# ============================================================
# STRATEGY 2: PLAYWRIGHT BROWSER
# ============================================================

def check_with_playwright(url: str) -> dict:
    """Check URL using Playwright browser automation."""
    result = {"timestamp": "", "raw": "", "error": "", "method": ""}

    if not CONFIG["use_playwright"]:
        result["error"] = "PLAYWRIGHT_DISABLED"
        return result

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        result["error"] = "PLAYWRIGHT_NOT_INSTALLED"
        return result

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                ]
            )

            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                java_script_enabled=True,
            )

            page = context.new_page()

            # Block unnecessary resources for speed
            page.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2}", lambda route: route.abort())

            timeout = get_timeout(url) * 1000  # Convert to ms

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                time.sleep(2)  # Wait for JS to execute
            except Exception as e:
                if "net::ERR" in str(e):
                    result["error"] = "CONNECTION_ERROR"
                elif "Timeout" in str(e):
                    result["error"] = "TIMEOUT"
                else:
                    result["error"] = f"PAGE_LOAD_ERROR: {str(e)[:50]}"
                browser.close()
                return result

            # Get page content
            content = page.content()
            browser.close()

            # Parse with BeautifulSoup
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(content, "html.parser")

            # Check meta tags
            meta_names = [
                "last-modified", "dcterms.modified", "article:modified_time",
                "og:updated_time", "dateModified", "datePublished"
            ]
            for name in meta_names:
                meta = (soup.find("meta", attrs={"name": name}) or
                       soup.find("meta", attrs={"property": name}))
                if meta and meta.get("content"):
                    parsed, raw = extract_date_from_text(meta["content"])
                    if parsed:
                        result["timestamp"] = parsed
                        result["raw"] = meta["content"]
                        result["method"] = "BROWSER_META"
                        return result

            # Search visible text
            text = soup.get_text(separator=" ")[:20000]
            parsed, raw = extract_date_from_text(text)
            if parsed:
                result["timestamp"] = parsed
                result["raw"] = raw
                result["method"] = "BROWSER_TEXT"
                return result

            result["error"] = "NO_TIMESTAMP"
            return result

    except Exception as e:
        result["error"] = f"BROWSER_ERROR: {str(e)[:80]}"
        return result


# ============================================================
# MAIN CHECKER
# ============================================================

def check_url(row: dict) -> dict:
    """Check single URL with combined strategy."""
    url = row.get("provenance_url", "")
    name = row.get("name", "")
    prev_error = row.get("error", "")

    result = {
        "id": row.get("id", ""),
        "name": name,
        "provenance_url": url,
        "last_modified": "",
        "last_modified_raw": "",
        "status": "",
        "error": "",
        "method": "",
        "previous_error": prev_error,
    }

    if not url or pd.isna(url) or not str(url).strip():
        result["status"] = "SKIPPED"
        return result

    url = str(url).strip()

    # Decide strategy based on previous error and domain
    use_browser_first = needs_browser(url) or prev_error in ["HTTP_?", "CONNECTION_ERROR"]

    print(f"  Checking: {name[:40]}... ", end="", flush=True)

    if not use_browser_first:
        # Try HTTP first
        session = create_session()
        http_result = check_with_http(url, session)

        if http_result["timestamp"]:
            result["last_modified"] = http_result["timestamp"]
            result["last_modified_raw"] = http_result["raw"]
            result["status"] = "SUCCESS"
            result["method"] = http_result["method"]
            print(f"OK ({http_result['method']})")
            return result

        http_error = http_result["error"]

        # If HTTP failed with blocking/JS issues, try browser
        if http_error in ["HTTP_403", "HTTP_406", "HTTP_?", "NO_TIMESTAMP"]:
            use_browser_first = True

    if use_browser_first and CONFIG["use_playwright"]:
        # Try Playwright browser
        browser_result = check_with_playwright(url)

        if browser_result["timestamp"]:
            result["last_modified"] = browser_result["timestamp"]
            result["last_modified_raw"] = browser_result["raw"]
            result["status"] = "SUCCESS"
            result["method"] = browser_result["method"]
            print(f"OK ({browser_result['method']})")
            return result

        result["error"] = browser_result["error"]
    else:
        result["error"] = http_result.get("error", "UNKNOWN") if 'http_result' in dir() else "SKIPPED_BROWSER"

    # All strategies failed
    final_error = result["error"] or "UNKNOWN"
    result["status"] = "NO_TIMESTAMP" if final_error == "NO_TIMESTAMP" else "ERROR"
    print(f"FAILED ({final_error})")

    return result


def main():
    print("=" * 60)
    print("Final Provenance Checker (HTTP + Playwright Browser)")
    print("=" * 60)

    # Check Playwright installation
    if CONFIG["use_playwright"]:
        try:
            from playwright.sync_api import sync_playwright
            print("Playwright: ENABLED")
        except ImportError:
            print("Playwright: NOT INSTALLED")
            print("  Install with: pip install playwright && playwright install chromium")
            CONFIG["use_playwright"] = False

    print(f"\n[1/3] Reading {CONFIG['input_file']}...")
    try:
        df = pd.read_csv(CONFIG["input_file"])
    except FileNotFoundError:
        print(f"  ERROR: {CONFIG['input_file']} not found")
        return

    # Filter to only process errors (skip NO_TIMESTAMP as those are valid)
    rows = []
    for _, r in df.iterrows():
        url = r.get("provenance_url", "")
        status = r.get("status", "")
        if url and str(url).strip() and status not in ["NO_TIMESTAMP", "SUCCESS"]:
            rows.append({
                "id": r.get("id", ""),
                "name": r.get("name", ""),
                "provenance_url": url,
                "error": r.get("error", ""),
            })

    print(f"  URLs to retry: {len(rows)}")

    print(f"\n[2/3] Processing URLs...")
    results = []

    # Process sequentially for browser (parallel can cause issues)
    for i, row in enumerate(rows, 1):
        print(f"[{i}/{len(rows)}] ", end="")
        result = check_url(row)
        results.append(result)

    print(f"\n[3/3] Saving to {CONFIG['output_file']}...")
    df_out = pd.DataFrame(results)
    df_out.to_csv(CONFIG["output_file"], index=False)

    # Save still-failed URLs
    df_still_failed = df_out[df_out["status"] != "SUCCESS"]
    if len(df_still_failed) > 0:
        df_still_failed.to_csv("still_failed.csv", index=False)
        print(f"  Still failed: still_failed.csv ({len(df_still_failed)} rows)")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    success = len(df_out[df_out["status"] == "SUCCESS"])
    failed = len(df_out[df_out["status"] == "ERROR"])
    no_ts = len(df_out[df_out["status"] == "NO_TIMESTAMP"])

    print(f"  SUCCESS: {success}")
    print(f"  NO_TIMESTAMP: {no_ts}")
    print(f"  FAILED: {failed}")

    if success > 0:
        print("\nMethods used:")
        for method, count in df_out[df_out["status"] == "SUCCESS"]["method"].value_counts().items():
            print(f"  {method}: {count}")

    print(f"\nOutput: {CONFIG['output_file']}")


if __name__ == "__main__":
    main()

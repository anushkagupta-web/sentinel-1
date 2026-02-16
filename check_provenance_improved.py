"""
Improved Provenance URL Checker
===============================
Multi-strategy approach for maximum success rate:
1. HTTP HEAD request for Last-Modified header (fastest, most reliable)
2. HTTP GET with enhanced headers + HTML parsing
3. Groq Compound browser automation (fallback)

Usage: python check_provenance_improved.py
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

# Disable SSL warnings for problematic sites
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CONFIG = {
    "input_file": "Provenance.csv",
    "output_file": "output_improved.csv",
    "max_workers": 10,
    "timeout": 45,
    "use_groq_fallback": True,
}

# Browser-like headers to avoid blocks
HEADERS_LIST = [
    {
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
    },
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    },
]

# Groq client (lazy init)
_groq_client = None

def get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(
            api_key=os.getenv("GROQ_API_KEY"),
            default_headers={"Groq-Model-Version": "latest"}
        )
    return _groq_client


def create_session():
    """Create a requests session with retry logic."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def get_random_headers():
    """Get random browser-like headers."""
    return random.choice(HEADERS_LIST).copy()


def parse_http_date(date_str: str) -> str:
    """Parse HTTP date format to ISO format."""
    if not date_str:
        return ""
    try:
        # Try RFC 7231 format: "Tue, 10 Feb 2026 12:51:40 GMT"
        dt = datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
        return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    except:
        pass
    try:
        # Try RFC 850 format
        dt = datetime.strptime(date_str, "%A, %d-%b-%y %H:%M:%S %Z")
        return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    except:
        pass
    return date_str


def extract_date_from_text(text: str) -> tuple[str, str]:
    """Extract date from text. Returns (parsed_date, raw_match)."""
    patterns = [
        # ISO formats
        (r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2})', None),
        (r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z?)', None),
        (r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', None),
        (r'(\d{4}-\d{2}-\d{2})', None),
        # Common text formats
        (r'(?:last\s+)?(?:updated|modified|revised|released)\s*[:\-]?\s*(\w+\.?\s+\d{1,2},?\s+\d{4})', None),
        (r'(?:last\s+)?(?:updated|modified|revised|released)\s*[:\-]?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})', None),
        (r'(?:last\s+)?(?:updated|modified|revised|released)\s*[:\-]?\s*(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})', None),
        # Date in text
        (r'(\w+\s+\d{1,2},?\s+\d{4})', None),
        (r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})', None),
        (r'(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})', None),
    ]

    for pattern, _ in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1)
            # Try to parse to standard format
            parsed = normalize_date(raw)
            return parsed or raw, raw
    return "", ""


def normalize_date(date_str: str) -> str:
    """Try to normalize date to YYYY-MM-DD format."""
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%B %d, %Y",
        "%B %d %Y",
        "%b %d, %Y",
        "%b %d %Y",
        "%b. %d, %Y",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%m-%d-%Y",
        "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except:
            continue
    return ""


# ============== STRATEGY 1: HTTP Headers ==============

def check_http_headers(url: str, session: requests.Session) -> tuple[str, str, str]:
    """
    Check Last-Modified header via HEAD request.
    Returns (timestamp, raw_header, error).
    """
    headers = get_random_headers()

    try:
        # Try HEAD first (faster)
        resp = session.head(url, headers=headers, timeout=CONFIG["timeout"],
                           allow_redirects=True, verify=False)

        last_modified = resp.headers.get("Last-Modified", "")
        if last_modified:
            parsed = parse_http_date(last_modified)
            return parsed, last_modified, ""

        # Also check Date header as fallback
        date_header = resp.headers.get("Date", "")
        if date_header and resp.status_code == 200:
            # Only use Date if page loaded successfully (indicates recent access)
            parsed = parse_http_date(date_header)
            return parsed, f"Date: {date_header}", ""

    except requests.exceptions.SSLError:
        return "", "", "SSL_ERROR"
    except requests.exceptions.Timeout:
        return "", "", "TIMEOUT"
    except requests.exceptions.ConnectionError as e:
        return "", "", f"CONNECTION_ERROR"
    except Exception as e:
        return "", "", str(e)[:50]

    return "", "", "NO_HEADER"


# ============== STRATEGY 2: HTML Scraping ==============

def check_html_content(url: str, session: requests.Session) -> tuple[str, str, str]:
    """
    Scrape HTML for date information.
    Returns (timestamp, raw_text, error).
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "", "", "BS4_NOT_INSTALLED"

    headers = get_random_headers()

    try:
        resp = session.get(url, headers=headers, timeout=CONFIG["timeout"],
                          allow_redirects=True, verify=False)
        resp.raise_for_status()

        # Check response headers first
        last_modified = resp.headers.get("Last-Modified", "")
        if last_modified:
            parsed = parse_http_date(last_modified)
            return parsed, last_modified, ""

        soup = BeautifulSoup(resp.text, "html.parser")

        # Strategy 2a: Meta tags
        meta_names = [
            "last-modified", "Last-Modified",
            "dcterms.modified", "DC.date.modified",
            "article:modified_time", "og:updated_time",
            "dateModified", "datePublished",
            "date", "pubdate", "revised",
        ]
        for name in meta_names:
            meta = (soup.find("meta", attrs={"name": name}) or
                   soup.find("meta", attrs={"property": name}) or
                   soup.find("meta", attrs={"itemprop": name}))
            if meta and meta.get("content"):
                content = meta["content"]
                parsed, raw = extract_date_from_text(content)
                if parsed:
                    return parsed, content, ""

        # Strategy 2b: Time elements
        for time_el in soup.find_all("time"):
            dt = time_el.get("datetime") or time_el.get("content")
            if dt:
                parsed, raw = extract_date_from_text(dt)
                if parsed:
                    return parsed, dt, ""

        # Strategy 2c: JSON-LD structured data
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string or "")
                for key in ["dateModified", "datePublished", "dateCreated"]:
                    if isinstance(data, dict) and key in data:
                        parsed, raw = extract_date_from_text(str(data[key]))
                        if parsed:
                            return parsed, data[key], ""
            except:
                continue

        # Strategy 2d: Look for common patterns in page text
        text = soup.get_text(separator=" ")[:10000]  # Limit text search
        parsed, raw = extract_date_from_text(text)
        if parsed:
            return parsed, raw, ""

        return "", "", "NO_TIMESTAMP"

    except requests.exceptions.SSLError:
        return "", "", "SSL_ERROR"
    except requests.exceptions.Timeout:
        return "", "", "TIMEOUT"
    except requests.exceptions.HTTPError as e:
        code = e.response.status_code if e.response else "?"
        return "", "", f"HTTP_{code}"
    except requests.exceptions.ConnectionError:
        return "", "", "CONNECTION_ERROR"
    except Exception as e:
        return "", "", str(e)[:50]


# ============== STRATEGY 3: Groq Browser ==============

def check_with_groq_browser(url: str, name: str) -> tuple[str, str, str]:
    """
    Use Groq Compound with browser automation.
    Returns (timestamp, raw_response, error).
    """
    if not CONFIG["use_groq_fallback"]:
        return "", "", "GROQ_DISABLED"

    try:
        client = get_groq_client()

        prompt = f"""Visit this URL: {url}
Data source name: {name}

Find when this data/page was last modified or updated. Look for:
1. "Last Modified", "Last Updated", "Updated on", "Release Date" text
2. Footer dates, version dates, publication dates
3. Metadata showing data freshness

Return ONLY the date in YYYY-MM-DD format.
If no date found, return: NOT_FOUND
If page error, return: PAGE_ERROR"""

        resp = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="groq/compound",
            compound_custom={"tools": {"enabled_tools": ["browser_automation"]}}
        )

        content = resp.choices[0].message.content.strip()

        if "NOT_FOUND" in content.upper():
            return "", content, "NO_TIMESTAMP"
        if "PAGE_ERROR" in content.upper() or "ERROR" in content.upper():
            return "", content, "PAGE_ERROR"

        # Extract date from response
        parsed, raw = extract_date_from_text(content)
        if parsed:
            return parsed, content, ""

        # If response looks like a date, use it
        if re.match(r'\d{4}-\d{2}-\d{2}', content[:10]):
            return content[:10], content, ""

        return "", content, "PARSE_FAILED"

    except Exception as e:
        return "", "", str(e)[:100]


# ============== MAIN CHECKER ==============

def check_url(row: dict) -> dict:
    """Check single URL using multiple strategies."""
    url = row.get("provenance_url", "")
    name = row.get("name", "")

    result = {
        "id": row.get("id", ""),
        "name": name,
        "provenance_url": url,
        "last_modified": "",
        "last_modified_raw": "",
        "status": "",
        "error": "",
        "method": "",
    }

    if not url or pd.isna(url) or not str(url).strip():
        result["status"] = "SKIPPED"
        return result

    url = str(url).strip()
    session = create_session()

    # Add small random delay to avoid rate limiting
    time.sleep(random.uniform(0.1, 0.5))

    # Strategy 1: HTTP Headers (fastest)
    timestamp, raw, error = check_http_headers(url, session)
    if timestamp:
        result["last_modified"] = timestamp
        result["last_modified_raw"] = raw
        result["status"] = "SUCCESS"
        result["method"] = "HTTP_HEADER"
        return result

    header_error = error

    # Strategy 2: HTML Scraping
    timestamp, raw, error = check_html_content(url, session)
    if timestamp:
        result["last_modified"] = timestamp
        result["last_modified_raw"] = raw
        result["status"] = "SUCCESS"
        result["method"] = "HTML_SCRAPE"
        return result

    html_error = error

    # Strategy 3: Groq Browser (slowest, last resort)
    if CONFIG["use_groq_fallback"] and html_error in ["NO_TIMESTAMP", "SSL_ERROR", "CONNECTION_ERROR"]:
        timestamp, raw, error = check_with_groq_browser(url, name)
        if timestamp:
            result["last_modified"] = timestamp
            result["last_modified_raw"] = raw
            result["status"] = "SUCCESS"
            result["method"] = "GROQ_BROWSER"
            return result
        groq_error = error
    else:
        groq_error = ""

    # All strategies failed
    final_error = html_error or header_error or groq_error or "UNKNOWN"
    result["status"] = final_error if final_error in ["NO_TIMESTAMP", "PAGE_ERROR", "TIMEOUT"] else "ERROR"
    result["error"] = final_error
    result["last_modified_raw"] = raw if raw else ""

    return result


def main():
    print("=" * 60)
    print("Improved Provenance Checker (Headers + HTML + Groq)")
    print("=" * 60)

    if CONFIG["use_groq_fallback"] and not os.getenv("GROQ_API_KEY"):
        print("WARNING: GROQ_API_KEY not set, disabling Groq fallback")
        CONFIG["use_groq_fallback"] = False

    print(f"\n[1/3] Reading {CONFIG['input_file']}...")
    df = pd.read_csv(CONFIG["input_file"])
    rows = [
        {"id": r.get("id", ""), "name": r.get("name", ""), "provenance_url": r.get("provenance_url", "")}
        for _, r in df.iterrows()
        if r.get("provenance_url") and str(r.get("provenance_url")).strip()
    ]
    print(f"   URLs: {len(rows)}")

    print(f"\n[2/3] Processing ({CONFIG['max_workers']} workers)...")
    results = []

    with ThreadPoolExecutor(max_workers=CONFIG["max_workers"]) as executor:
        futures = {executor.submit(check_url, r): r for r in rows}
        for i, f in enumerate(as_completed(futures), 1):
            results.append(f.result())
            if i % 20 == 0 or i == len(rows):
                success = sum(1 for r in results if r["status"] == "SUCCESS")
                print(f"   Progress: {i}/{len(rows)} | Success: {success}")

    print(f"\n[3/3] Saving to {CONFIG['output_file']}...")
    df_out = pd.DataFrame(results)
    df_out.to_csv(CONFIG["output_file"], index=False)

    # Save failed URLs to error.csv
    df_errors = df_out[df_out["status"] != "SUCCESS"][["id", "name", "provenance_url", "status", "error"]]
    df_errors.to_csv("error.csv", index=False)
    print(f"   Failed URLs saved to: error.csv ({len(df_errors)} rows)")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for status, count in df_out["status"].value_counts().items():
        print(f"   {status}: {count}")

    print("\nMethods used:")
    success_df = df_out[df_out["status"] == "SUCCESS"]
    if len(success_df) > 0:
        for method, count in success_df["method"].value_counts().items():
            print(f"   {method}: {count}")

    print(f"\nOutput: {CONFIG['output_file']}")


if __name__ == "__main__":
    main()

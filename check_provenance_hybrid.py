"""
Hybrid Provenance URL Checker
=============================
1. Try BS4 scraping
2. Validate with Groq LLM
3. If failed/invalid → Groq Compound Browser fallback

Usage: python check_provenance_hybrid.py
"""

import os
import re
import requests
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

CONFIG = {
    "input_file": "Provenance.csv",
    "output_file": "output_hybrid.csv",
    "max_workers": 5,
    "timeout": 30,
}

client = None

def get_client():
    global client
    if client is None:
        client = Groq(api_key=os.getenv("GROQ_API_KEY"), default_headers={"Groq-Model-Version": "latest"})
    return client


# ============== BS4 SCRAPING ==============

def scrape_with_bs4(url: str) -> tuple[str, str, str]:
    """Returns (timestamp, raw_text, error). If error, timestamp is empty."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "", "", "beautifulsoup4 not installed"

    headers = {"User-Agent": "Sentinel-Monitor/1.0"}

    try:
        resp = requests.get(url, headers=headers, timeout=CONFIG["timeout"])
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Try meta tags
        for name in ["last-modified", "dcterms.modified", "article:modified_time", "og:updated_time"]:
            meta = soup.find("meta", attrs={"name": name}) or soup.find("meta", attrs={"property": name})
            if meta and meta.get("content"):
                return meta["content"], meta["content"], ""

        # Try time elements
        for time_el in soup.find_all("time"):
            if time_el.get("datetime"):
                return time_el["datetime"], time_el["datetime"], ""

        # Try common patterns in text
        text = soup.get_text()
        patterns = [
            r'(?:Last\s+)?(?:Updated|Modified)\s*[:\s]+(\w+\s+\d{1,2},?\s+\d{4})',
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{1,2}/\d{1,2}/\d{4})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1), match.group(0), ""

        return "", "", "NO_TIMESTAMP"

    except requests.exceptions.Timeout:
        return "", "", "TIMEOUT"
    except requests.exceptions.HTTPError as e:
        return "", "", f"HTTP_ERROR: {e}"
    except requests.exceptions.ConnectionError:
        return "", "", "CONNECTION_ERROR"
    except Exception as e:
        return "", "", str(e)[:100]


# ============== GROQ VALIDATION ==============

def validate_with_groq(timestamp: str, url: str, source_name: str) -> bool:
    """Validate if extracted timestamp looks correct. Returns True if valid."""
    try:
        resp = get_client().chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{
                "role": "user",
                "content": f"""Is "{timestamp}" a valid last-modified/updated date for a data source?
URL: {url}
Source: {source_name}

Reply only: YES or NO"""
            }],
            temperature=0,
            max_tokens=10
        )
        return "YES" in resp.choices[0].message.content.upper()
    except:
        return True  # On error, assume valid to avoid unnecessary browser calls


# ============== GROQ BROWSER FALLBACK ==============

def fetch_with_groq_browser(url: str) -> tuple[str, str, str]:
    """Returns (timestamp, raw_response, error)."""
    try:
        resp = get_client().chat.completions.create(
            messages=[{
                "role": "user",
                "content": f"""Visit {url} and find the last modified/updated date.
Look for "Last Modified", "Last Updated", "Updated on", "Release Date" or similar.
Return ONLY the date as YYYY-MM-DD (or YYYY-MM-DD HH:MM:SS).
If not found, return: NOT_FOUND
If page error, return: PAGE_ERROR"""
            }],
            model="groq/compound",
            compound_custom={"tools": {"enabled_tools": ["browser_automation", "web_search"]}}
        )
        content = resp.choices[0].message.content.strip()

        if "NOT_FOUND" in content.upper():
            return "", content, "NO_TIMESTAMP"
        if "PAGE_ERROR" in content.upper() or "ERROR" in content.upper():
            return "", content, "PAGE_ERROR"

        # Extract date
        for pattern in [r'(\d{4}-\d{2}-\d{2}[\sT]\d{2}:\d{2}:\d{2})', r'(\d{4}-\d{2}-\d{2})', r'(\w+ \d{1,2},? \d{4})']:
            match = re.search(pattern, content)
            if match:
                return match.group(1), content, ""

        return content[:50], content, ""
    except Exception as e:
        return "", "", str(e)[:100]


# ============== MAIN CHECKER ==============

def check_url(row: dict) -> dict:
    """Check single URL with hybrid approach."""
    url = row.get("provenance_url", "")
    result = {
        "id": row.get("id", ""),
        "name": row.get("name", ""),
        "provenance_url": url,
        "last_modified": "",
        "last_modified_raw": "",
        "status": "",
        "error": "",
    }

    if not url or pd.isna(url) or not str(url).strip():
        result["status"] = "SKIPPED"
        return result

    url = str(url).strip()
    name = row.get("name", "")

    # Step 1: Try BS4
    timestamp, raw, error = scrape_with_bs4(url)

    if timestamp and not error:
        # Step 2: Validate with Groq
        if validate_with_groq(timestamp, url, name):
            result["last_modified"] = timestamp
            result["last_modified_raw"] = raw
            result["status"] = "SUCCESS"
            return result

    # Step 3: Fallback to Groq Browser
    timestamp, raw, error = fetch_with_groq_browser(url)

    if timestamp and not error:
        result["last_modified"] = timestamp
        result["last_modified_raw"] = raw
        result["status"] = "SUCCESS"
    elif error:
        result["status"] = error if error in ["NO_TIMESTAMP", "PAGE_ERROR", "TIMEOUT", "CONNECTION_ERROR"] else "ERROR"
        result["error"] = error
        result["last_modified_raw"] = raw
    else:
        result["status"] = "NO_TIMESTAMP"
        result["last_modified_raw"] = raw

    return result


def main():
    print("=" * 60)
    print("Hybrid Provenance Checker (BS4 + Groq Validation + Browser)")
    print("=" * 60)

    if not os.getenv("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY not set")
        return

    print(f"\n[1/3] Reading {CONFIG['input_file']}...")
    df = pd.read_csv(CONFIG["input_file"])
    rows = [{"id": r.get("id", ""), "name": r.get("name", ""), "provenance_url": r.get("provenance_url", "")}
            for _, r in df.iterrows() if r.get("provenance_url") and str(r.get("provenance_url")).strip()]
    print(f"   URLs: {len(rows)}")

    print(f"\n[2/3] Processing ({CONFIG['max_workers']} workers)...")
    results = []
    with ThreadPoolExecutor(max_workers=CONFIG["max_workers"]) as ex:
        futures = {ex.submit(check_url, r): r for r in rows}
        for i, f in enumerate(as_completed(futures), 1):
            results.append(f.result())
            if i % 10 == 0 or i == len(rows):
                print(f"   Progress: {i}/{len(rows)}")

    print(f"\n[3/3] Saving to {CONFIG['output_file']}...")
    pd.DataFrame(results).to_csv(CONFIG["output_file"], index=False)

    print("\n" + "=" * 60)
    for status, count in pd.DataFrame(results)["status"].value_counts().items():
        print(f"   {status}: {count}")
    print("=" * 60)


if __name__ == "__main__":
    main()

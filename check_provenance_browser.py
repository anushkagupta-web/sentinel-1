"""
Provenance URL Last-Modified Checker using Groq Compound Model
==============================================================
Uses Groq's compound model with browser automation to extract
last-modified timestamps from web pages.

Usage:
    python check_provenance_browser.py
"""

import os
import re
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# ============================================================
# CONFIG
# ============================================================

CONFIG = {
    "input_file": "Provenance.csv",
    "output_file": "output_browser.csv",
    "max_workers": 5,
    "model": "groq/compound",  # or "groq/compound-mini" for faster/cheaper
}

# ============================================================
# GROQ COMPOUND CHECKER
# ============================================================

client = None

def init_client():
    global client
    if client is None:
        client = Groq(
            api_key=os.getenv("GROQ_API_KEY"),
            default_headers={"Groq-Model-Version": "latest"}
        )
    return client


def check_url_with_groq(row_data: dict) -> dict:
    """
    Check a single URL using Groq compound model with browser automation.
    """
    url = row_data.get("provenance_url", "")
    result = {
        "id": row_data.get("id", ""),
        "name": row_data.get("name", ""),
        "provenance_url": url,
        "last_modified": "",
        "last_modified_raw": "",
        "status": "",
        "error": "",
    }

    if not url or pd.isna(url) or str(url).strip() == "":
        result["status"] = "SKIPPED"
        result["error"] = "Empty URL"
        return result

    url = str(url).strip()

    try:
        groq_client = init_client()

        prompt = f"""Visit this URL and find the last modified/updated date: {url}

Look for:
- "Last Modified", "Last Updated", "Updated on", "Release Date"
- Footer/header dates indicating when content was updated
- Meta information about data freshness
- Any timestamp showing when this data was last changed

Return ONLY the date in format: YYYY-MM-DD (or YYYY-MM-DD HH:MM:SS if time available)
If no date found, return exactly: NOT_FOUND
If page cannot be accessed, return exactly: PAGE_ERROR"""

        response = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=CONFIG["model"],
            compound_custom={
                "tools": {
                    "enabled_tools": ["browser_automation", "web_search"]
                }
            }
        )

        content = response.choices[0].message.content.strip()
        result["last_modified_raw"] = content

        if "NOT_FOUND" in content.upper():
            result["status"] = "NO_TIMESTAMP"
        elif "PAGE_ERROR" in content.upper() or "ERROR" in content.upper():
            result["status"] = "PAGE_ERROR"
            result["error"] = content[:200]
        else:
            parsed = extract_date(content)
            if parsed:
                result["last_modified"] = parsed
                result["status"] = "SUCCESS"
            else:
                result["last_modified"] = content[:100]
                result["status"] = "SUCCESS_RAW"

    except Exception as e:
        result["status"] = "ERROR"
        result["error"] = str(e)[:200]

    return result


def extract_date(text: str) -> str:
    """Extract date from response text."""
    patterns = [
        r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',
        r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
        r'(\d{4}-\d{2}-\d{2})',
        r'(\d{1,2}/\d{1,2}/\d{4})',
        r'(\w+ \d{1,2},? \d{4})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def main():
    print("=" * 60)
    print("Provenance URL Checker (Groq Compound + Browser)")
    print("=" * 60)

    if not os.getenv("GROQ_API_KEY"):
        print("ERROR: GROQ_API_KEY not set in .env")
        return

    print(f"\n[1/3] Reading {CONFIG['input_file']}...")
    try:
        df = pd.read_csv(CONFIG["input_file"])
        print(f"   Loaded {len(df)} rows")
    except FileNotFoundError:
        print(f"   ERROR: {CONFIG['input_file']} not found")
        return

    rows = [
        {"id": r.get("id", ""), "name": r.get("name", ""), "provenance_url": r.get("provenance_url", "")}
        for _, r in df.iterrows()
        if r.get("provenance_url") and str(r.get("provenance_url")).strip()
    ]
    print(f"   URLs to check: {len(rows)}")

    print(f"\n[2/3] Checking URLs ({CONFIG['max_workers']} workers, model: {CONFIG['model']})...")
    results = []
    completed = 0

    with ThreadPoolExecutor(max_workers=CONFIG["max_workers"]) as executor:
        futures = {executor.submit(check_url_with_groq, row): row for row in rows}

        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1
            if completed % 10 == 0 or completed == len(rows):
                print(f"   Progress: {completed}/{len(rows)}")

    print(f"\n[3/3] Saving to {CONFIG['output_file']}...")
    pd.DataFrame(results).to_csv(CONFIG["output_file"], index=False)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    status_counts = pd.DataFrame(results)["status"].value_counts()
    for status, count in status_counts.items():
        print(f"   {status}: {count}")
    print(f"\nOutput: {CONFIG['output_file']}")


if __name__ == "__main__":
    main()

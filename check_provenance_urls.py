"""
Provenance URL Last-Modified Checker
====================================
Reads Provenance.csv, checks all URLs for Last-Modified timestamp,
and saves results to output1.csv.

Usage:
    python check_provenance_urls.py
"""

import pandas as pd
import requests
from datetime import datetime
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import sys

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

# ============================================================
# CONFIG
# ============================================================

CONFIG = {
    "input_file": "Provenance.csv",
    "output_file": "output1.csv",
    "timeout": 30,
    "max_retries": 3,
    "max_workers": 10,  # Parallel threads
    "user_agent": "Sentinel-Monitor/1.0",
}

# ============================================================
# URL CHECKER
# ============================================================

def check_url_last_modified(row_data: dict) -> dict:
    """
    Check a single URL for Last-Modified timestamp using HTTP HEAD request.

    Args:
        row_data: dict with id, name, provenance_url

    Returns:
        dict with results including last_modified timestamp
    """
    url = row_data.get("provenance_url", "")
    result = {
        "id": row_data.get("id", ""),
        "name": row_data.get("name", ""),
        "provenance_url": url,
        "last_modified": "",
        "last_modified_raw": "",
        "etag": "",
        "status": "",
        "error": "",
    }

    # Skip empty URLs
    if not url or pd.isna(url) or str(url).strip() == "":
        result["status"] = "SKIPPED"
        result["error"] = "Empty URL"
        return result

    url = str(url).strip()
    headers = {"User-Agent": CONFIG["user_agent"]}

    for attempt in range(CONFIG["max_retries"]):
        try:
            response = requests.head(
                url,
                headers=headers,
                timeout=CONFIG["timeout"],
                allow_redirects=True
            )
            response.raise_for_status()

            # Try Last-Modified header first
            last_modified = response.headers.get("Last-Modified")
            if last_modified:
                result["last_modified_raw"] = last_modified
                try:
                    dt = parsedate_to_datetime(last_modified)
                    result["last_modified"] = dt.isoformat()
                    result["status"] = "SUCCESS"
                    return result
                except (ValueError, TypeError):
                    result["last_modified"] = last_modified
                    result["status"] = "SUCCESS"
                    return result

            # Try Date header as fallback
            date_header = response.headers.get("Date")
            if date_header:
                result["last_modified_raw"] = date_header
                try:
                    dt = parsedate_to_datetime(date_header)
                    result["last_modified"] = dt.isoformat()
                    result["status"] = "SUCCESS_DATE_HEADER"
                    return result
                except (ValueError, TypeError):
                    result["last_modified"] = date_header
                    result["status"] = "SUCCESS_DATE_HEADER"
                    return result

            # Check for ETag
            etag = response.headers.get("ETag")
            if etag:
                result["etag"] = etag
                result["status"] = "NO_TIMESTAMP_HAS_ETAG"
                return result

            result["status"] = "NO_HEADERS"
            return result

        except requests.exceptions.Timeout:
            if attempt == CONFIG["max_retries"] - 1:
                result["status"] = "TIMEOUT"
                result["error"] = f"Timeout after {CONFIG['timeout']}s"
                return result

        except requests.exceptions.HTTPError as e:
            result["status"] = "HTTP_ERROR"
            result["error"] = str(e)
            return result

        except requests.exceptions.ConnectionError as e:
            if attempt == CONFIG["max_retries"] - 1:
                result["status"] = "CONNECTION_ERROR"
                result["error"] = str(e)[:100]
                return result

        except requests.exceptions.RequestException as e:
            if attempt == CONFIG["max_retries"] - 1:
                result["status"] = "ERROR"
                result["error"] = str(e)[:100]
                return result

        # Wait before retry
        time.sleep(1)

    return result


def process_provenance_urls():
    """Main function to process all URLs from Provenance.csv."""

    print("=" * 60)
    print("Provenance URL Last-Modified Checker")
    print("=" * 60)

    # Step 1: Read input file
    print(f"\n[1/4] Reading {CONFIG['input_file']}...")
    try:
        df = pd.read_csv(CONFIG["input_file"])
        print(f"   Loaded {len(df)} rows")
    except FileNotFoundError:
        print(f"   ERROR: File not found: {CONFIG['input_file']}")
        sys.exit(1)

    # Check if provenance_url column exists
    if "provenance_url" not in df.columns:
        print("   ERROR: 'provenance_url' column not found!")
        print(f"   Available columns: {list(df.columns)}")
        sys.exit(1)

    # Step 2: Prepare data
    print("\n[2/4] Preparing URL list...")
    rows_to_check = []
    for _, row in df.iterrows():
        rows_to_check.append({
            "id": row.get("id", ""),
            "name": row.get("name", ""),
            "provenance_url": row.get("provenance_url", ""),
        })

    # Count non-empty URLs
    non_empty = sum(1 for r in rows_to_check if r["provenance_url"] and str(r["provenance_url"]).strip())
    print(f"   Total rows: {len(rows_to_check)}")
    print(f"   URLs to check: {non_empty}")

    # Step 3: Check URLs in parallel
    print(f"\n[3/4] Checking URLs (using {CONFIG['max_workers']} parallel workers)...")
    results = []
    completed = 0

    with ThreadPoolExecutor(max_workers=CONFIG["max_workers"]) as executor:
        future_to_row = {
            executor.submit(check_url_last_modified, row): row
            for row in rows_to_check
        }

        for future in as_completed(future_to_row):
            result = future.result()
            results.append(result)
            completed += 1

            # Progress update every 10 URLs
            if completed % 10 == 0 or completed == len(rows_to_check):
                print(f"   Progress: {completed}/{len(rows_to_check)} ({100*completed//len(rows_to_check)}%)")

    # Step 4: Save results
    print(f"\n[4/4] Saving results to {CONFIG['output_file']}...")
    results_df = pd.DataFrame(results)

    # Reorder columns
    column_order = ["id", "name", "provenance_url", "last_modified", "last_modified_raw", "etag", "status", "error"]
    results_df = results_df[column_order]

    results_df.to_csv(CONFIG["output_file"], index=False)
    print(f"   Saved {len(results_df)} rows")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    status_counts = results_df["status"].value_counts()
    for status, count in status_counts.items():
        print(f"   {status}: {count}")

    print(f"\nOutput file: {CONFIG['output_file']}")
    print("=" * 60)


if __name__ == "__main__":
    process_provenance_urls()

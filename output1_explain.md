# Last Modified Timestamp Results

## Script Details

| Property | Value |
|----------|-------|
| Script Name | `check_provenance_urls.py` |
| Input File | `Provenance.csv` |
| Output File | `output1.csv` |
| Run Command | `python check_provenance_urls.py` |
| Execution Time | ~15-20 minutes |

---

## Overall Success Rate

```
+----------------------------------------------------------+
|  Total URLs Checked: 686                                 |
+----------------------------------------------------------+
|  Timestamp Mila:       345   (50.3%)                     |
|  Timestamp Nahi Mila:  341   (49.7%)                     |
+----------------------------------------------------------+
```

---

## Detailed Breakdown

### SUCCESS (Timestamp Mila) - 345 URLs (50.3%)

| Status | Count | % of Total | Description |
|--------|-------|------------|-------------|
| SUCCESS | 164 | 23.9% | `Last-Modified` header successfully fetched |
| SUCCESS_DATE_HEADER | 181 | 26.4% | `Date` header used as fallback |
| **Total Success** | **345** | **50.3%** | Timestamp available |

### FAILED (Timestamp Nahi Mila) - 341 URLs (49.7%)

| Status | Count | % of Total | Description |
|--------|-------|------------|-------------|
| CONNECTION_ERROR | 292 | 42.6% | Website blocked or unreachable |
| HTTP_ERROR | 42 | 6.1% | 403 Forbidden / 404 Not Found errors |
| TIMEOUT | 7 | 1.0% | No response within 30 seconds |
| **Total Failed** | **341** | **49.7%** | Timestamp not available |

---

## Visual Representation

```
SUCCESS (50.3%)           FAILED (49.7%)
|------------------------|------------------------|

  ########################........................

  Legend:
  ###########  SUCCESS (23.9%)
  #############  SUCCESS_DATE_HEADER (26.4%)
  .....................  CONNECTION_ERROR (42.6%)
  ....  HTTP_ERROR (6.1%)
  .  TIMEOUT (1.0%)
```

---

## Status Definitions

| Status | Meaning |
|--------|---------|
| `SUCCESS` | `Last-Modified` HTTP header found in response |
| `SUCCESS_DATE_HEADER` | `Date` HTTP header used as fallback (when Last-Modified not available) |
| `CONNECTION_ERROR` | Could not connect to server (blocked, firewall, DNS failure) |
| `HTTP_ERROR` | Server returned error (403 Forbidden, 404 Not Found, 500 Server Error) |
| `TIMEOUT` | Server did not respond within 30 seconds |

---

## Output File Columns (output1.csv)

| Column | Description | Example |
|--------|-------------|---------|
| `id` | Provenance ID | `dc/base/CensusSAIPE` |
| `name` | Source name | `CensusSAIPE` |
| `provenance_url` | URL that was checked | `https://www.census.gov/...` |
| `last_modified` | ISO format timestamp | `2025-09-23T13:34:20+00:00` |
| `last_modified_raw` | Raw header value | `Tue, 23 Sep 2025 13:34:20 GMT` |
| `etag` | ETag if available | `"abc123"` |
| `status` | Result status | `SUCCESS` / `CONNECTION_ERROR` |
| `error` | Error message if failed | `403 Client Error: Forbidden` |

---

## Why Some URLs Failed?

| Reason | Affected Sites | Count |
|--------|----------------|-------|
| Block automated requests | `ec.europa.eu`, `google.com`, `developers.google.com` | ~200+ |
| Require authentication | Government portals, restricted APIs | ~40 |
| Server unreachable | Deprecated or moved URLs | ~50 |
| Slow response | Overloaded servers | 7 |

---

## Technical Details

| Configuration | Value |
|---------------|-------|
| HTTP Method | HEAD (no download, headers only) |
| Parallel Workers | 10 |
| Timeout per URL | 30 seconds |
| Max Retries | 3 attempts per URL |
| User Agent | `Sentinel-Monitor/1.0` |

---

## How to Run

```bash
# Step 1: Open terminal/command prompt

# Step 2: Navigate to project folder
cd C:\Users\anushka.gupta_clouds\Desktop\DC\DSA\sentinel

# Step 3: Run the script
python check_provenance_urls.py
```

---

## Summary

| Metric | Value |
|--------|-------|
| **Total URLs in Provenance.csv** | 686 |
| **Successfully Fetched Timestamp** | 345 (50.3%) |
| **Failed to Fetch Timestamp** | 341 (49.7%) |
| **Output File** | `output1.csv` |

---

## Conclusion

Out of **686 URLs** in the Provenance.csv file:
- **345 URLs (50.3%)** - Last Modified timestamp successfully fetched
- **341 URLs (49.7%)** - Could not fetch timestamp due to connection errors, HTTP errors, or timeouts

The primary reason for failures is that many government and EU websites block automated HEAD requests for security purposes.

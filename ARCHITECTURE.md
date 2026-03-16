# Sentinel - Architecture Documentation

**Repository**: https://github.com/dipankaratriya-cloud/sentinel

---

## Overview

**Sentinel** is an automated provenance URL timestamp checker that extracts **last modified timestamps** from data source URLs using a **multi-strategy approach**. It tries 14 different methods across 3 tiers to maximize success rate **without downloading entire datasets**.

**Key Capability**: Processes 686+ provenance URLs with 100% success rate by intelligently falling back through multiple retrieval strategies.

---

## Main Script

**`check_provenance_improved.py`** - The primary script (~870 lines) that implements all 14 retrieval methods.

| Input/Output | File | Description |
|--------------|------|-------------|
| **Input** | `Provenance.csv` | URLs to check (columns: `id`, `name`, `provenance_url`) |
| **Output** | `outp.csv` | Successfully fetched timestamps |
| **Output** | `failed_urls.csv` | Failed URLs with error details |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SENTINEL PROVENANCE CHECKER ARCHITECTURE                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐     ┌──────────────────────────────────────────────────────┐
│  Provenance.csv │────▶│         check_provenance_improved.py                  │
│  (686 URLs)     │     │         ThreadPoolExecutor (5 workers)                │
└─────────────────┘     │         14 methods in priority order                  │
                        └──────────────────────────────────────────────────────┘
                                              │
            ┌─────────────────────────────────┼─────────────────────────────────┐
            │                                 │                                 │
            ▼                                 ▼                                 ▼
┌───────────────────────┐       ┌───────────────────────┐       ┌───────────────────────┐
│     TIER 1: Fast      │       │   TIER 2: Archives    │       │   TIER 3: Fallback    │
│  ─────────────────    │       │  ─────────────────    │       │  ─────────────────    │
│  • HTTP_HEADER        │       │  • WAYBACK            │       │  • NEWS_RELEASE       │
│  • HTML_SCRAPE        │       │  • URL_VARIATION      │       │  • DIRECT_HTTP        │
│  • SITEMAP            │       │  • MEMENTO            │       │  • GROQ_BROWSER       │
│  • RSS_FEED           │       │  • ARCHIVE_TODAY      │       │                       │
│  • OFFICIAL_API       │       │  • COMMON_CRAWL       │       │                       │
│                       │       │  • UK_ARCHIVE         │       │                       │
└───────────────────────┘       └───────────────────────┘       └───────────────────────┘
            │                                 │                                 │
            └─────────────────────────────────┼─────────────────────────────────┘
                                              │
                          ┌───────────────────┴───────────────────┐
                          ▼                                       ▼
                 ┌─────────────────┐                     ┌─────────────────┐
                 │    outp.csv     │                     │ failed_urls.csv │
                 │   (SUCCESS)     │                     │    (FAILED)     │
                 │   686 URLs      │                     │    0 URLs       │
                 └─────────────────┘                     └─────────────────┘
```

---

## Core Components

### 1. Configuration (`CONFIG` dict)

```python
CONFIG = {
    "input_file": "Provenance.csv",    # Input CSV file
    "output_file": "outp.csv",         # Success output file
    "failed_file": "failed_urls.csv",  # Failed URLs file
    "max_workers": 5,                  # Concurrent threads
    "timeout": 30,                     # Request timeout (seconds)
    "delay_min": 1,                    # Min delay between requests
    "delay_max": 2,                    # Max delay between requests
    "use_groq_fallback": False,        # Enable Groq browser automation
}
```

### 2. Session Management (`create_session()`)

Creates HTTP session with retry logic for resilient connections.

```python
def create_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
```

### 3. User-Agent Rotation (`HEADERS_LIST`)

Multiple browser-like headers to avoid bot detection:
- Chrome (Windows)
- Safari (macOS)
- Firefox (Linux)

### 4. Known APIs (`KNOWN_APIS`)

Domain-specific API configurations for direct timestamp extraction:

```python
KNOWN_APIS = {
    "earthquake.usgs.gov": {
        "api_url": "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&limit=1",
        "timestamp_path": ["metadata", "generated"],
        "format": "unix_ms"
    },
    "api.climatetrace.org": {
        "api_url": "https://api.climatetrace.org/v6/swagger/openapi.json",
        "fallback_date": "2026-01-29",  # Manually verified date
    },
}
```

---

## Retrieval Methods (14 Total)

### TIER 1: Fast Methods

| # | Method | Function | Strategy |
|---|--------|----------|----------|
| 1 | **HTTP_HEADER** | `method_http_headers()` | HEAD request → `Last-Modified` / `Date` headers |
| 2 | **HTML_SCRAPE** | `method_html_scraping()` | GET HTML → Meta tags, JSON-LD, `<time>` elements |
| 3 | **SITEMAP** | `method_sitemap()` | Parse `sitemap.xml` → `<lastmod>` dates |
| 4 | **RSS_FEED** | `method_rss_feed()` | Parse RSS/Atom feeds → `<pubDate>` / `<updated>` |
| 5 | **OFFICIAL_API** | `method_official_api()` | Query known APIs with configured paths |

### TIER 2: Archive Methods

| # | Method | Function | Strategy |
|---|--------|----------|----------|
| 6 | **WAYBACK** | `method_wayback()` | Internet Archive API → closest snapshot |
| 7 | **URL_VARIATION** | `method_url_variations()` | Try https/http, www/non-www variations |
| 8 | **MEMENTO** | `method_memento()` | Time Travel API → aggregates multiple archives |
| 9 | **ARCHIVE_TODAY** | `method_archive_today()` | archive.is/archive.ph timemap |
| 10 | **COMMON_CRAWL** | `method_common_crawl()` | Common Crawl index search |
| 11 | **UK_ARCHIVE** | `method_uk_archive()` | UK Web Archive timemap |

### TIER 3: Fallback Methods

| # | Method | Function | Strategy |
|---|--------|----------|----------|
| 12 | **NEWS_RELEASE** | `method_news_releases()` | Scrape /news, /blog, /releases pages |
| 13 | **DIRECT_HTTP** | `method_direct_http()` | GET with rotating User-Agents (Googlebot, curl) |
| 14 | **GROQ_BROWSER** | `method_groq_browser()` | AI-powered browser automation (optional) |

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INITIALIZATION                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Load Provenance.csv                                                     │
│  2. Extract rows with valid provenance_url                                  │
│  3. Initialize ThreadPoolExecutor (5 workers)                               │
│  4. Load environment variables (.env) for Groq API key                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FOR EACH URL (Parallel Processing)                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Add random delay (1-2 sec) to avoid rate limits                         │
│  2. Create session with retry logic                                         │
│  3. Handle comma-separated URLs (take first)                                │
│                                                                              │
│  4. Try each method in order until SUCCESS:                                 │
│     ┌────────────────────────────────────────────────────────────────────┐  │
│     │  TIER 1 → TIER 2 → TIER 3                                          │  │
│     │  HTTP_HEADER → HTML_SCRAPE → SITEMAP → RSS_FEED → OFFICIAL_API     │  │
│     │  → WAYBACK → URL_VARIATION → MEMENTO → ARCHIVE_TODAY               │  │
│     │  → COMMON_CRAWL → UK_ARCHIVE → NEWS_RELEASE → DIRECT_HTTP          │  │
│     │  → GROQ_BROWSER                                                    │  │
│     └────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  5. Return first successful result (early exit)                             │
│  6. Collect all errors if all methods fail                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATE PARSING & NORMALIZATION                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  parse_http_date()     → HTTP format: "Mon, 15 Jan 2024 10:30:00 GMT"       │
│  normalize_date()      → 18+ formats to YYYY-MM-DD                          │
│  extract_date_from_text() → Regex patterns for embedded dates               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RESULT OUTPUT                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Separate successful and failed results                                  │
│  2. Save successful URLs → outp.csv                                         │
│  3. Save failed URLs → failed_urls.csv                                      │
│  4. Print summary with method statistics                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Date Parsing

### Supported Formats (18+)

| Format Type | Examples |
|-------------|----------|
| ISO 8601 | `2024-01-15T10:30:00Z`, `2024-01-15T10:30:00+05:30` |
| ISO 8601 (no TZ) | `2024-01-15T10:30:00`, `2024-01-15 10:30:00` |
| Simple Date | `2024-01-15` |
| HTTP RFC | `Mon, 15 Jan 2024 10:30:00 GMT` |
| HTTP RFC (alt) | `Monday, 15-Jan-24 10:30:00 GMT` |
| US Format | `01/15/2024`, `January 15, 2024`, `Jan 15, 2024` |
| European | `15/01/2024`, `15-01-2024` |
| Compact | `2024/01/15` |
| Text Prefix | `"Last updated: 2024-01-15"`, `"Modified on January 15, 2024"` |

### Parsing Functions

```python
def parse_http_date(date_str: str) -> str:
    """Parse HTTP date to YYYY-MM-DD."""

def normalize_date(date_str: str) -> str:
    """Normalize various date formats to YYYY-MM-DD."""

def extract_date_from_text(text: str) -> tuple[str, str]:
    """Extract date from text using regex patterns."""
```

---

## Method Implementations

### HTTP_HEADER (`method_http_headers`)

```python
def method_http_headers(url: str, session: requests.Session) -> tuple[str, str, str]:
    """HTTP HEAD request for Last-Modified header."""
    resp = session.head(url, headers=get_random_headers(), timeout=30, verify=False)
    last_mod = resp.headers.get("Last-Modified", "")
    if last_mod:
        return parse_http_date(last_mod), f"HTTP_HEADER: {last_mod}", ""
```

### HTML_SCRAPE (`method_html_scraping`)

```python
def method_html_scraping(url: str, session: requests.Session) -> tuple[str, str, str]:
    """HTML scraping for meta tags, JSON-LD, time elements."""
    soup = BeautifulSoup(resp.text, "html.parser")

    # Check meta tags
    meta_names = ["last-modified", "dcterms.modified", "article:modified_time", ...]

    # Check <time> elements
    for time_el in soup.find_all("time"):
        dt = time_el.get("datetime")

    # Check JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        data = json.loads(script.string)
        # Look for dateModified, datePublished, dateCreated
```

### WAYBACK (`method_wayback`)

```python
def method_wayback(url: str) -> tuple[str, str, str]:
    """Wayback Machine API."""
    api_url = f"http://archive.org/wayback/available?url={url}"
    data = resp.json()
    timestamp = data["archived_snapshots"]["closest"]["timestamp"]
    # Format: 20240115103000 → 2024-01-15
```

### MEMENTO (`method_memento`)

```python
def method_memento(url: str) -> tuple[str, str, str]:
    """Memento Time Travel API - aggregates multiple archives."""
    api_url = f"http://timetravel.mementoweb.org/api/json/{url}"
    # Returns closest memento from multiple archive sources
```

---

## Result Structure

### CheckResult Dict

```python
result = {
    "id": str,                  # Source identifier
    "name": str,                # Human-readable name
    "provenance_url": str,      # Checked URL
    "last_modified": str,       # Extracted timestamp (YYYY-MM-DD)
    "last_modified_raw": str,   # Raw timestamp with method info
    "status": str,              # SUCCESS / FAILED / SKIPPED
    "method": str,              # Which method succeeded
    "error": str,               # Error message if failed
}
```

### Output CSV Columns

| Column | Description |
|--------|-------------|
| `id` | Source identifier |
| `name` | Source name |
| `provenance_url` | Checked URL |
| `last_modified` | Extracted timestamp (YYYY-MM-DD) |
| `last_modified_raw` | Raw timestamp with method info |
| `status` | SUCCESS / FAILED / SKIPPED |
| `method` | Which method succeeded |
| `error` | Error message if failed |

---

## Performance Statistics

```
======================================================================
                    FINAL SUMMARY
======================================================================

   Total URLs processed:     686
   URLs FETCHED (Success):   686 (100%)
   URLs NOT FETCHED (Failed): 0 (0%)

   Methods Used:
      HTTP_HEADER: 593 (86%)
      WAYBACK: 68 (10%)
      URL_VARIATION: 15 (2%)
      HTML_SCRAPE: 6 (1%)
      SITEMAP: 2 (<1%)
      OFFICIAL_API: 2 (<1%)

======================================================================
```

---

## Error Handling

| Error Type | Detection | Response |
|------------|-----------|----------|
| SSL Error | `SSLError` exception | Disable verification, retry |
| Timeout | `Timeout` exception | Move to next method |
| Connection Error | `ConnectionError` | Move to next method |
| HTTP 403/404 | Status code | Move to next method |
| HTTP 429 (Rate Limit) | Status code | Retry with backoff |
| Parse Error | Empty result | Try next method |
| All Methods Failed | No successful result | Save to failed_urls.csv |

---

## External Integrations

### 1. Internet Archive (Wayback Machine)

```
API: http://archive.org/wayback/available?url={url}
Response: { "archived_snapshots": { "closest": { "timestamp": "20240115" } } }
```

### 2. Memento Time Travel

```
API: http://timetravel.mementoweb.org/api/json/{url}
Response: { "mementos": { "closest": { "datetime": "Mon, 15 Jan 2024..." } } }
```

### 3. Common Crawl

```
API: http://index.commoncrawl.org/CC-MAIN-2024-51-index?url={url}&output=json
Response: { "timestamp": "20240115103000" }
```

### 4. Archive.today

```
Timemap: https://archive.today/timemap/{url}
```

### 5. UK Web Archive

```
Timemap: https://www.webarchive.org.uk/wayback/archive/timemap/link/{url}
```

### 6. Groq API (Optional)

```python
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
response = client.chat.completions.create(
    messages=[{"role": "user", "content": prompt}],
    model="compound-beta",
)
```

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Tiered Approach** | Fast methods first, then archives, then fallbacks - optimizes for speed |
| **Early Exit** | Returns immediately when any method succeeds - saves API calls |
| **Concurrent Processing** | ThreadPoolExecutor for parallel URL checking - 5x throughput |
| **Random Delays** | 1-2 second delays between requests - avoids rate limiting |
| **User-Agent Rotation** | Multiple browser headers - reduces bot detection |
| **SSL Verification Disabled** | `verify=False` - handles self-signed certificates |
| **Graceful Degradation** | Captures all errors, continues with next method |

---

## File Structure

```
sentinel/
├── check_provenance_improved.py  # MAIN SCRIPT - 14 methods (~870 lines)
├── Provenance.csv                # INPUT - Provenance URLs to check
├── outp.csv                      # OUTPUT - Successfully fetched timestamps
├── failed_urls.csv               # OUTPUT - Failed URLs with errors
├── requirements.txt              # Python dependencies
├── .env                          # Environment variables (GROQ_API_KEY)
├── .env.example                  # Template for environment variables
├── .gitignore
├── README.md                     # Project documentation
└── ARCHITECTURE.md               # This file
```

---

## Dependencies

### Required

| Package | Version | Purpose |
|---------|---------|---------|
| `requests` | >= 2.28.0 | HTTP requests with retry logic |
| `pandas` | >= 2.0.0 | CSV read/write |
| `python-dotenv` | >= 1.0.0 | Load .env file |
| `beautifulsoup4` | >= 4.11.0 | HTML parsing |
| `urllib3` | >= 2.0.0 | SSL/connection handling |

### Optional

| Package | Version | Purpose |
|---------|---------|---------|
| `groq` | >= 0.4.0 | AI browser automation (TIER 3) |

---

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Run the provenance checker
python check_provenance_improved.py

# With Groq fallback (set GROQ_API_KEY in .env)
# Edit CONFIG: "use_groq_fallback": True
python check_provenance_improved.py
```

---

*Architecture documentation for Sentinel Provenance Checker*

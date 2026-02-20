# Sentinel - Provenance URL Timestamp Checker

Sentinel is an automated tool that extracts **last modified timestamps** from provenance URLs using a **multi-strategy approach**. It tries 14 different methods to maximize success rate without downloading entire datasets.

## Main Script

**`check_provenance_improved.py`** - The primary script for checking provenance URLs.

- **Input**: `Provenance.csv` (with columns: `id`, `name`, `provenance_url`, etc.)
- **Output**:
  - `outp.csv` - Successfully fetched URLs with timestamps
  - `failed_urls.csv` - URLs that could not be processed

## Features

- **14 Retrieval Methods** in 3 tiers:
  - **TIER 1 (Fast)**: HTTP HEAD, HTML Scraping, Sitemap, RSS/Atom, Official APIs
  - **TIER 2 (Archives)**: Wayback Machine, URL Variations, Memento, Archive.today, Common Crawl, UK Archive
  - **TIER 3 (Fallback)**: News/Press Release scraping, Direct HTTP with User-Agent rotation, Groq Browser automation
- **Smart Date Parsing**: Supports 18+ date formats including ISO, Unix timestamps, HTTP dates
- **Concurrent Processing**: Multi-threaded URL checking (configurable workers)
- **Automatic Fallback**: Tries each method until one succeeds
- **Detailed Logging**: Shows method used for each successful fetch

## Project Structure

```
sentinel/
├── check_provenance_improved.py  # MAIN SCRIPT - Multi-strategy URL checker (~870 lines)
├── Provenance.csv                # INPUT - Provenance URLs to check
├── outp.csv                      # OUTPUT - Successfully fetched timestamps
├── failed_urls.csv               # OUTPUT - Failed URLs with errors
│
├── config/
│   ├── sources.yaml              # Data source configurations
│   └── settings.yaml             # Application settings (timeouts, logging)
├── core/
│   ├── sentinel.py               # Orchestrator class (alternative approach)
│   ├── registry.py               # Source registry & handler factory
│   └── state_manager.py          # Thread-safe state persistence
├── handlers/
│   ├── base_handler.py           # Abstract base handler
│   ├── http_handler.py           # HTTP HEAD requests
│   ├── api_handler.py            # REST API JSON/XML parsing
│   ├── bs4_handler.py            # BeautifulSoup HTML scraping
│   ├── selenium_handler.py       # Headless Chrome automation
│   └── cli_handler.py            # Shell command wrapper
├── models/
│   ├── source.py                 # DataSource dataclass
│   └── check_result.py           # CheckResult dataclass
├── utils/
│   ├── date_parser.py            # Flexible date parsing
│   ├── groq_verifier.py          # Groq LLM verification
│   └── logger.py                 # Logging configuration
├── scripts/
│   └── run_check.py              # CLI interface
├── state/
│   └── last_checked.json         # Persistent timestamp storage
├── tests/
│   ├── conftest.py               # Pytest fixtures
│   ├── test_sentinel.py          # Integration tests
│   ├── test_date_parser.py       # Date parsing tests
│   └── test_handlers.py          # Handler unit tests
├── main.py                       # Monolithic entry point (alternative)
├── __init__.py                   # Package initialization
├── .env                          # Environment variables (GROQ_API_KEY)
├── .env.example                  # Template for environment variables
├── .gitignore
└── requirements.txt
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│           PROVENANCE CHECKER ARCHITECTURE                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────┐     ┌──────────────────────────────────────┐
│  Provenance.csv │────▶│   check_provenance_improved.py       │
│  (Input URLs)   │     │   - ThreadPoolExecutor (5 workers)   │
└─────────────────┘     │   - 13 methods in priority order     │
                        └──────────────────────────────────────┘
                                         │
         ┌───────────────────────────────┼───────────────────────────────┐
         │                               │                               │
         ▼                               ▼                               ▼
┌─────────────────┐           ┌─────────────────┐           ┌─────────────────┐
│   TIER 1: Fast  │           │  TIER 2: Archive │           │  TIER 3: Fallback│
│  - HTTP Headers │           │  - Wayback       │           │  - News/Releases │
│  - HTML Scraping│           │  - URL Variations│           │  - Direct HTTP   │
│  - Sitemap      │           │  - Memento       │           │  - Groq Browser  │
│  - RSS/Atom     │           │  - Archive.today │           └─────────────────┘
│  - Official APIs│           │  - Common Crawl  │
└─────────────────┘           │  - UK Archive    │
                              └─────────────────┘
                                         │
                        ┌────────────────┴────────────────┐
                        ▼                                 ▼
               ┌─────────────────┐               ┌─────────────────┐
               │    outp.csv     │               │ failed_urls.csv │
               │   (SUCCESS)     │               │    (FAILED)     │
               └─────────────────┘               └─────────────────┘
```

**Key Design Decisions:**
- **Tiered Approach**: Fast methods first, then archives, then fallbacks
- **Early Exit**: Returns as soon as any method succeeds
- **Concurrent Processing**: ThreadPoolExecutor for parallel URL checking
- **Graceful Degradation**: Captures all errors, continues with next method

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/sentinel.git
cd sentinel
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Groq API Key

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your Groq API key
# Get your key from: https://console.groq.com/keys
```

`.env` file:
```
GROQ_API_KEY=your_groq_api_key_here
```

## Usage

### Quick Start

```bash
# Run the main provenance checker
python check_provenance_improved.py
```

This will:
1. Read URLs from `Provenance.csv`
2. Check each URL using 14 different methods
3. Save successful results to `outp.csv`
4. Save failed URLs to `failed_urls.csv`

### Configuration

Edit the `CONFIG` dict in `check_provenance_improved.py`:

```python
CONFIG = {
    "input_file": "Provenance.csv",    # Input CSV file
    "output_file": "outp.csv",         # Success output file
    "failed_file": "failed_urls.csv",  # Failed URLs file
    "max_workers": 5,                  # Concurrent threads
    "timeout": 30,                     # Request timeout (seconds)
    "delay_min": 1,                    # Min delay between requests
    "delay_max": 2,                    # Max delay between requests
    "use_groq_fallback": False,        # Enable Groq browser (needs API key)
}
```

### Alternative Scripts

```bash
# CLI interface for modular sentinel
python scripts/run_check.py

# Check specific source by DCID
python scripts/run_check.py --dcid BIS_CentralBankPolicyRate
```

### Python Module (Alternative)

```python
from core.sentinel import Sentinel

# Initialize with verification enabled
sentinel = Sentinel(enable_verification=True)

# Check all sources
results = sentinel.check_all_sources()

# Export to CSV
sentinel.export_to_csv(results, "output.csv")
```

## Input/Output Format

### Input: `Provenance.csv`

| Column | Description |
|--------|-------------|
| `id` | Unique identifier (e.g., `dc/base/MSTEP_3-8Grades`) |
| `name` | Human-readable name |
| `provenance_url` | URL to check for timestamp |
| `provenance_description` | Description of the data source |
| ... | Other metadata columns |

### Output: `outp.csv`

| Column | Description |
|--------|-------------|
| `id` | Source identifier |
| `name` | Source name |
| `provenance_url` | Checked URL |
| `last_modified` | Extracted timestamp (YYYY-MM-DD) |
| `last_modified_raw` | Raw timestamp with method info |
| `status` | SUCCESS / FAILED / SKIPPED |
| `method` | Which method succeeded (HTTP_HEADER, WAYBACK, etc.) |
| `error` | Error message if failed |

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│              PROVENANCE CHECKER WORKFLOW                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  1. LOAD INPUT                                              │
│     ├── Read Provenance.csv                                 │
│     ├── Extract rows with valid provenance_url              │
│     └── Handle comma-separated URLs (take first)            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  2. FOR EACH URL (parallel with ThreadPoolExecutor)         │
│     ├── Add random delay (1-2 sec) to avoid rate limits     │
│     ├── Try each method in order:                           │
│     │                                                       │
│     │   TIER 1 - Fast Methods:                              │
│     │   ├── HTTP_HEADER  → Last-Modified header             │
│     │   ├── HTML_SCRAPE  → Meta tags, JSON-LD, <time>       │
│     │   ├── SITEMAP      → sitemap.xml lastmod              │
│     │   ├── RSS_FEED     → pubDate/updated                  │
│     │   └── OFFICIAL_API → Known APIs (USGS, etc.)          │
│     │                                                       │
│     │   TIER 2 - Archive Methods:                           │
│     │   ├── WAYBACK      → archive.org                      │
│     │   ├── URL_VARIATION→ https/http, www/non-www          │
│     │   ├── MEMENTO      → Time Travel API                  │
│     │   ├── ARCHIVE_TODAY→ archive.is/archive.ph            │
│     │   ├── COMMON_CRAWL → commoncrawl.org                  │
│     │   └── UK_ARCHIVE   → webarchive.org.uk                │
│     │                                                       │
│     │   TIER 3 - Fallback:                                  │
│     │   ├── NEWS_RELEASE → News/blog/release page dates     │
│     │   ├── DIRECT_HTTP  → Different User-Agents            │
│     │   └── GROQ_BROWSER → AI browser automation            │
│     │                                                       │
│     └── Return first successful result                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  3. SAVE RESULTS                                            │
│     ├── Successful URLs → outp.csv                          │
│     ├── Failed URLs → failed_urls.csv                       │
│     └── Print summary with success rate                     │
└─────────────────────────────────────────────────────────────┘
```

## Retrieval Methods (14 Total)

### TIER 1: Fast Methods

| Method | Description | Best For |
|--------|-------------|----------|
| **HTTP_HEADER** | HTTP HEAD request for `Last-Modified` header | Direct file URLs (ZIP, CSV) |
| **HTML_SCRAPE** | Parse meta tags, JSON-LD, `<time>` elements | Static HTML pages |
| **SITEMAP** | Parse `sitemap.xml` for `lastmod` dates | Sites with sitemaps |
| **RSS_FEED** | Check RSS/Atom feeds for `pubDate`/`updated` | Sites with feeds |
| **OFFICIAL_API** | Query known APIs (e.g., USGS earthquake) | Configured domains |

### TIER 2: Archive Methods

| Method | Description | Best For |
|--------|-------------|----------|
| **WAYBACK** | Internet Archive Wayback Machine API | Any URL with history |
| **URL_VARIATION** | Try https/http, www/non-www variations | Broken URLs |
| **MEMENTO** | Time Travel API (aggregates archives) | Multiple archive sources |
| **ARCHIVE_TODAY** | archive.is / archive.ph snapshots | Alternative archives |
| **COMMON_CRAWL** | Common Crawl index search | Large-scale crawl data |
| **UK_ARCHIVE** | UK Web Archive timemap | UK government sites |

### TIER 3: Fallback Methods

| Method | Description | Best For |
|--------|-------------|----------|
| **NEWS_RELEASE** | Scrape news/blog/release pages for dates | Sites with news sections |
| **DIRECT_HTTP** | GET with rotating User-Agents (Googlebot, curl) | Bot-blocked sites |
| **GROQ_BROWSER** | AI-powered browser automation (optional) | JavaScript-heavy sites |

## Console Output

```
======================================================================
IMPROVED PROVENANCE CHECKER - ALL METHODS INTEGRATED
======================================================================
Methods: HTTP Headers, HTML Scraping, Sitemap, RSS, Official API,
         Wayback, URL Variations, Memento, Archive.today,
         Common Crawl, UK Archive, News/Press Releases,
         Direct HTTP, Groq Browser
======================================================================

[1/4] Reading Provenance.csv...
   Total URLs: 150

[2/4] Processing (5 workers)...
   [+] 1/150 CaliforniaSchoolPerformance -> HTTP_HEADER
   [+] 2/150 crdc_instructional_wifi_devices -> HTTP_HEADER
   [+] 3/150 USGS_Earthquakes -> WAYBACK
   [+] 4/150 Mongolia_Demographics -> HTTP_HEADER
   [+] 5/150 EurostatData_GDP -> HTML_SCRAPE
   [+] 6/150 ClimateTrace_Emissions -> OFFICIAL_API
   [+] 7/150 USFEMA_NationalRiskIndex -> MEMENTO
   ...

[3/4] Saving results...
   SUCCESS: outp.csv (150 URLs)

======================================================================
                    FINAL SUMMARY
======================================================================

   Total URLs processed:     150
   URLs FETCHED (Success):   150 (100%)
   URLs NOT FETCHED (Failed): 0 (0%)

   Methods Used:
      HTTP_HEADER: 95
      WAYBACK: 25
      HTML_SCRAPE: 12
      MEMENTO: 8
      OFFICIAL_API: 5
      COMMON_CRAWL: 3
      NEWS_RELEASE: 2

======================================================================
OUTPUT FILES:
   Successful URLs saved to: outp.csv
======================================================================
```

## Configuration

### Main Script Configuration

Edit the `CONFIG` dict in `check_provenance_improved.py`:

```python
CONFIG = {
    "input_file": "Provenance.csv",    # Input file with provenance URLs
    "output_file": "outp.csv",         # Output for successful URLs
    "failed_file": "failed_urls.csv",  # Output for failed URLs
    "max_workers": 5,                  # Number of concurrent threads
    "timeout": 30,                     # HTTP request timeout (seconds)
    "delay_min": 1,                    # Minimum delay between requests
    "delay_max": 2,                    # Maximum delay between requests
    "use_groq_fallback": False,        # Enable Groq browser automation
}
```

### Adding Known APIs

Add domain-specific APIs in `KNOWN_APIS` dict:

```python
KNOWN_APIS = {
    "earthquake.usgs.gov": {
        "api_url": "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&limit=1",
        "timestamp_path": ["metadata", "generated"],
        "format": "unix_ms"
    },
    "your.domain.com": {
        "api_url": "https://your.domain.com/api/status",
        "timestamp_path": ["data", "lastUpdated"],
        "format": "iso"  # or "unix_ms"
    },
}
```

### Alternative: YAML Configuration (Modular Approach)

For the modular `core/sentinel.py` approach, edit `config/sources.yaml`:

```yaml
my_new_source:
  import_name: "My New Data Source"
  dcid: "my_new_source"
  method: api                      # http_head, api, beautifulsoup, selenium, cli
  data_url: "https://api.example.com/data.json"
  timestamp_field: "lastModified"
```

## Dependencies

### Required (for check_provenance_improved.py)

```bash
pip install requests pandas python-dotenv beautifulsoup4 urllib3
```

| Package | Version | Purpose |
|---------|---------|---------|
| `requests` | >= 2.28.0 | HTTP requests with retry logic |
| `pandas` | >= 2.0.0 | CSV read/write |
| `python-dotenv` | >= 1.0.0 | Load .env file |
| `beautifulsoup4` | >= 4.11.0 | HTML parsing (TIER 1) |
| `urllib3` | >= 2.0.0 | SSL/connection handling |

### Optional (for Groq fallback)

```bash
pip install groq
```

| Package | Version | Purpose |
|---------|---------|---------|
| `groq` | >= 0.4.0 | AI browser automation (TIER 3) |

### Optional (for modular sentinel)

```bash
pip install PyYAML selenium webdriver-manager lxml
```

| Package | Purpose |
|---------|---------|
| `PyYAML` | YAML config parsing |
| `selenium` | Browser automation |
| `webdriver-manager` | Auto ChromeDriver |
| `lxml` | Fast XML parser |

### Testing

```bash
pip install pytest pytest-cov responses requests-mock
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | Groq API key for browser fallback (TIER 3) | Optional |

Get your Groq API key from: https://console.groq.com/keys

**Note**: The main script works without Groq API key. It's only needed if you enable `use_groq_fallback: True` for JavaScript-heavy sites.

## Testing

### Run Main Script

```bash
# Process all URLs from Provenance.csv
python check_provenance_improved.py
```

### Test with Sample Data

The script uses `Provenance.csv` as input. Sample rows include:
- `CaliforniaSchoolPerformance` - caaspp-elpac.ets.org
- `Mongolia_Demographics` - 1212.mn
- `EurostatData_GDP` - ec.europa.eu
- `USFEMA_NationalRiskIndex` - hazards.fema.gov

### Unit Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_date_parser.py

# Run with verbose output
pytest -v
```

## Supported Date Formats

The date parser supports 18+ formats including:

- ISO 8601: `2024-01-15T10:30:00Z`, `2024-01-15T10:30:00+05:30`
- HTTP Date: `Mon, 15 Jan 2024 10:30:00 GMT`
- Unix Timestamps: `1705315800` (seconds), `1705315800000` (milliseconds)
- US Format: `01/15/2024`, `January 15, 2024`
- European Format: `15/01/2024`, `15 Jan 2024`
- Compact: `20240115`, `2024-01-15`
- With prefixes: `Last updated: 2024-01-15`, `Modified on January 15, 2024`

## Troubleshooting

### Common Issues

**SSL Errors**
```
SSL certificate verify failed
```
The script automatically disables SSL warnings. If issues persist, check your network/proxy settings.

**Rate Limiting**
```
HTTP_429 or CONNECTION_ERROR
```
Increase `delay_min`/`delay_max` in CONFIG, or reduce `max_workers`.

**No Timestamps Found**
If a URL fails with all methods:
1. Check if the URL is accessible in browser
2. Look at `failed_urls.csv` for error details
3. The URL may require JavaScript (enable `use_groq_fallback`)

### Groq API Setup (Optional)

```bash
# Set API key for Groq browser fallback
# Windows
set GROQ_API_KEY=your_key_here

# Linux/Mac
export GROQ_API_KEY=your_key_here

# Or add to .env file
echo "GROQ_API_KEY=your_key_here" > .env
```

Then enable in CONFIG:
```python
CONFIG = {
    ...
    "use_groq_fallback": True,
}
```

### Date Parsing Issues

If dates aren't parsed correctly:
1. Check `last_modified_raw` column for the raw value
2. Add new format to `normalize_date()` function
3. Add regex pattern to `extract_date_from_text()`

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements.txt
pip install pytest pytest-cov

# Run tests before committing
pytest

# Check code coverage
pytest --cov=. --cov-report=html
```

## License

This project is open source and available under the [MIT License](LICENSE).

## Acknowledgments

- [Internet Archive Wayback Machine](https://archive.org/web/) for historical snapshots
- [Memento Time Travel](http://timetravel.mementoweb.org/) for aggregating web archives
- [Common Crawl](https://commoncrawl.org/) for web crawl data
- [Archive.today](https://archive.today/) for page archiving
- [UK Web Archive](https://www.webarchive.org.uk/) for UK site archives
- [Groq](https://groq.com/) for AI browser automation (optional)
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) for HTML parsing
- [Data Commons](https://datacommons.org/) for provenance data references

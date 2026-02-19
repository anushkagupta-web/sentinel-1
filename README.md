# Sentinel - Data Source Monitoring Agent

Sentinel is an automated monitoring agent that detects updates in external data sources by examining metadata (timestamps, ETags) **without downloading entire datasets**. It also uses **Groq LLM** to verify that the extracted timestamp is actually the "last modified" date, providing confidence scores and reasoning for each verification.

## Features

- **Multiple Retrieval Methods**: HTTP HEAD, REST API, BeautifulSoup, Selenium, CLI
- **Smart Date Parsing**: Supports 18+ date formats including ISO, Unix timestamps, HTTP dates
- **LLM Verification**: Uses Groq API (llama-3.3-70b-versatile model) to verify extracted timestamps with confidence scores
- **State Management**: Tracks previous timestamps to detect changes via JSON persistence
- **CSV Export**: Exports results with verification details
- **Configurable**: YAML-based configuration for sources and settings
- **Concurrent Processing**: Optional Groq Compound feature for parallel source checking
- **Modular Architecture**: Clean separation of concerns with Factory and Strategy patterns

## Project Structure

```
sentinel/
├── config/
│   ├── sources.yaml          # Data source configurations (7 sources)
│   └── settings.yaml         # Application settings (timeouts, logging)
├── core/
│   ├── sentinel.py           # Main orchestrator class (~300 lines)
│   ├── registry.py           # Source registry & handler factory (~110 lines)
│   └── state_manager.py      # Thread-safe state persistence (~125 lines)
├── handlers/
│   ├── base_handler.py       # Abstract base handler (~85 lines)
│   ├── http_handler.py       # HTTP HEAD requests (~95 lines)
│   ├── api_handler.py        # REST API JSON/XML parsing (~170 lines)
│   ├── bs4_handler.py        # BeautifulSoup HTML scraping (~215 lines)
│   ├── selenium_handler.py   # Headless Chrome automation (~170 lines)
│   └── cli_handler.py        # Shell command wrapper (~97 lines)
├── models/
│   ├── source.py             # DataSource dataclass (~60 lines)
│   └── check_result.py       # CheckResult dataclass (~80 lines)
├── utils/
│   ├── date_parser.py        # Flexible date parsing (~180 lines)
│   ├── groq_verifier.py      # Groq LLM verification (~290 lines)
│   └── logger.py             # Logging configuration (~70 lines)
├── scripts/
│   └── run_check.py          # CLI interface (~130 lines)
├── state/
│   └── last_checked.json     # Persistent timestamp storage
├── tests/
│   ├── conftest.py           # Pytest fixtures
│   ├── test_sentinel.py      # Integration tests
│   ├── test_date_parser.py   # Date parsing tests
│   └── test_handlers.py      # Handler unit tests
├── main.py                   # Monolithic entry point (alternative)
├── __init__.py               # Package initialization
├── .env                      # Environment variables (API keys)
├── .env.example              # Template for environment variables
├── .gitignore
├── requirements.txt
├── output.csv                # Default results output
├── Provenance.csv            # Input data for provenance checking
├── Provenance.md             # Markdown version of provenance data
│
│   # Experimental Scripts (Groq Compound Integration)
├── check_provenance_browser.py   # Groq Compound with browser automation
├── check_provenance_final.py     # Enhanced final version
├── check_provenance_hybrid.py    # Hybrid: BS4 + Groq + Browser fallback
├── check_provenance_improved.py  # Multi-strategy approach
└── check_provenance_urls.py      # URL checking variant
```

## Architecture & Design Patterns

```
┌─────────────────────────────────────────────────────────────┐
│                    SENTINEL ARCHITECTURE                     │
└─────────────────────────────────────────────────────────────┘

┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐
│   Sentinel  │────▶│  Registry   │────▶│      Handlers       │
│ (Orchestrator)    │  (Factory)  │     │ (Strategy Pattern)  │
└─────────────┘     └─────────────┘     └─────────────────────┘
       │                                         │
       │            ┌─────────────┐              │
       │────────────│StateManager │◀─────────────│
       │            │  (State)    │              │
       │            └─────────────┘              │
       │                                         │
       ▼                                         ▼
┌─────────────┐                         ┌─────────────────────┐
│GroqVerifier │                         │    CheckResult      │
│ (Decorator) │                         │    (DataClass)      │
└─────────────┘                         └─────────────────────┘
```

**Design Patterns Used:**
- **Factory Pattern**: SourceRegistry creates appropriate handlers based on method
- **Strategy Pattern**: Different handlers implement different retrieval strategies
- **Template Method Pattern**: BaseHandler defines interface, subclasses implement details
- **State Pattern**: StateManager handles persistent state with thread-safety
- **Decorator Pattern**: Groq verification wraps handler results

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

### Command Line Interface

```bash
# Check all sources
python scripts/run_check.py

# Check specific source by DCID
python scripts/run_check.py --dcid BIS_CentralBankPolicyRate

# List all available sources
python scripts/run_check.py --list

# Disable LLM verification (faster, no API calls)
python scripts/run_check.py --no-verify

# Verbose mode for debugging
python scripts/run_check.py -v

# Custom output file
python scripts/run_check.py --output results.csv
```

### Python Module

```python
from core.sentinel import Sentinel

# Initialize with verification enabled
sentinel = Sentinel(enable_verification=True)

# Check all sources
results = sentinel.check_all_sources()

# Check specific source
result = sentinel.check_for_updates("BIS_CentralBankPolicyRate")

# Export to CSV
sentinel.export_to_csv(results, "output.csv")
```

### Experimental Scripts

```bash
# Groq Compound with browser automation
python check_provenance_browser.py

# Hybrid approach (BS4 + Groq validation + Browser fallback)
python check_provenance_hybrid.py

# Multi-strategy improved version
python check_provenance_improved.py
```

## Available Data Sources

| DCID | Name | Method | Description |
|------|------|--------|-------------|
| `BIS_CentralBankPolicyRate` | BIS Central Bank Policy Rate | HTTP HEAD | Bank for International Settlements policy rates ZIP file |
| `usa_child_birth` | USA Child Birth | HTTP HEAD | CDC birth data CSV |
| `FBIGovCrime` | FBI Gov Crime | Selenium | FBI crime statistics (JavaScript-heavy site) |
| `USA_DOL_Wages` | USA DOL Wages | Selenium | Labor department minimum wage history (bot protection) |
| `mongolia_imports` | Mongolia Imports | BeautifulSoup | Mongolia open data portal |
| `FAO_Currency_statvar` | FAO Currency Statvar | CLI | FAO currency exchange rate ZIP |
| `CDC500` | CDC 500 Places | API | CDC 500 Places health data JSON API |

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                     SENTINEL WORKFLOW                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  1. INITIALIZATION                                          │
│     ├── Load config/sources.yaml (7 data sources)          │
│     ├── Load config/settings.yaml (timeouts, options)      │
│     ├── Initialize StateManager (load last_checked.json)   │
│     └── Initialize GroqVerifier (load GROQ_API_KEY)        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  2. FOR EACH DATA SOURCE                                    │
│     ├── Get source configuration from registry              │
│     ├── Select handler based on method:                     │
│     │   ├── http_head  → HTTPHandler                        │
│     │   ├── api        → APIHandler                         │
│     │   ├── beautifulsoup → BS4Handler                      │
│     │   ├── selenium   → SeleniumHandler                    │
│     │   └── cli        → CLIHandler                         │
│     ├── Handler fetches current timestamp                   │
│     ├── Compare with stored timestamp (detect changes)      │
│     └── Update state file with current timestamp            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  3. GROQ LLM VERIFICATION (if enabled)                      │
│     ├── Send extracted timestamp + context to Groq API      │
│     ├── Model: llama-3.3-70b-versatile                      │
│     ├── LLM analyzes if timestamp is "last modified" date   │
│     └── Returns: is_verified, confidence (0-1), reasoning   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  4. EXPORT RESULTS                                          │
│     ├── Create CheckResult objects for all sources          │
│     ├── Export to CSV with all details                      │
│     ├── Update JSON state file for next comparison          │
│     └── Display console summary                             │
└─────────────────────────────────────────────────────────────┘
```

## Retrieval Methods

### 1. HTTP HEAD (`http_head`)
Sends HTTP HEAD request to get `Last-Modified` header without downloading the file. Falls back to ETag and Date headers if Last-Modified is unavailable. Includes retry logic with configurable timeout.

**Best for:** Direct file URLs (ZIP, CSV, etc.)

### 2. API (`api`)
Fetches JSON/XML from REST API and extracts timestamp fields. Searches recursively for fields like `rowsUpdatedAt`, `lastModified`, `dataUpdatedAt`. Supports Unix timestamps in seconds and milliseconds.

**Best for:** REST API endpoints with structured JSON responses

### 3. BeautifulSoup (`beautifulsoup`)
Parses static HTML pages using CSS selectors. Extracts dates from `<time>` elements (datetime attribute), meta tags, and text patterns using regex. Supports custom selectors.

**Best for:** Static HTML pages with visible date information

### 4. Selenium (`selenium`)
Uses headless Chrome browser for JavaScript-rendered pages. Auto-downloads ChromeDriver via webdriver-manager. Supports wait timeouts for dynamic content and CSS selectors.

**Best for:** JavaScript-heavy sites, pages with bot protection

### 5. CLI (`cli`)
Executes shell commands like `curl -sI` to fetch headers. Parses HTTP headers from command output.

**Best for:** Custom retrieval commands, specific curl configurations

## Output Format

### Console Output

```
Groq LLM verification: ENABLED

Checking all data sources...
--------------------------------------------------

Results Summary:
----------------------------------------------------------------------
  [NO CHANGE ] BIS Central Bank Policy Rate [VERIFIED 100%]
  [UPDATED   ] USA Child Birth [VERIFIED 87%]
  [ERROR     ] FBI Gov Crime [NOT VERIFIED]

Results exported to: output.csv

Summary: 1 updated, 1 unchanged, 1 errors
```

### CSV Output Columns

| Column | Description |
|--------|-------------|
| `import_name` | Human-readable source name |
| `dcid` | Data Commons ID |
| `data_url` | Source data URL |
| `script_url` | Reference script URL |
| `method` | Retrieval method used |
| `last_modified_timestamp` | Current parsed timestamp |
| `raw_timestamp` | Original timestamp string |
| `previous_timestamp` | Previously stored timestamp |
| `changed` | Whether data has changed (True/False) |
| `check_time` | When the check was performed |
| `status` | success/error/no_change |
| `error` | Error message (if any) |
| `is_verified` | LLM verification result |
| `verification_confidence` | Confidence percentage (0-100%) |
| `verification_reasoning` | LLM explanation |
| `suggested_timestamp` | LLM suggested timestamp (if different) |

### State File Format (`state/last_checked.json`)

```json
{
  "BIS_CentralBankPolicyRate": {
    "timestamp": "2026-02-11T09:22:49+00:00",
    "last_check": "2026-02-16T13:17:28.483087",
    "raw_value": "Wed, 11 Feb 2026 09:22:49 GMT"
  },
  "usa_child_birth": {
    "timestamp": "2026-01-15T00:00:00+00:00",
    "last_check": "2026-02-16T13:17:30.123456",
    "raw_value": "January 15, 2026"
  }
}
```

## Configuration

### Adding a New Source

Edit `config/sources.yaml`:

```yaml
my_new_source:
  import_name: "My New Data Source"
  dcid: "my_new_source"
  method: api                      # http_head, api, beautifulsoup, selenium, cli
  data_url: "https://api.example.com/data.json"
  script_url: "https://github.com/..."
  timestamp_field: "lastModified"  # Primary field to look for
  fallback_fields:                 # Alternative fields if primary not found
    - "updated_at"
    - "modified"
    - "dataUpdatedAt"
```

### Selenium Source Example

```yaml
my_js_source:
  import_name: "JavaScript Heavy Site"
  dcid: "my_js_source"
  method: selenium
  data_url: "https://example.com/dynamic-page"
  wait_timeout: 45                 # Seconds to wait for page load
  selectors:                       # CSS selectors to try
    - "time.last-updated"
    - "span.date-modified"
    - ".update-info"
```

### BeautifulSoup Source Example

```yaml
my_static_source:
  import_name: "Static HTML Page"
  dcid: "my_static_source"
  method: beautifulsoup
  data_url: "https://example.com/data-page"
  selectors:
    - "time[datetime]"
    - "meta[name='last-modified']"
  pattern: "Last updated: (\\d{4}-\\d{2}-\\d{2})"  # Regex pattern
```

### Application Settings (`config/settings.yaml`)

```yaml
http:
  timeout: 30                      # Request timeout in seconds
  max_retries: 3                   # Number of retry attempts
  user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

selenium:
  headless: true                   # Run Chrome in headless mode
  wait_timeout: 45                 # Default wait timeout
  page_load_timeout: 60            # Page load timeout

logging:
  level: INFO                      # DEBUG, INFO, WARNING, ERROR
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "sentinel.log"             # Log file path
```

## Dependencies

### Core Dependencies
- `requests >= 2.28.0` - HTTP client for API calls
- `PyYAML >= 6.0` - YAML configuration parsing
- `python-dateutil >= 2.8.0` - Flexible date parsing

### Web Scraping
- `beautifulsoup4 >= 4.11.0` - HTML/XML parsing
- `lxml >= 4.9.0` - Fast XML/HTML parser backend

### Browser Automation
- `selenium >= 4.8.0` - Browser automation framework
- `webdriver-manager >= 4.0.0` - Automatic ChromeDriver management

### LLM Verification
- `groq >= 0.4.0` - Groq API client
- `python-dotenv >= 1.0.0` - Environment variable management

### Data Processing
- `pandas >= 2.0.0` - CSV processing and data manipulation

### Testing
- `pytest >= 7.0.0` - Test framework
- `pytest-cov >= 4.0.0` - Coverage reporting
- `responses >= 0.22.0` - HTTP mocking
- `requests-mock >= 1.10.0` - Request mocking

### Optional
- `colorama >= 0.4.6` - Colored console output
- `tqdm >= 4.65.0` - Progress bars

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | Groq API key for LLM verification | Yes (for verification) |

Get your Groq API key from: https://console.groq.com/keys

## Testing

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

### Selenium Issues

```bash
# If ChromeDriver fails to download automatically:
pip install --upgrade webdriver-manager

# For Chrome version mismatch:
# The webdriver-manager will auto-detect and download the correct version
```

### Groq API Errors

```bash
# Verify API key is set
echo $GROQ_API_KEY  # Linux/Mac
echo %GROQ_API_KEY% # Windows

# Run without verification to test other components
python scripts/run_check.py --no-verify
```

### Date Parsing Issues

If a date isn't being parsed correctly, check:
1. The `timestamp_field` or `selectors` in sources.yaml
2. Add a custom `pattern` regex for non-standard formats
3. Check logs for the raw extracted value

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

- [Groq](https://groq.com/) for LLM API (llama-3.3-70b-versatile model)
- [Data Commons](https://datacommons.org/) for data source references
- [Selenium](https://www.selenium.dev/) for browser automation
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) for HTML parsing

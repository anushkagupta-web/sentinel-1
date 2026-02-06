# Sentinel - Data Source Monitoring Agent

Sentinel is an automated monitoring agent that detects updates in external data sources by examining metadata (timestamps, ETags) **without downloading entire datasets**. It also uses **Groq LLM** to verify that the extracted timestamp is actually the "last modified" date.

## Features

- **Multiple Retrieval Methods**: HTTP HEAD, REST API, BeautifulSoup, Selenium, CLI
- **Smart Date Parsing**: Supports 18+ date formats including ISO, Unix timestamps, HTTP dates
- **LLM Verification**: Uses Groq API to verify extracted timestamps with confidence scores
- **State Management**: Tracks previous timestamps to detect changes
- **CSV Export**: Exports results with verification details
- **Configurable**: YAML-based configuration for sources and settings

## Project Structure

```
sentinel/
├── config/
│   ├── sources.yaml        # Data source configurations
│   └── settings.yaml       # Application settings
├── core/
│   ├── sentinel.py         # Main orchestrator
│   ├── registry.py         # Source registry & handler factory
│   └── state_manager.py    # State persistence
├── handlers/
│   ├── base_handler.py     # Abstract base handler
│   ├── http_handler.py     # HTTP HEAD requests
│   ├── api_handler.py      # REST API JSON parsing
│   ├── bs4_handler.py      # BeautifulSoup HTML scraping
│   ├── selenium_handler.py # Browser automation
│   └── cli_handler.py      # Shell command wrapper
├── models/
│   ├── source.py           # DataSource dataclass
│   └── check_result.py     # CheckResult dataclass
├── utils/
│   ├── date_parser.py      # Date parsing utility
│   ├── groq_verifier.py    # Groq LLM verification
│   └── logger.py           # Logging setup
├── scripts/
│   └── run_check.py        # CLI interface
├── state/
│   └── last_checked.json   # Stored timestamps
├── tests/                  # Unit tests
├── .env                    # Environment variables (API keys)
├── .gitignore
├── requirements.txt
└── output.csv              # Results output
```

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/sentinel.git
cd sentinel
```

### 2. Create Virtual Environment (Optional but Recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

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

### Check All Sources

```bash
python scripts/run_check.py
```

### Check Specific Source

```bash
python scripts/run_check.py --dcid BIS_CentralBankPolicyRate
```

### List Available Sources

```bash
python scripts/run_check.py --list
```

### Disable LLM Verification

```bash
python scripts/run_check.py --no-verify
```

### Verbose Mode

```bash
python scripts/run_check.py -v
```

### Custom Output File

```bash
python scripts/run_check.py --output results.csv
```

## Available Data Sources

| DCID | Name | Method | Description |
|------|------|--------|-------------|
| `BIS_CentralBankPolicyRate` | BIS Central Bank Policy Rate | HTTP HEAD | Bank policy rates ZIP file |
| `usa_child_birth` | USA Child Birth | HTTP HEAD | CDC birth data CSV |
| `FBIGovCrime` | FBI Gov Crime | Selenium | FBI crime statistics (JS-heavy) |
| `USA_DOL_Wages` | USA DOL Wages | BeautifulSoup | Labor department wages HTML |
| `mongolia_imports` | Mongolia Imports | API | REST API endpoint |
| `FAO_Currency_statvar` | FAO Currency Statvar | CLI | FAO currency data |
| `CDC500` | CDC 500 Places | API | CDC health data JSON API |

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                     SENTINEL WORKFLOW                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Load Configuration (sources.yaml, settings.yaml)        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  2. For Each Data Source:                                   │
│     ├── Select appropriate handler (HTTP/API/Selenium/etc)  │
│     ├── Fetch current timestamp from source                 │
│     ├── Compare with stored timestamp                       │
│     └── Detect if data has changed                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Groq LLM Verification:                                  │
│     ├── Send extracted timestamp + page content to LLM      │
│     ├── LLM analyzes if timestamp is "last modified" date   │
│     └── Returns: is_verified, confidence, reasoning         │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Export Results:                                         │
│     ├── CSV file with all details                           │
│     ├── JSON state file for next comparison                 │
│     └── Console summary                                     │
└─────────────────────────────────────────────────────────────┘
```

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
| `method` | Retrieval method used |
| `last_modified_timestamp` | Current timestamp |
| `previous_timestamp` | Previously stored timestamp |
| `changed` | Whether data has changed |
| `is_verified` | LLM verification result |
| `verification_confidence` | Confidence percentage |
| `verification_reasoning` | LLM explanation |

## Retrieval Methods

### 1. HTTP HEAD (`http_head`)
Sends HTTP HEAD request to get `Last-Modified` header without downloading the file.

### 2. API (`api`)
Fetches JSON/XML from REST API and extracts timestamp fields like `rowsUpdatedAt`, `lastModified`.

### 3. BeautifulSoup (`beautifulsoup`)
Parses static HTML pages to find dates in `<time>` tags, meta tags, or text patterns.

### 4. Selenium (`selenium`)
Uses headless Chrome browser for JavaScript-rendered pages.

### 5. CLI (`cli`)
Executes shell commands like `curl -sI` to fetch headers.

## Configuration

### Adding a New Source

Edit `config/sources.yaml`:

```yaml
my_new_source:
  import_name: "My New Data Source"
  dcid: "my_new_source"
  method: api                    # http_head, api, beautifulsoup, selenium, cli
  data_url: "https://api.example.com/data.json"
  script_url: "https://github.com/..."
  timestamp_field: "lastModified"
  fallback_fields:
    - "updated_at"
    - "modified"
```

### Settings (`config/settings.yaml`)

```yaml
http:
  timeout: 30
  max_retries: 3
  user_agent: "Sentinel-Monitor/1.0"

selenium:
  headless: true
  wait_timeout: 45

logging:
  level: INFO
```

## Dependencies

- `requests` - HTTP client
- `beautifulsoup4` - HTML parsing
- `selenium` - Browser automation
- `webdriver-manager` - ChromeDriver management
- `PyYAML` - YAML configuration
- `python-dateutil` - Date parsing
- `groq` - Groq LLM API
- `python-dotenv` - Environment variables

## Environment Variables

| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key for LLM verification |

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is open source and available under the [MIT License](LICENSE).

## Acknowledgments

- [Groq](https://groq.com/) for LLM API
- [Data Commons](https://datacommons.org/) for data source references

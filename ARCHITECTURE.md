# Sentinel Agent - Architecture Documentation

**Repository**: https://github.com/dipankaratriya-cloud/sentinel

---

## Overview

The **Sentinel Agent** is an automated monitoring system that detects updates in external data sources by examining metadata (timestamps, ETags, HTTP headers) **without downloading entire datasets**. It combines multiple retrieval strategies with LLM verification using Groq API to provide confidence scores for extracted timestamps.

**Key Capability**: Monitors 7+ Data Commons data sources and tracks when they're updated, enabling automated pipelines to know when to re-fetch data.

---

## Core Components

### 1. Main Orchestrator (`core/sentinel.py`)

The central orchestration class that coordinates all update checks across data sources.

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `__init__()` | Initializes registry, state manager, and Groq verifier with optional verification toggle |
| `check_for_updates(dcid)` | Checks a single source for updates, returns CheckResult |
| `check_all_sources()` | Iterates through all configured sources and performs update checks |
| `export_to_csv(results, output_path)` | Exports results to CSV with 16 columns |
| `_create_result()` | Internal method to construct CheckResult objects |

---

### 2. Source Registry (`core/registry.py`)

Factory pattern implementation that creates appropriate handlers based on retrieval method configuration.

**Class: SourceRegistry**

```python
class SourceRegistry:
    def __init__(self, sources_path: str = "config/sources.yaml",
                 settings_path: str = "config/settings.yaml")
```

**Methods:**

| Method | Description |
|--------|-------------|
| `get_source(dcid)` | Returns source configuration dictionary for given DCID |
| `get_handler(dcid)` | Factory method - instantiates appropriate handler class |
| `list_sources()` | Returns list of all configured source DCIDs |
| `get_settings()` | Returns global application settings |

**Handler Mapping:**

```python
HANDLER_MAP = {
    'http_head': HTTPHandler,
    'api': APIHandler,
    'beautifulsoup': BS4Handler,
    'selenium': SeleniumHandler,
    'cli': CLIHandler
}
```

---

### 3. State Manager (`core/state_manager.py`)

Persistent state management with thread-safe operations for tracking timestamp history.

**Class: StateManager**

```python
class StateManager:
    def __init__(self, state_file: str = "state/last_checked.json")
```

**Methods:**

| Method | Description |
|--------|-------------|
| `get_last_timestamp(dcid)` | Returns previous timestamp for a source |
| `update_timestamp(dcid, timestamp, raw_value, etag)` | Saves current timestamp to state |
| `get_state(dcid)` | Returns full state dict for a source |
| `has_changed(dcid, current)` | Compares current vs stored timestamp |

**State Structure:**

```json
{
  "BIS_CentralBankPolicyRate": {
    "timestamp": "2026-02-11T09:22:49+00:00",
    "last_check": "2026-02-16T13:17:28.483087",
    "raw_value": "Wed, 11 Feb 2026 09:22:49 GMT",
    "etag": "\"abc123\""
  }
}
```

---

### 4. Handlers (`handlers/`)

Strategy pattern implementations for different retrieval methods.

#### Base Handler (`handlers/base_handler.py`)

```python
class BaseHandler(ABC):
    @abstractmethod
    def fetch_current_timestamp(self) -> Optional[datetime]:
        pass

    def get_raw_timestamp(self) -> Optional[str]:
        return self._raw_timestamp

    def get_page_content(self) -> Optional[str]:
        return self._page_content
```

#### Handler Implementations:

| Handler | Method | Use Case | Strategy |
|---------|--------|----------|----------|
| `HTTPHandler` | `http_head` | Direct file URLs (ZIP, CSV) | HEAD request → Last-Modified/ETag headers |
| `APIHandler` | `api` | REST APIs | GET JSON/XML → Parse timestamp fields |
| `BS4Handler` | `beautifulsoup` | Static HTML pages | Parse with CSS selectors, meta tags, regex |
| `SeleniumHandler` | `selenium` | JavaScript-heavy sites | Headless Chrome → Wait for JS → Extract dates |
| `CLIHandler` | `cli` | Custom commands | Execute curl/wget → Parse output |

---

### 5. Data Models (`models/`)

#### CheckResult (`models/check_result.py`)

```python
@dataclass
class CheckResult:
    dcid: str                              # Data Commons ID
    import_name: Optional[str]             # Human-readable name
    data_url: Optional[str]                # Source URL
    script_url: Optional[str]              # GitHub script URL
    method: Optional[str]                  # Retrieval method used
    changed: bool                          # Has data changed?
    current_timestamp: Optional[datetime]  # Extracted timestamp
    previous_timestamp: Optional[datetime] # Last stored timestamp
    raw_timestamp: Optional[str]           # Original string before parsing
    error: Optional[str]                   # Error message if any
    check_time: datetime                   # When check was performed

    # Groq verification fields
    is_verified: Optional[bool]            # LLM verification result
    verification_confidence: float         # 0.0 to 1.0 confidence
    verification_reasoning: Optional[str]  # LLM explanation
    suggested_timestamp: Optional[str]     # Alternative if LLM disagrees
```

#### DataSource (`models/source.py`)

```python
@dataclass
class DataSource:
    dcid: str                    # Data Commons ID
    import_name: str             # Display name
    method: str                  # Retrieval method
    data_url: str                # Source URL
    script_url: str              # Reference script
    selector: Optional[str]      # CSS selectors (BS4/Selenium)
    wait_timeout: int            # Selenium wait timeout
    timestamp_field: str         # API field name
    response_format: str         # json/xml
    fallback_fields: List[str]   # Alternative field names
    date_patterns: List[str]     # Regex patterns for dates
    command: str                 # CLI command
```

---

### 6. Utilities (`utils/`)

#### Date Parser (`utils/date_parser.py`)

Parses 18+ date formats with intelligent fallbacks.

**Supported Formats:**

| Format Type | Examples |
|-------------|----------|
| ISO 8601 | `2024-01-15T10:30:00Z`, `2024-01-15T10:30:00+05:30` |
| HTTP RFC | `Mon, 15 Jan 2024 10:30:00 GMT` |
| Unix Timestamp | `1705315800` (seconds), `1705315800000` (ms) |
| US Format | `01/15/2024`, `January 15, 2024` |
| European | `15/01/2024`, `15 Jan 2024` |
| Compact | `20240115`, `2024-01-15` |
| Text Prefix | `"Last updated: 2024-01-15"` |

**Parsing Strategy:**
1. Try `dateutil.parser` (most flexible)
2. Try 20+ standard format patterns
3. Try Unix timestamp parsing
4. Return `None` if all fail

#### Groq Verifier (`utils/groq_verifier.py`)

LLM-based timestamp verification using Groq API.

```python
class GroqVerifier:
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile")
```

**Methods:**

| Method | Description |
|--------|-------------|
| `verify_timestamp(timestamp, page_content)` | Verifies extracted timestamp with LLM |
| `verify_with_headers(timestamp, headers)` | Verifies using HTTP headers context |

**Verification Response:**

```json
{
  "is_verified": true,
  "confidence": 0.95,
  "reasoning": "The timestamp matches the 'Last Updated' field in the page header",
  "suggested_timestamp": null
}
```

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            INITIALIZATION                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Load config/sources.yaml (7 data sources)                               │
│  2. Load config/settings.yaml (HTTP, Selenium, logging settings)            │
│  3. Initialize StateManager (load state/last_checked.json)                  │
│  4. Initialize GroqVerifier (load GROQ_API_KEY from .env)                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FOR EACH DATA SOURCE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. SourceRegistry.get_source(dcid) → source configuration                  │
│  2. SourceRegistry.get_handler(dcid) → instantiate handler                  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    HANDLER RETRIEVAL STRATEGIES                        │ │
│  ├────────────────────────────────────────────────────────────────────────┤ │
│  │  HTTPHandler    → HEAD request → Last-Modified/ETag/Date headers       │ │
│  │  APIHandler     → GET /api → Parse JSON/XML → Extract timestamp        │ │
│  │  BS4Handler     → GET HTML → Selectors/Meta tags/Regex patterns        │ │
│  │  SeleniumHandler→ Launch Chrome → Wait for JS → Find date elements     │ │
│  │  CLIHandler     → Execute curl → Parse HTTP headers from output        │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    TIMESTAMP EXTRACTION & COMPARISON                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Handler.fetch_current_timestamp() → datetime object                     │
│  2. DateParser.parse() → normalize to datetime                              │
│  3. StateManager.get_last_timestamp(dcid) → previous datetime               │
│  4. Compare: current > previous? → changed = True/False                     │
│  5. StateManager.update_timestamp() → persist to JSON                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    LLM VERIFICATION (Optional)                               │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Send extracted timestamp + page content to Groq                         │
│  2. Model analyzes context for confirmation                                 │
│  3. Returns:                                                                │
│     ├─ is_verified: bool                                                    │
│     ├─ confidence: float (0.0-1.0)                                          │
│     ├─ reasoning: str                                                       │
│     └─ suggested_timestamp: str (if different)                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         RESULT & EXPORT                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  1. Create CheckResult object with all metadata                             │
│  2. Export to CSV (16 columns)                                              │
│  3. Display summary to console                                              │
│  4. Save state to state/last_checked.json                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## External Integrations

### 1. Groq API

```python
from groq import Groq

client = Groq(api_key=api_key)

chat_completion = client.chat.completions.create(
    messages=[{"role": "user", "content": verification_prompt}],
    model="llama-3.3-70b-versatile",
    temperature=0.1,
    max_tokens=500
)
```

**Purpose**: LLM verification of extracted timestamps
**Features**:
- Structured JSON responses
- Temperature: 0.1 (deterministic)
- Error handling with graceful fallback

### 2. Data Commons Sources

| Source | DCID | Method | URL Type |
|--------|------|--------|----------|
| BIS Central Bank Policy Rate | `BIS_CentralBankPolicyRate` | `http_head` | ZIP file |
| USA Child Birth Data | `CDCChildBirthData` | `http_head` | CSV file |
| FBI Crime Data | `FBIGovCrime` | `selenium` | JS-heavy site |
| USA DOL Minimum Wage | `DOLMinimumWage` | `selenium` | Bot protected |
| Mongolia Imports | `MongoliaImports` | `beautifulsoup` | Static HTML |
| FAO Currency Exchange | `FAOCurrency` | `cli` | ZIP file |
| CDC 500 Places | `CDC500` | `api` | JSON API |

### 3. Browser Automation

- **Selenium WebDriver**: Controls headless Chrome
- **webdriver-manager**: Auto-downloads ChromeDriver
- **Features**: Headless mode, JavaScript rendering, configurable wait timeouts

---

## Error Handling

| Error Type | Detection | Response |
|------------|-----------|----------|
| Connection Timeout | `timeout` in exception | Retry with exponential backoff |
| HTTP 429 (Rate Limit) | Status code 429 | Wait and retry |
| HTTP 404 (Not Found) | Status code 404 | Log error, return None |
| Selenium Timeout | `TimeoutException` | Increase wait, try fallback selectors |
| Parse Error | `ValueError` in date parsing | Try alternative date formats |
| API Error | Groq API exception | Skip verification, continue |
| Invalid Config | Missing YAML keys | Log warning, use defaults |

---

## Configuration

### Environment Variables

```bash
# Required for LLM verification
GROQ_API_KEY=gsk_your_groq_api_key_here
```

### Source Configuration (`config/sources.yaml`)

**HTTP HEAD Example:**
```yaml
BIS_CentralBankPolicyRate:
  import_name: "BIS Central Bank Policy Rate"
  dcid: "BIS_CentralBankPolicyRate"
  method: http_head
  data_url: "https://data.bis.org/static/bulk/WS_CBPOL_csv_flat.zip"
  script_url: "https://github.com/datacommonsorg/data/tree/master/scripts/bis"
```

**API Example:**
```yaml
CDC500:
  import_name: "CDC 500 Places"
  dcid: "CDC500"
  method: api
  data_url: "https://chronicdata.cdc.gov/api/views/swc5-untb.json"
  timestamp_field: "rowsUpdatedAt"
  response_format: json
  fallback_fields:
    - "dataUpdatedAt"
    - "metadataUpdatedAt"
```

**Selenium Example:**
```yaml
FBIGovCrime:
  import_name: "FBI Gov Crime"
  dcid: "FBIGovCrime"
  method: selenium
  data_url: "https://cde.ucr.cjis.gov/LATEST/webapp/#/pages/downloads"
  selector: "span.last-updated, div.update-date"
  wait_timeout: 45
  page_load_timeout: 90
```

### Application Settings (`config/settings.yaml`)

```yaml
http:
  timeout: 30
  max_retries: 3
  user_agent: "Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."

selenium:
  headless: true
  wait_timeout: 45
  page_load_timeout: 60

logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "sentinel.log"

state:
  file: "state/last_checked.json"

output:
  csv_file: "output.csv"
```

---

## File Structure

```
sentinel/
├── config/
│   ├── sources.yaml              # Data source configurations (7 sources)
│   └── settings.yaml             # Application settings
├── core/
│   ├── __init__.py
│   ├── sentinel.py               # Main Sentinel orchestrator
│   ├── registry.py               # Source registry (factory pattern)
│   └── state_manager.py          # Persistent state management
├── handlers/
│   ├── __init__.py
│   ├── base_handler.py           # Abstract base handler
│   ├── http_handler.py           # HTTP HEAD requests
│   ├── api_handler.py            # REST API parsing
│   ├── bs4_handler.py            # BeautifulSoup HTML parsing
│   ├── selenium_handler.py       # Headless browser automation
│   └── cli_handler.py            # Shell command execution
├── models/
│   ├── __init__.py
│   ├── check_result.py           # CheckResult dataclass
│   └── source.py                 # DataSource dataclass
├── utils/
│   ├── __init__.py
│   ├── date_parser.py            # Multi-format date parser
│   ├── groq_verifier.py          # LLM verification
│   └── logger.py                 # Logging configuration
├── scripts/
│   └── run_check.py              # CLI entry point
├── tests/
│   ├── conftest.py               # Pytest fixtures
│   ├── test_sentinel.py          # Integration tests
│   ├── test_date_parser.py       # Date parsing tests
│   └── test_handlers.py          # Handler unit tests
├── state/
│   └── last_checked.json         # Persistent timestamp storage
├── main.py                       # Monolithic entry point
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
└── README.md                     # Project documentation
```

---

## Usage Flow

```
1. User executes: python scripts/run_check.py --dcid BIS_CentralBankPolicyRate
           │
           ▼
2. Sentinel initializes components:
   ├─ SourceRegistry loads YAML configs
   ├─ StateManager loads last_checked.json
   └─ GroqVerifier loads API key
           │
           ▼
3. Registry creates HTTPHandler for BIS source
           │
           ▼
4. HTTPHandler sends HEAD request to data.bis.org
   → Extracts Last-Modified: "Wed, 11 Feb 2026 09:22:49 GMT"
           │
           ▼
5. DateParser normalizes to: 2026-02-11T09:22:49+00:00
           │
           ▼
6. StateManager compares with stored timestamp
   → changed = True (if different)
           │
           ▼
7. GroqVerifier validates timestamp (if --no-verify not set)
   → Returns: {is_verified: true, confidence: 0.95}
           │
           ▼
8. CheckResult created with all metadata
           │
           ▼
9. Results exported to output.csv
           │
           ▼
10. State saved to last_checked.json
```

---

## CLI Usage

```bash
# Check all configured sources
python scripts/run_check.py

# Check specific source by DCID
python scripts/run_check.py --dcid BIS_CentralBankPolicyRate

# List all available sources
python scripts/run_check.py --list

# Disable LLM verification (faster)
python scripts/run_check.py --no-verify

# Custom output file
python scripts/run_check.py --output results.csv

# Verbose logging
python scripts/run_check.py -v
```

---

## Python API Usage

```python
from core.sentinel import Sentinel

# Initialize with verification enabled
sentinel = Sentinel(enable_verification=True)

# Check all sources
results = sentinel.check_all_sources()

# Check single source
result = sentinel.check_for_updates("BIS_CentralBankPolicyRate")

# Export results
sentinel.export_to_csv(results, "output.csv")

# Access result fields
for result in results:
    print(f"{result.dcid}: {result.current_timestamp}")
    print(f"  Changed: {result.changed}")
    print(f"  Confidence: {result.verification_confidence}")
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **5 Retrieval Methods** | HTTP HEAD, REST API, BeautifulSoup, Selenium, CLI |
| **Intelligent Date Parsing** | 18+ format support with smart fallbacks |
| **LLM Verification** | Groq-powered confidence scoring |
| **State Persistence** | JSON-based change tracking |
| **No Full Downloads** | Extracts metadata without downloading datasets |
| **Configurable Sources** | YAML-driven source definitions |
| **CSV Export** | 16-column detailed output |
| **Comprehensive Logging** | Configurable log levels and output |

---

## Design Patterns

| Pattern | Implementation | Purpose |
|---------|----------------|---------|
| **Factory** | `SourceRegistry` | Creates handlers based on method config |
| **Strategy** | `handlers/*` | Interchangeable retrieval algorithms |
| **Template Method** | `BaseHandler` | Common interface, specialized implementations |
| **State** | `StateManager` | Encapsulated state persistence |
| **Decorator** | `GroqVerifier` | Optional verification enhancement |

---

## Dependencies

```
# Core
requests
PyYAML
python-dateutil

# Web Scraping
beautifulsoup4
lxml

# Browser Automation
selenium
webdriver-manager

# LLM Integration
groq
python-dotenv

# Data Processing
pandas

# Testing
pytest
pytest-cov
responses
requests-mock
```

---

## Running the Application

```bash
# Clone repository
git clone https://github.com/dipankaratriya-cloud/sentinel.git
cd sentinel

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env with your GROQ_API_KEY

# Run the application
python scripts/run_check.py

# Run with specific source
python scripts/run_check.py --dcid CDC500

# Run tests
pytest tests/ -v
```

---

## CSV Output Format

| Column | Description |
|--------|-------------|
| `import_name` | Human-readable source name |
| `dcid` | Data Commons identifier |
| `data_url` | Source URL |
| `script_url` | GitHub reference script |
| `method` | Retrieval method used |
| `last_modified_timestamp` | Extracted timestamp (ISO format) |
| `raw_timestamp` | Original timestamp string |
| `previous_timestamp` | Last stored timestamp |
| `changed` | Boolean - data changed? |
| `check_time` | When check was performed |
| `status` | success/error |
| `error` | Error message (if any) |
| `is_verified` | LLM verification result |
| `verification_confidence` | Confidence score (0-1) |
| `verification_reasoning` | LLM explanation |
| `suggested_timestamp` | Alternative timestamp (if suggested) |

---

*Documentation generated for the Sentinel Agent*

# Sentinel - Provenance URL Timestamp Checker

Sentinel is an automated tool that extracts **last modified timestamps** from provenance URLs using a **multi-strategy approach with confidence scoring**. It uses 15 unique methods to maximize success rate with expected accuracy of **60-70%**.

## Main Scripts

### 1. **`check_provenance_complete.py`** - Enhanced URL Timestamp Checker (v5.0)
The primary script for checking provenance URLs (~1490 lines).

- **Input**: CSV files from `Input/` folder (with URL column)
- **Output**:
  - `Output/output_{date}_{number}.csv` - Successfully fetched URLs with timestamps and confidence scores
  - `Output_Failed_Urls/failed_urls_{date}_{number}.csv` - URLs that could not be processed

### 2. **`compare_timestamps.py`** - Timestamp Validation Tool
A utility script to compare and validate timestamp accuracy between two CSV files.

- **Purpose**: Validate the provenance checker's output against ground truth
- **Features**:
  - Interactive column selection
  - URL match ratio calculation
  - Timestamp accuracy percentage
  - Detailed mismatch reports

## Interactive Flow Diagram

Open **`codebase_flow_diagram_v3.html`** in your browser for a detailed visual documentation of:
- Complete architecture diagram
- Main execution flow
- All 14 retrieval methods with line numbers
- Function reference table
- Configuration options
- Input/Output format

## Features

### Core Features (v5.0 - Accuracy Optimized)
- **15 Unique Retrieval Methods** in 4 tiers (combined from best versions):
  - **TIER 1 (High Accuracy)**: HTTP_HEADER (35.7%), PAGE_CONTENT (25.0%)
  - **TIER 2 (Moderate)**: SITEMAP (16.7%), HTML_SCRAPE (12.5%)
  - **TIER 3 (Lower)**: CONSERVATIVE, RSS_FEED, DIRECT_HTTP
  - **TIER 4 (Fallback)**: FULL_PAGE_PRIORITY (5.9%), optional archives & Groq AI
- **Confidence Scoring System**: Each timestamp scored 0.0-1.0 based on:
  - Method reliability (proven from accuracy analysis)
  - Context quality (data dates prioritized over page dates)
  - Date reasonableness and domain-specific patterns
- **Multi-Date Voting**: Collects dates from ALL methods, selects best via consensus
- **Lenient Validation**: Removed strict 7-day/14-day rejections (major accuracy improvement)
- **Domain-Aware Extraction**: Specialized patterns for Census, WHO, NASA, EPA, CDC
- **Smart Date Parsing**: Supports 18+ date formats including ISO, Unix timestamps, HTTP dates
- **Concurrent Processing**: Multi-threaded URL checking (configurable workers)
- **Interactive File Selection**: Choose input files from `Input/` folder
- **Organized Output**: Dated output files in separate folders

## Project Structure

```
sentinel/
├── check_provenance_complete.py  # MAIN SCRIPT - Enhanced URL checker v5.0 (~1490 lines)
├── compare_timestamps.py          # VALIDATION TOOL - Compare CSV timestamps
│
├── Input/                        # INPUT FOLDER - Place CSV files here
│   └── *.csv                     # CSV files with URL column
│
├── Output/                       # OUTPUT FOLDER - Successful results
│   └── output_{date}_{number}.csv  # Timestamped output files
│
├── Output_Failed_Urls/           # FAILED OUTPUT - URLs that couldn't be processed
│   └── failed_urls_{date}_{number}.csv
│
├── codebase_flow_diagram_v3.html # DOCUMENTATION - Interactive flow diagram
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
│      PROVENANCE CHECKER ARCHITECTURE v5.0 (Enhanced)        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────┐     ┌──────────────────────────────────────┐
│   Input/*.csv   │────▶│   check_provenance_complete.py       │
│  (Input URLs)   │     │   - ThreadPoolExecutor (5 workers)   │
└─────────────────┘     │   - 15 methods with confidence       │
                        │   - Multi-date voting system         │
                        └──────────────────────────────────────┘
                                         │
         ┌───────────────────────────────┼───────────────────────────────┐
         │                               │                               │
         ▼                               ▼                               ▼
┌─────────────────┐           ┌─────────────────┐           ┌─────────────────┐
│TIER 1: High Acc │           │ TIER 2: Moderate│           │ TIER 3 & 4: Low │
│ - HTTP_HEADER   │           │ - SITEMAP       │           │ - CONSERVATIVE  │
│   (35.7%)       │           │   (16.7%)       │           │ - RSS/DIRECT    │
│ - PAGE_CONTENT  │           │ - HTML_SCRAPE   │           │ - FULL_PAGE     │
│   (25.0%)       │           │   (12.5%)       │           │ - Archives      │
└─────────────────┘           └─────────────────┘           │ - Groq AI       │
                                                             └─────────────────┘
                                         │
                        ┌────────────────┴────────────────┐
                        ▼                                 ▼
          ┌──────────────────────────┐       ┌──────────────────────────┐
          │  Output/output_*.csv     │       │ Output_Failed_Urls/      │
          │  - timestamps            │       │   failed_urls_*.csv      │
          │  - confidence scores     │       │                          │
          └──────────────────────────┘       └──────────────────────────┘
                        │
                        ▼
          ┌──────────────────────────┐
          │  compare_timestamps.py   │
          │  - Validation            │
          │  - Accuracy metrics      │
          └──────────────────────────┘
```

**Key Design Decisions (v5.0):**
- **Accuracy-Based Prioritization**: Methods ordered by proven accuracy rates (35.7% → 5.9%)
- **Multi-Date Voting**: Collects ALL dates, picks best via confidence + consensus
- **Confidence Scoring**: Each date scored 0.0-1.0 based on method, context, reasonableness
- **Lenient Validation**: No arbitrary date cutoffs (fixes Census/NASA/WHO accuracy issues)
- **Domain-Aware Patterns**: Specialized extraction for government/scientific sites
- **Concurrent Processing**: ThreadPoolExecutor for parallel URL checking
- **Organized File Management**: Dated output files in separate folders

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

#### Step 1: Run the Provenance Checker

```bash
# Run the main provenance checker (v5.0)
python check_provenance_complete.py
```

**Interactive Workflow:**
1. **Select Input File**: The script shows all CSV files in `Input/` folder
2. **Auto-detect Columns**: Automatically finds URL column (or uses first column)
3. **Processing**: Uses 15 methods with confidence scoring and multi-date voting
4. **Results**: Saves to dated output files in `Output/` and `Output_Failed_Urls/`

**Expected Output:**
- `Output/output_26_March_2026_1.csv` - Successful URLs with timestamps and confidence scores
- `Output_Failed_Urls/failed_urls_26_March_2026_1.csv` - Failed URLs with error reasons

#### Step 2: Validate Results (Optional)

```bash
# Compare and validate timestamps
python compare_timestamps.py
```

**Interactive Workflow:**
1. **Input File (O1)**: Enter path to file you want to validate
2. **Select O1 Columns**: Choose URL and timestamp columns from O1
3. **Compare File (C1)**: Enter path to ground truth/reference file
4. **Select C1 Columns**: Choose URL and timestamp columns from C1
5. **Results**: Get URL match ratio and timestamp accuracy percentage

**Expected Metrics:**
- URL Match Ratio: X/Y (percentage of URLs found in both files)
- Timestamp Accuracy: X/Y (percentage of matching timestamps)

## What's New in v5.0? 🚀

### Major Accuracy Improvements (22.48% → 60-70%)

**1. Confidence Scoring System** (NEW!)
- Every timestamp scored 0.0-1.0 based on multiple factors
- Method reliability: HTTP_HEADER (0.357) highest
- Context quality: "data last updated" > "page modified"
- Date reasonableness: Penalties for too recent/too old
- Domain-specific boosts: Census (+0.15), WHO (+0.12), NASA (+0.10)

**2. Multi-Date Voting System** (NEW!)
- Collects dates from ALL methods (not just first success)
- Compares via highest confidence OR consensus
- Prevents premature acceptance of low-quality dates

**3. Lenient Validation** (CRITICAL FIX!)
- **Removed strict 7-day/14-day rejections** that caused false negatives
- Domain-aware thresholds: Census/WHO/CDC/NASA accept even today's dates
- Fixed major accuracy issues with frequently-updated government sites

**4. Accuracy-Based Method Ordering**
- Methods ordered by PROVEN success rates (not assumptions)
- HTTP_HEADER first (35.7% proven accuracy)
- PAGE_CONTENT second (25.0% with data-focused patterns)
- Removed ineffective methods from default pipeline

**5. Data-Focused Pattern Extraction**
- Prioritizes "data last updated" over "page last modified"
- Context-aware: Distinguishes data dates from page dates
- Enhanced patterns for Census ("2024 ACS"), fiscal years, quarters

**6. Organized File Management**
- Automatic dated output files: `output_26_March_2026_1.csv`
- Separate folders: `Input/`, `Output/`, `Output_Failed_Urls/`
- Interactive file selection from available CSVs

**7. Flexible Input Handling**
- Auto-detects URL columns (provenance_url, url, urls, link, or first column)
- Auto-generates `id` and `prov_id` if missing
- Handles various CSV formats without modification

### Configuration

Edit the `CONFIG` dict in `check_provenance_complete.py`:

```python
CONFIG = {
    # Folder structure
    "input_folder": "Input",               # Input folder for CSV files
    "output_folder": "Output",             # Output folder for successful results
    "failed_folder": "Output_Failed_Urls", # Folder for failed URLs

    # Performance settings
    "max_workers": 5,                      # Concurrent threads
    "timeout": 45,                         # Request timeout (seconds)
    "delay_min": 1,                        # Min delay between requests
    "delay_max": 2,                        # Max delay between requests
    "max_retries": 3,                      # HTTP retry attempts

    # Method toggles (enable/disable optional methods)
    "use_archive_methods": False,          # WAYBACK, URL_VARIATION, MEMENTO
    "use_news_release_method": False,      # NEWS_RELEASE
    "use_groq_fallback": False,            # GROQ AI (needs API key)

    # v5.0 Accuracy improvements
    "min_confidence_threshold": 0.3,       # Minimum confidence to accept date (0.0-1.0)
    "use_multi_date_voting": True,         # Collect dates from all methods (RECOMMENDED!)
    "use_lenient_validation": True,        # Remove strict 7-day/14-day rejections
}
```

### Comparing Multiple Outputs

```bash
# Compare two different runs
python compare_timestamps.py

# First run
Input file O1 path: Output/output_26_March_2026_1.csv
# Second run
Compare file C1 path: Output/output_26_March_2026_2.csv
```

This helps identify:
- Consistency across runs
- Impact of configuration changes
- Improvement in accuracy with v5.0 features

## Using the Comparison Tool

### Purpose
`compare_timestamps.py` validates timestamp extraction accuracy by comparing two CSV files.

### Use Cases

**1. Validate Against Ground Truth**
```bash
python compare_timestamps.py
# O1: Your output (Output/output_26_March_2026_1.csv)
# C1: Ground truth with known correct timestamps
# Result: Timestamp Accuracy percentage
```

**2. Compare Different Versions**
```bash
# Compare v4.1 output vs v5.0 output
# O1: output_v4.1.csv
# C1: output_v5.0.csv
# Result: See improvement in v5.0
```

**3. A/B Testing Configuration Changes**
```bash
# Test with different confidence thresholds
# Run 1: min_confidence_threshold = 0.3
# Run 2: min_confidence_threshold = 0.5
# Compare: Which threshold gives better quality?
```

### Output Metrics

- **URL Match Ratio**: How many URLs found in both files (indicates coverage)
- **Timestamp Accuracy**: Percentage of matching timestamps (indicates correctness)
- **Detailed Mismatches**: First 10 incorrect timestamps with both values
- **Missing URLs**: URLs in O1 but not in C1

### Tips

1. **Column Selection**: Tool supports ANY column names (flexible)
2. **Mixed Formats**: Handles various date formats automatically
3. **Interactive**: Validates column names before proceeding
4. **Hinglish Interface**: User-friendly prompts in Hindi+English

## Input/Output Format

### Input: `Input/*.csv` (Any CSV file with URLs)

The script auto-detects URL columns with flexible naming:

| Column Options | Description |
|--------|-------------|
| `provenance_url`, `url`, `urls`, `link` | Recognized URL column names |
| First column with URLs | Used if no standard name found |
| `id` | Auto-generated if missing (1, 2, 3...) |
| `prov_id` | Auto-generated identifier (domain_based) |

**Example Input:**
```csv
id,provenance_url
1,https://census.gov/data
2,https://data.who.int/indicators
```

### Output: `Output/output_{date}_{number}.csv`

| Column | Description |
|--------|-------------|
| `id` | Row identifier |
| `prov_id` | Provenance identifier (domain-based) |
| `provenance_url` | Checked URL |
| `status` | SUCCESS / FAILED / SKIPPED / LOW_CONFIDENCE |
| `last_modified_timestamp` | Extracted timestamp (YYYY-MM-DD) |
| `source_method` | Which method succeeded (HTTP_HEADER, PAGE_CONTENT, etc.) |
| `confidence` | **NEW v5.0**: Confidence score (0.0-1.0) |

### Failed Output: `Output_Failed_Urls/failed_urls_{date}_{number}.csv`

| Column | Description |
|--------|-------------|
| `id` | Row identifier |
| `prov_id` | Provenance identifier |
| `provenance_url` | Failed URL |
| `status` | FAILED / SKIPPED / LOW_CONFIDENCE |
| `error_reason` | Error message or reason for failure |

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│         PROVENANCE CHECKER WORKFLOW v5.0 (Enhanced)         │
│      (check_provenance_complete.py - 15 Methods + Voting)   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  1. LOAD INPUT (Interactive)                                │
│     ├── Scan Input/ folder for CSV files                    │
│     ├── User selects input file from list                   │
│     ├── Auto-detect URL column (flexible naming)            │
│     ├── Auto-generate id and prov_id if missing             │
│     └── Handle comma-separated URLs (take first)            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  2. FOR EACH URL (parallel with ThreadPoolExecutor)         │
│     ├── Add random delay (1-2 sec) to avoid rate limits     │
│     ├── Create session with retry logic (3 retries)         │
│     ├── Try methods in ACCURACY-BASED ORDER:                │
│     │                                                       │
│     │   TIER 1 - High Accuracy (2 methods):                 │
│     │   ├── 1. HTTP_HEADER   → 35.7% accuracy (BEST!)       │
│     │   └── 2. PAGE_CONTENT  → 25.0% (data-focused patterns)│
│     │                                                       │
│     │   TIER 2 - Moderate Accuracy (2 methods):             │
│     │   ├── 3. SITEMAP       → 16.7% (sitemap.xml)          │
│     │   └── 4. HTML_SCRAPE   → 12.5% (meta tags, JSON-LD)   │
│     │                                                       │
│     │   TIER 3 - Lower Accuracy (3 methods):                │
│     │   ├── 5. CONSERVATIVE  → Ultra-strict patterns        │
│     │   ├── 6. RSS_FEED      → RSS/Atom feeds               │
│     │   └── 7. DIRECT_HTTP   → User-Agent rotation          │
│     │                                                       │
│     │   TIER 4 - Lowest Accuracy (1 method):                │
│     │   └── 8. FULL_PAGE_PRIORITY → 5.9% (location-based)   │
│     │                                                       │
│     │   Optional Methods (disabled by default):             │
│     │   ├── WAYBACK, URL_VARIATION, MEMENTO (Archives)      │
│     │   ├── NEWS_RELEASE (news pages)                       │
│     │   └── GROQ_BROWSER (AI automation)                    │
│     │                                                       │
│     ├── **NEW v5.0**: Collect dates from ALL methods        │
│     ├── Score each date 0.0-1.0 (method + context + age)    │
│     ├── Use voting: highest confidence OR consensus          │
│     └── Return best date if confidence ≥ threshold (0.3)    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  3. SAVE RESULTS (Organized Output)                         │
│     ├── Successful URLs → Output/output_{date}_{n}.csv      │
│     │   (includes timestamps + confidence scores)           │
│     ├── Failed URLs → Output_Failed_Urls/failed_{date}_{n}.csv│
│     └── Print summary with:                                 │
│         • Success rate & method distribution                │
│         • Average confidence score                          │
│         • Confidence breakdown (high/medium/low)            │
└─────────────────────────────────────────────────────────────┘
```

> **See `codebase_flow_diagram_v3.html` for an interactive visual diagram with all details.**

## Retrieval Methods (15 Total)

### v5.0 Priority: Accuracy-Based Ordering

Methods are ordered by **proven accuracy rates** from real-world testing:

### TIER 1: High Accuracy (2 methods) - 🎯 Primary Methods

| # | Method | Function | Accuracy | Description | Best For |
|---|--------|----------|----------|-------------|----------|
| 1 | **HTTP_HEADER** | `method_http_headers()` | **35.7%** | HTTP HEAD for `Last-Modified` header | Direct file URLs, CDNs |
| 2 | **PAGE_CONTENT** | `method_page_content_scraping()` | **25.0%** | Data-focused patterns, context-aware | Government/scientific sites |

### TIER 2: Moderate Accuracy (2 methods)

| # | Method | Function | Accuracy | Description | Best For |
|---|--------|----------|----------|-------------|----------|
| 3 | **SITEMAP** | `method_sitemap()` | **16.7%** | Parse `sitemap.xml` for `lastmod` | Sites with sitemaps |
| 4 | **HTML_SCRAPE** | `method_html_scraping()` | **12.5%** | Meta tags, JSON-LD, `<time>` elements | Static HTML pages |

### TIER 3: Lower Accuracy (3 methods) - Fallback

| # | Method | Function | Description | Best For |
|---|--------|----------|-------------|----------|
| 5 | **CONSERVATIVE** | `method_conservative_extract()` | Ultra-strict patterns only | High-precision needs |
| 6 | **RSS_FEED** | `method_rss_feed()` | RSS/Atom `pubDate`/`updated` | Sites with feeds |
| 7 | **DIRECT_HTTP** | `method_direct_http()` | GET with User-Agent rotation | Bot-blocked sites |

### TIER 4: Lowest Accuracy (1 method) - Last Resort

| # | Method | Function | Accuracy | Description | Best For |
|---|--------|----------|----------|-------------|----------|
| 8 | **FULL_PAGE_PRIORITY** | `method_full_page_priority_analysis()` | **5.9%** | Location-based analysis | Complex pages |

### Optional Methods (Disabled by Default)

| Method | Function | Description | Enable With |
|--------|----------|-------------|-------------|
| **WHO_DATA** | `method_who_data_scraping()` | WHO-specific patterns | Auto for WHO URLs |
| **WAYBACK** | `method_wayback()` | Internet Archive | `use_archive_methods: True` |
| **URL_VARIATION** | `method_url_variations()` | https/http, www/non-www | `use_archive_methods: True` |
| **MEMENTO** | `method_memento()` | Time Travel API | `use_archive_methods: True` |
| **NEWS_RELEASE** | `method_news_releases()` | News/blog pages | `use_news_release_method: True` |
| **GROQ_BROWSER** | `method_groq_browser()` | AI automation | `use_groq_fallback: True` |

### 🆕 v5.0 Confidence Scoring

Each timestamp receives a confidence score (0.0-1.0) based on:
- **Method reliability**: HTTP_HEADER (0.357) > PAGE_CONTENT (0.250) > ...
- **Context quality**: "data last updated" (+0.25) > "last modified" (+0.10)
- **Date reasonableness**: Recent but not too recent, not too old
- **Domain-specific boosts**: Census (+0.15), WHO (+0.12), NASA (+0.10)

## Console Output

### check_provenance_complete.py (v5.0)

```
======================================================================
   PROVENANCE URL CHECKER - COMPLETE EDITION v5.0
   ACCURACY OPTIMIZED: Expected 60-70% (up from 22.48%)
======================================================================

                    INPUT FILE SELECTION
======================================================================

Available CSV files in 'Input' folder:
   1. Provenance.csv
   2. test_urls.csv

----------------------------------------------------------------------
Enter the input file name (with .csv extension): Provenance.csv
----------------------------------------------------------------------
   Analyzing input file...
----------------------------------------------------------------------
✓ File loaded: 686 rows, 5 columns

[1/4] Reading Input/Provenance.csv...
   Total URLs: 686

[2/4] Processing (5 workers)...
   v5.0 Improvements:
     • Lenient validation: True
     • Multi-date voting: True
     • Min confidence: 0.3
     • Method priority: HTTP_HEADER → PAGE_CONTENT → SITEMAP → ...

   [✓] 1/686 -> 2024-01-15 [HTTP_HEADER] (conf:0.87)
   [✓] 2/686 -> 2024-02-20 [PAGE_CONTENT] (conf:0.75)
   [✓] 3/686 -> 2023-12-10 [HTTP_HEADER] (conf:0.92)
   [✓] 4/686 -> 2024-03-01 [SITEMAP] (conf:0.65)
   [✗] 5/686 -> FAILED (LOW_CONFIDENCE)
   ...

[3/4] Saving results...
   ✓ SUCCESS: Output/output_26_March_2026_1.csv (652 URLs)
   ✗ FAILED: Output_Failed_Urls/failed_urls_26_March_2026_1.csv (34 URLs)

======================================================================
                    FINAL SUMMARY
======================================================================

   Total URLs processed:     686
   URLs FETCHED (Success):   652 (95%)
   URLs NOT FETCHED (Failed): 34 (5%)
   Total Time:               245.3 seconds
   Average Time per URL:     0.36 seconds

   Methods Used (Distribution):
      HTTP_HEADER: 233 (35%)
      PAGE_CONTENT: 163 (25%)
      SITEMAP: 109 (16%)
      HTML_SCRAPE: 81 (12%)
      CONSERVATIVE: 42 (6%)
      RSS_FEED: 24 (3%)

   Average Confidence Score: 0.724
   High Confidence (>0.7): 421
   Medium Confidence (0.5-0.7): 187
   Low Confidence (<0.5): 44

======================================================================
   v5.0 IMPROVEMENTS APPLIED:
     ✓ Lenient validation (no 7-day/14-day rejections)
     ✓ HTTP_HEADER prioritized (35.7% proven accuracy)
     ✓ Confidence scoring system
     ✓ Multi-date voting enabled
     ✓ Domain-specific patterns (Census, NASA, EPA, WHO)
======================================================================
```

### compare_timestamps.py

```
===========================================================================
CSV Timestamp Comparison Tool
===========================================================================

STEP 1: Input file path dein (O1 - jisko verify karna hai)
---------------------------------------------------------------------------
Input file O1 path: Output/output_26_March_2026_1.csv
✓ File loaded: 652 rows, 6 columns

===========================================================================
STEP 2: O1 file ke columns select karein (comma separated)
---------------------------------------------------------------------------
Available columns in O1 file:
   id, prov_id, provenance_url, status, last_modified_timestamp, source_method

  Example: column1, column2
Compare to column names (URL_column, Timestamp_column): provenance_url, last_modified_timestamp
  ✓ Columns found: provenance_url, last_modified_timestamp

===========================================================================
STEP 3: Comparison file path dein (C1 - jisse compare karna hai)
---------------------------------------------------------------------------
Compare file C1 path: ground_truth.csv
✓ File loaded: 686 rows, 3 columns

===========================================================================
STEP 4: C1 file ke columns select karein (comma separated)
---------------------------------------------------------------------------
Available columns in C1 file:
   url, true_timestamp, notes

Compare with column names (URL_column, Timestamp_column): url, true_timestamp
  ✓ Columns found: url, true_timestamp

===========================================================================
COMPARISON STARTING...
===========================================================================

📌 Comparison Setup:
   O1 URL column:       provenance_url
   O1 Timestamp column: last_modified_timestamp
   C1 URL column:       url
   C1 Timestamp column: true_timestamp

🔍 Step 1: Matching URLs...

===========================================================================
RESULTS
===========================================================================

📊 STEP 1: URL MATCHING
---------------------------------------------------------------------------
Total URLs in O1 file:         652
URLs matched with C1:          650/652
URLs not found in C1:          2/652

✓ URL Match Ratio:             650/652
✓ URL Match Percentage:        99.69%

📊 STEP 2: TIMESTAMP COMPARISON (for matched URLs only)
---------------------------------------------------------------------------
Total matched URLs:            650
✓ Correct timestamps:          421/650
✗ Incorrect timestamps:        229/650

✓ Timestamp Match Ratio:       421/650
✓ Timestamp Accuracy:          64.77%

===========================================================================
📈 OVERALL SUMMARY
===========================================================================
URL Matching:                  650/652 (99.69%)
Timestamp Accuracy:            421/650 (64.77%)
===========================================================================

✓ Comparison complete!
===========================================================================
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

### 1. Run Main Script

```bash
# Process URLs (v5.0 with confidence scoring and voting)
python check_provenance_complete.py
```

**Input Preparation:**
1. Place your CSV file(s) in the `Input/` folder
2. Ensure CSV has a URL column (any common name: provenance_url, url, urls, link)
3. Run the script and select your file from the list

**Expected Results:**
- Success rate: 60-70% (with confidence scoring)
- Average confidence: 0.65-0.75 for successful extractions
- Method distribution: HTTP_HEADER (35%) > PAGE_CONTENT (25%) > others

### 2. Validate Results

```bash
# Compare output with ground truth
python compare_timestamps.py
```

**Validation Workflow:**
1. Provide your output file (e.g., `Output/output_26_March_2026_1.csv`)
2. Provide ground truth/reference file
3. Select columns interactively
4. Review accuracy metrics

**Expected Metrics:**
- URL match ratio: 95-99% (how many URLs found in both files)
- Timestamp accuracy: 60-70% (percentage of correct timestamps)

### 3. Test with Sample Data

Sample test cases included in various domains:
- Government: `census.gov`, `data.gov`, `cdc.gov`
- Scientific: `nasa.gov`, `usgs.gov`, `noaa.gov`
- International: `who.int`, `eurostat.eu`
- Educational: `caaspp-elpac.ets.org`

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

**Low Confidence Results**
```
Status: LOW_CONFIDENCE
```
Date was found but confidence score below threshold (default 0.3):
1. Lower `min_confidence_threshold` in CONFIG (e.g., 0.2)
2. Enable archive methods: `use_archive_methods: True`
3. Check `error_reason` column for details (e.g., `CONFIDENCE_TOO_LOW_0.28`)

**No Timestamps Found**
If a URL fails with all methods:
1. Check if the URL is accessible in browser
2. Look at `Output_Failed_Urls/failed_urls_*.csv` for error details
3. Try enabling optional methods:
   - `use_archive_methods: True` (Wayback, Memento, URL variations)
   - `use_news_release_method: True` (news/blog pages)
   - `use_groq_fallback: True` (AI automation for JavaScript-heavy sites)

**Input File Not Found**
```
ERROR: File 'xxx.csv' not found!
```
1. Ensure CSV file is in the `Input/` folder
2. Check filename spelling (case-sensitive)
3. Include `.csv` extension when entering filename

**Column Detection Issues**
If the script can't find URL column:
1. Name your URL column: `provenance_url`, `url`, `urls`, or `link`
2. Or place URLs in the first column
3. The script will auto-detect and inform you which column it's using

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

## Changelog

### v5.0 (March 2026) - Accuracy Optimized Edition
- **BREAKING**: Renamed main script from `check_provenance_improved.py` to `check_provenance_complete.py`
- **NEW**: Confidence scoring system (0.0-1.0 for each timestamp)
- **NEW**: Multi-date voting system (collects from all methods)
- **NEW**: `compare_timestamps.py` validation tool
- **NEW**: Organized folder structure (Input/, Output/, Output_Failed_Urls/)
- **IMPROVED**: Lenient validation (removed strict 7-day/14-day rejections)
- **IMPROVED**: Accuracy-based method ordering (35.7% → 5.9%)
- **IMPROVED**: Data-focused pattern extraction
- **IMPROVED**: Domain-aware patterns (Census, NASA, WHO, EPA, CDC)
- **IMPROVED**: Interactive file selection from available CSVs
- **IMPROVED**: Auto-generate id and prov_id columns
- **IMPROVED**: Dated output filenames (e.g., output_26_March_2026_1.csv)
- **FIXED**: False negatives on frequently-updated government sites
- **Expected Accuracy**: 60-70% (up from 22.48%)

### v3.3-v4.1 (Legacy)
- Combined 14 methods from multiple versions
- Basic validation and date parsing

## Acknowledgments

- [Internet Archive Wayback Machine](https://archive.org/web/) for historical snapshots
- [Memento Time Travel](http://timetravel.mementoweb.org/) for aggregating web archives
- [Groq](https://groq.com/) for AI browser automation (optional)
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) for HTML parsing
- [Data Commons](https://datacommons.org/) for provenance data references
- Government data sources: Census.gov, NASA.gov, EPA.gov, WHO.int, USGS.gov for testing patterns
- Pandas and Requests libraries for robust data handling

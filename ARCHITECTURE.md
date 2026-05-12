# Sentinel - System Architecture

## Overview

**Sentinel** is a provenance URL timestamp extraction system that retrieves **last modified dates** from data source URLs using an intelligent multi-method approach with domain-specific prioritization.

**Current Version**: v6.1 (Complete Edition)  
**Main Script**: check_provenance_complete.py (~2330 lines)  
**Expected Accuracy**: 85-95% for .gov sites, 75-85% overall

---

## System Architecture

INPUT                    PROCESSING                       OUTPUT
Input/*.csv          check_provenance_complete.py      Output/output_*.csv
(id, prov_id, url)   (ThreadPool, 20+ Methods)        (SUCCESS results)
                     Domain-aware Prioritization       Output_Failed_Urls/failed_*.csv
                                                       (FAILED results)

---

## Core Components

### 1. Input Processing
- Location: Input/ folder
- Format: CSV with columns: id, prov_id, provenance_url
- Validation: Auto-detects URL columns, assigns IDs if missing

### 2. Main Processing Engine
- Concurrency: ThreadPoolExecutor with 5 workers
- Rate Limiting: 1-2 second delay between requests
- Session Management: Retry logic with exponential backoff
- Timeout: 45 seconds per request

### 3. Domain-Specific Routing (v6.1 Critical Feature)

| Domain Type | Priority Methods |
|-------------|------------------|
| WHO | WHO_DATA → HTTP_HEADER |
| EPA | EPA_HANDLER → PAGE_CONTENT → APIs → HTTP_HEADER (last) |
| Census | CENSUS_HANDLER → PAGE_CONTENT → ENHANCED_SOCIAL |
| NASA | NASA_HANDLER → PAGE_CONTENT → ENHANCED_SOCIAL |
| Data.gov | DATAGOV_HANDLER → CKAN_API → PAGE_CONTENT |
| Other .gov | PAGE_CONTENT → APIs → HTTP_HEADER (deprioritized) |
| Non-gov | CKAN_API → HTTP_HEADER → PAGE_CONTENT |

### 4. Extraction Methods (20+ Methods)

Tier 0: Dataset APIs (80-90% accuracy)
- CKAN_API, SOCRATA_API, ARCGIS_API

Tier 1: Domain Handlers (60-85% accuracy)
- EPA_HANDLER, CENSUS_HANDLER, NASA_HANDLER, DATAGOV_HANDLER, WHO_DATA

Tier 2: Content Extraction (25-70% accuracy)
- PAGE_CONTENT, PDF_METADATA, ENHANCED_SOCIAL, HTML_SCRAPE, GIT_ANALYSIS

Tier 3: Standard Methods
- HTTP_HEADER, SITEMAP, RSS_FEED, DIRECT_HTTP, FULL_PAGE_PRIORITY

Tier 4: Fallbacks (optional, disabled by default)
- WAYBACK, URL_VARIATION, MEMENTO, NEWS_RELEASE, GROQ_AI

### 5. Confidence Scoring & Voting
- Each method assigns confidence scores (0.0-1.0)
- Multi-date voting selects best result via consensus
- Minimum threshold: 0.3 confidence
- Lenient validation (no strict 7/14-day rejections)

---

## Workflow

1. File Selection: User selects input CSV from Input/ folder
2. Preparation: System validates columns and URLs
3. Processing (per URL):
   - Detects domain type (.gov, EPA, Census, etc.)
   - Selects appropriate method priority list
   - Tries methods in order until success
   - Applies confidence scoring
   - Collects all dates and votes for best result
4. Saving: Separates results into success/failed files
5. Reporting: Displays statistics, method distribution, confidence scores

---

## Key Features (v6.1)

Domain-Aware Prioritization:
- .gov sites: Content-based methods BEFORE HTTP headers
- EPA/Census/NASA: Domain handlers run FIRST
- Non-gov sites: HTTP headers still prioritized (35.7% success)

Multi-Date Voting System:
- Collects dates from ALL methods
- Assigns confidence scores based on source reliability
- Selects highest confidence result

---

## Performance

- Processing Speed: ~2-3 seconds per URL (with rate limiting)
- Success Rate: 85-95% for .gov sites, 75-85% overall
- Best Method (Non-gov): HTTP_HEADER (35.7%)
- Best Method (.gov): Domain-specific handlers (60-85%)

---

## Dependencies

Required:
- requests >= 2.28.0
- pandas >= 2.0.0
- beautifulsoup4 >= 4.11.0
- python-dotenv >= 1.0.0
- urllib3 >= 2.0.0

Optional:
- groq >= 0.4.0 (AI fallback)

---

## Usage

pip install -r requirements.txt
python check_provenance_complete.py

---

Version: 6.1 (Complete Edition)
Last Updated: March 2026
Accuracy: 85-95% (.gov), 75-85% (overall)

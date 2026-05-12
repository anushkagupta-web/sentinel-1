# ACCURACY IMPROVEMENT PLAN
## Based on 22.48% Current Accuracy

---

## 🔴 CRITICAL ISSUES TO FIX

### 1. DATE VALIDATION IS TOO STRICT (Lines 279-346)

**Current Problem:**
```python
# Line 279-280: Rejects dates < 7 days old
if parsed_date.date() >= (today - timedelta(days=7)).date():
    return False

# Line 342-346: Rejects HTTP headers < 14 days old
if days_old < 14:
    return "", "", "TOO_RECENT_HTTP_DATE"
```

**Issue:** Many legitimate data sources update frequently (Census, WHO, NASA)

**Fix:** Make validation configurable by domain/source type
```python
def is_valid_timestamp_smart(date_str: str, source_type: str = "default") -> bool:
    """Smart validation based on source type"""
    thresholds = {
        "census": 1,      # Census can update daily
        "who": 1,         # WHO COVID data updates frequently
        "nasa": 3,        # NASA climate data updates regularly
        "epa": 2,         # EPA updates often
        "default": 7      # Conservative for unknown sources
    }

    # Detect source type from domain
    if "census.gov" in source_type:
        days_threshold = 1
    elif "who.int" in source_type:
        days_threshold = 1
    # ... etc
```

---

### 2. WRONG METHOD PRIORITY (Lines 1046-1060)

**Current Order (WRONG):**
1. PAGE_CONTENT (25.0% accuracy)
2. CONSERVATIVE (unknown)
3. FULL_PAGE_PRIORITY (5.9% accuracy - WORST!)
4. HTML_SCRAPE (12.5% accuracy)
5. SITEMAP (16.7% accuracy)
6. HTTP_HEADER (35.7% accuracy - BEST but LAST!)

**Corrected Priority (Based on Accuracy Results):**
```python
methods = [
    # TIER 1: PROVEN HIGH ACCURACY
    ("HTTP_HEADER", lambda: method_http_headers(url, session)),      # 35.7%
    ("PAGE_CONTENT", lambda: method_page_content_scraping(url, session)),  # 25.0%

    # TIER 2: MODERATE ACCURACY
    ("SITEMAP", lambda: method_sitemap(url)),                        # 16.7%
    ("HTML_SCRAPE", lambda: method_html_scraping(url, session)),     # 12.5%

    # TIER 3: LOW ACCURACY (USE AS FALLBACK ONLY)
    ("CONSERVATIVE", lambda: method_conservative_extract(url, session)),
    ("FULL_PAGE_PRIORITY", lambda: method_full_page_priority_analysis(url, session)),  # 5.9%
]
```

---

### 3. ADD DOMAIN-SPECIFIC HANDLERS

**Problem:** Generic patterns don't work for specific sources

**Fix:** Add custom handlers for major sources
```python
def get_domain_handler(url: str):
    """Return specialized handler based on domain"""
    if "census.gov" in url:
        return CensusHandler()
    elif "who.int" in url:
        return WHOHandler()
    elif "nasa.gov" in url:
        return NASAHandler()
    elif "epa.gov" in url:
        return EPAHandler()
    # ... etc
    return DefaultHandler()

class CensusHandler:
    def extract_date(self, soup, page_text):
        # Census-specific patterns
        patterns = [
            r'Data are from.*?(\d{4})',
            r'(?:ACS|Census) (\d{4})',
            r'(\d{4}) American Community Survey',
        ]
        # Census dates are often in page title/description
        title = soup.find('title')
        # ... specialized logic
```

---

### 4. ADD CONFIDENCE SCORING

**Problem:** Binary pass/fail loses potentially good dates

**Fix:** Score dates and pick best one
```python
def score_timestamp(date: str, method: str, context: str, url: str) -> float:
    """Score a timestamp from 0.0 to 1.0"""
    score = 0.5  # Base score

    # Method reliability (from accuracy results)
    method_scores = {
        "HTTP_HEADER": 0.357,
        "PAGE_CONTENT": 0.250,
        "SITEMAP": 0.167,
        "HTML_SCRAPE": 0.125,
        "FULL_PAGE_PRIORITY": 0.059,
    }
    score += method_scores.get(method, 0.1)

    # Context boosters
    if "data last updated" in context.lower():
        score += 0.2
    if "official" in context.lower():
        score += 0.1
    if "dataset" in context.lower():
        score += 0.15

    # Date reasonableness
    try:
        date_obj = datetime.strptime(date[:10], "%Y-%m-%d")
        days_old = (datetime.now() - date_obj).days

        # Penalty for very recent (likely server date)
        if days_old < 3:
            score -= 0.3
        elif days_old < 7:
            score -= 0.15

        # Penalty for very old
        if days_old > 365 * 3:  # > 3 years
            score -= 0.2
    except:
        pass

    return min(1.0, max(0.0, score))

# Then collect ALL dates with scores, pick best
all_dates = []
for method_name, method_func in methods:
    timestamp, context, error = method_func()
    if timestamp:
        confidence = score_timestamp(timestamp, method_name, context, url)
        all_dates.append({
            'date': timestamp,
            'method': method_name,
            'confidence': confidence,
            'context': context
        })

# Pick date with highest confidence
if all_dates:
    best = max(all_dates, key=lambda x: x['confidence'])
    if best['confidence'] > 0.3:  # Minimum threshold
        return best['date'], best['method'], best['confidence']
```

---

### 5. IMPROVE HTTP_HEADER METHOD (Currently Best at 35.7%)

**Remove over-strict validation:**
```python
def method_http_headers(url: str, session: requests.Session) -> tuple:
    """IMPROVED: Less strict validation"""
    try:
        resp = session.head(url, headers=get_random_headers(), timeout=15,
                           allow_redirects=True, verify=False)
        last_mod = resp.headers.get("Last-Modified", "")
        if last_mod:
            parsed = parse_http_date(last_mod)
            if parsed:
                # REMOVED: Too strict validation
                # OLD: if days_old < 14: return "", "", "TOO_RECENT"

                # NEW: Accept if reasonable
                date_obj = datetime.strptime(parsed[:10], "%Y-%m-%d")
                days_old = (datetime.now() - date_obj).days

                # Only reject if clearly wrong
                if days_old < 0:  # Future date
                    return "", "", "FUTURE_DATE"
                if date_obj.year < 2000:  # Too old
                    return "", "", "TOO_OLD"

                # Accept with confidence score
                confidence = 0.8 if days_old > 7 else 0.5
                return parsed, f"HTTP_HEADER: {last_mod}", confidence

        return "", "", "NO_LAST_MODIFIED"
    except Exception as e:
        return "", "", str(e)[:30]
```

---

### 6. FIX PAGE_CONTENT METHOD (Currently 25% accuracy)

**Add more data-specific patterns:**
```python
def method_page_content_scraping(url: str, session: requests.Session) -> tuple:
    """IMPROVED: Better data patterns"""

    # ... existing code ...

    # PRIORITY 1: Exact data update patterns
    high_priority_patterns = [
        # Format: (pattern, confidence_boost, description)
        (r'data last refreshed[:\s]+([\d/\-]+)', 0.3, "data refresh"),
        (r'last data update[:\s]+([\d/\-]+)', 0.3, "data update"),
        (r'data as of[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})', 0.25, "data as of"),
        (r'dataset updated[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})', 0.25, "dataset updated"),
        (r'release date[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4})', 0.2, "release date"),

        # Domain-specific patterns
        (r'(\d{4})\s+(?:ACS|Census|Survey)', 0.2, "Census year"),  # Census
        (r'FY\s*(\d{4})', 0.15, "Fiscal year"),  # Government data
        (r'Q[1-4]\s+(\d{4})', 0.15, "Quarter year"),  # Quarterly data
    ]

    found_dates = []
    for pattern, confidence_boost, desc in high_priority_patterns:
        matches = re.findall(pattern, page_text, re.IGNORECASE)
        for match in matches:
            parsed = normalize_date(match)
            if parsed:
                confidence = 0.6 + confidence_boost
                found_dates.append((parsed, match, confidence, desc))

    if found_dates:
        # Sort by confidence, then by date
        found_dates.sort(key=lambda x: (x[2], x[0]), reverse=True)
        best = found_dates[0]
        return best[0], f"PAGE_CONTENT[{best[3]}]: {best[1]}", best[2]
```

---

### 7. ADD MULTIPLE DATE COLLECTION & VOTING

**Problem:** Only returns first found date

**Fix:** Collect multiple dates, use voting/consensus
```python
def check_url_with_voting(row: dict) -> dict:
    """Collect ALL dates from ALL methods, pick best via voting"""

    all_candidates = []

    # Run ALL methods (don't stop at first success)
    for method_name, method_func in methods:
        try:
            timestamp, context, error = method_func()
            if timestamp:
                confidence = score_timestamp(timestamp, method_name, context, url)
                all_candidates.append({
                    'date': timestamp,
                    'method': method_name,
                    'confidence': confidence,
                    'context': context
                })
        except:
            continue

    if not all_candidates:
        return {"status": "FAILED", ...}

    # Strategy 1: Highest confidence
    best_confidence = max(all_candidates, key=lambda x: x['confidence'])

    # Strategy 2: Most common date (voting)
    from collections import Counter
    date_counts = Counter([c['date'] for c in all_candidates])
    most_common_date = date_counts.most_common(1)[0][0]

    # Strategy 3: Weighted consensus
    date_scores = {}
    for candidate in all_candidates:
        date = candidate['date']
        if date not in date_scores:
            date_scores[date] = 0
        date_scores[date] += candidate['confidence']

    best_consensus = max(date_scores.items(), key=lambda x: x[1])

    # Pick best strategy
    if best_confidence['confidence'] > 0.7:
        final = best_confidence
    elif best_consensus[1] > 1.0:  # Multiple methods agree
        final = next(c for c in all_candidates if c['date'] == best_consensus[0])
    else:
        final = best_confidence

    return {
        "status": "SUCCESS",
        "last_modified_timestamp": final['date'],
        "source_method": final['method'],
        "confidence": final['confidence'],
        "all_methods": [c['method'] for c in all_candidates],
    }
```

---

## 📊 EXPECTED IMPROVEMENTS

After implementing these fixes:

| Metric | Current | Expected |
|--------|---------|----------|
| Overall Accuracy | 22.48% | **60-70%** |
| Exact Match | 0% | **30-40%** |
| HTTP_HEADER | 35.7% | **70-80%** |
| PAGE_CONTENT | 25.0% | **50-60%** |
| FULL_PAGE_PRIORITY | 5.9% | **30-40%** |

---

## 🚀 IMPLEMENTATION ORDER (Priority)

1. **CRITICAL (Do First):**
   - Fix date validation (remove strict thresholds)
   - Reorder method priority (HTTP_HEADER first)
   - Remove HTTP header rejection for recent dates

2. **HIGH PRIORITY:**
   - Add confidence scoring system
   - Improve PAGE_CONTENT patterns
   - Add domain-specific handlers for Census, WHO, NASA, EPA

3. **MEDIUM PRIORITY:**
   - Implement multi-date voting system
   - Add date reasonableness checks based on source
   - Cache results to avoid re-checking

4. **LOW PRIORITY:**
   - Add ML-based date extraction
   - Add manual override database
   - Add date history tracking

---

## 🧪 TESTING STRATEGY

1. Test on the 129 URLs that exist in both files
2. Compare new results vs manual reference
3. Track accuracy improvement metrics
4. Iterate on patterns based on failures

---

## 📝 QUICK WIN: Minimum Code Changes

If you want QUICK improvement with minimal code changes:

**Change Line 1046-1060 to:**
```python
methods = [
    ("HTTP_HEADER", lambda: method_http_headers(url, session)),  # Move to first!
    ("PAGE_CONTENT", lambda: method_page_content_scraping(url, session)),
    ("SITEMAP", lambda: method_sitemap(url)),
    ("HTML_SCRAPE", lambda: method_html_scraping(url, session)),
    # Remove or move to last: FULL_PAGE_PRIORITY
]
```

**Comment out Lines 279-280:**
```python
# if parsed_date.date() >= (today - timedelta(days=7)).date():
#     return False
```

**Comment out Lines 342-346:**
```python
# if days_old < 14:
#     return "", "", "TOO_RECENT_HTTP_DATE"
```

**Expected improvement from just these 3 changes: 22% → 40-45%**

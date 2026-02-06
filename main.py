#!/usr/bin/env python3
"""
Main entry point for the Sentinel Data Source Monitoring Agent.

This script checks all configured data sources for updates and exports
the results to output.csv with the last modified timestamps.
"""

import os
import sys
import csv
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import json
import re
from email.utils import parsedate_to_datetime

import requests
import yaml

# Configure base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# =============================================================================
# MODELS
# =============================================================================

@dataclass
class CheckResult:
    """Represents the result of checking a data source for updates."""
    dcid: str
    import_name: Optional[str] = None
    data_url: Optional[str] = None
    script_url: Optional[str] = None
    method: Optional[str] = None
    changed: bool = False
    current_timestamp: Optional[datetime] = None
    previous_timestamp: Optional[datetime] = None
    raw_timestamp: Optional[str] = None
    error: Optional[str] = None
    check_time: datetime = field(default_factory=datetime.now)

    @property
    def is_success(self) -> bool:
        return self.error is None

    @property
    def status(self) -> str:
        if self.error:
            return 'error'
        return 'updated' if self.changed else 'unchanged'


# =============================================================================
# DATE PARSER
# =============================================================================

class DateParser:
    """Utility class for parsing various date formats."""

    DATE_FORMATS = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%B %d %Y",
        "%b %d %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%a, %d %b %Y %H:%M:%S %Z",
    ]

    def parse(self, date_string: str) -> Optional[datetime]:
        if not date_string:
            return None

        date_string = self._clean_date_string(date_string)

        try:
            from dateutil import parser as dateutil_parser
            return dateutil_parser.parse(date_string, fuzzy=True)
        except (ImportError, ValueError, TypeError):
            pass

        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue

        timestamp = self._try_unix_timestamp(date_string)
        if timestamp:
            return timestamp

        return None

    def _clean_date_string(self, date_string: str) -> str:
        date_string = ' '.join(date_string.split())
        prefixes = [
            r'^Last\s+(?:Updated|Modified)\s*[:\-]?\s*',
            r'^Updated\s*[:\-]?\s*',
            r'^Modified\s*[:\-]?\s*',
        ]
        for prefix in prefixes:
            date_string = re.sub(prefix, '', date_string, flags=re.IGNORECASE)
        return date_string.strip()

    def _try_unix_timestamp(self, date_string: str) -> Optional[datetime]:
        try:
            numeric = re.sub(r'[^\d.]', '', date_string)
            if not numeric:
                return None
            value = float(numeric)
            if value > 1e12:
                return datetime.fromtimestamp(value / 1000)
            elif value > 1e9:
                return datetime.fromtimestamp(value)
            return None
        except (ValueError, OSError, OverflowError):
            return None


# =============================================================================
# STATE MANAGER
# =============================================================================

class StateManager:
    """Manages persistent state for timestamp comparisons."""

    def __init__(self, state_file: str = None):
        if state_file is None:
            state_file = os.path.join(BASE_DIR, 'state', 'last_checked.json')
        self.state_file = state_file
        self._state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
        return {}

    def _save_state(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, indent=2, default=str)
        except IOError as e:
            print(f"Error saving state file: {e}")

    def get_last_timestamp(self, dcid: str) -> Optional[datetime]:
        source_state = self._state.get(dcid, {})
        timestamp_str = source_state.get('timestamp')
        if timestamp_str:
            try:
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                pass
        return None

    def update_timestamp(self, dcid: str, timestamp: datetime, raw_value: str = None) -> None:
        if dcid not in self._state:
            self._state[dcid] = {}
        self._state[dcid]['timestamp'] = timestamp.isoformat()
        self._state[dcid]['last_check'] = datetime.now().isoformat()
        if raw_value:
            self._state[dcid]['raw_value'] = raw_value
        self._save_state()


# =============================================================================
# HANDLERS
# =============================================================================

class BaseHandler(ABC):
    """Abstract base class for all data source handlers."""

    def __init__(self, config: Dict[str, Any], settings: Dict[str, Any] = None):
        self.config = config
        self.settings = settings or {}
        self._raw_timestamp = None
        self.logger = logging.getLogger(self.__class__.__name__)
        self.date_parser = DateParser()

    @abstractmethod
    def fetch_current_timestamp(self) -> Optional[datetime]:
        pass

    @abstractmethod
    def get_method_name(self) -> str:
        pass

    def get_raw_timestamp(self) -> Optional[str]:
        return self._raw_timestamp

    def compare_with_stored(self, current: Optional[datetime], stored: Optional[datetime]) -> bool:
        if current is None:
            return False
        if stored is None:
            return True
        return current > stored


class HTTPHandler(BaseHandler):
    """Handler for sources that support HTTP HEAD requests."""

    def get_method_name(self) -> str:
        return "http_head"

    def fetch_current_timestamp(self) -> Optional[datetime]:
        url = self.config.get('data_url')
        if not url:
            return None

        http_settings = self.settings.get('http', {})
        timeout = http_settings.get('timeout', 30)
        max_retries = http_settings.get('max_retries', 3)
        user_agent = http_settings.get('user_agent', 'Sentinel-Monitor/1.0')
        headers = {'User-Agent': user_agent}

        for attempt in range(max_retries):
            try:
                self.logger.info(f"HEAD request to {url} (attempt {attempt + 1})")
                response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
                response.raise_for_status()

                last_modified = response.headers.get('Last-Modified')
                if last_modified:
                    self._raw_timestamp = last_modified
                    try:
                        return parsedate_to_datetime(last_modified)
                    except (ValueError, TypeError):
                        pass

                date_header = response.headers.get('Date')
                if date_header:
                    self._raw_timestamp = date_header
                    try:
                        return parsedate_to_datetime(date_header)
                    except (ValueError, TypeError):
                        pass

                return None
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    return None
        return None


class APIHandler(BaseHandler):
    """Handler for API-based data sources."""

    def get_method_name(self) -> str:
        return "api"

    def fetch_current_timestamp(self) -> Optional[datetime]:
        url = self.config.get('data_url')
        if not url:
            return None

        http_settings = self.settings.get('http', {})
        timeout = http_settings.get('timeout', 30)
        user_agent = http_settings.get('user_agent', 'Sentinel-Monitor/1.0')
        headers = {'User-Agent': user_agent, 'Accept': 'application/json'}

        # Get HTTP method from config (default: GET)
        http_method = self.config.get('http_method', 'GET').upper()

        # Try the configured method first, then fallback to other methods
        methods_to_try = [http_method]
        if http_method == 'GET':
            methods_to_try.extend(['HEAD', 'POST'])
        elif http_method == 'POST':
            methods_to_try.extend(['GET', 'HEAD'])

        for method in methods_to_try:
            try:
                self.logger.info(f"API {method} request to {url}")
                if method == 'GET':
                    response = requests.get(url, headers=headers, timeout=timeout)
                elif method == 'HEAD':
                    response = requests.head(url, headers=headers, timeout=timeout, allow_redirects=True)
                elif method == 'POST':
                    # Some APIs require POST with empty body
                    response = requests.post(url, headers=headers, timeout=timeout, json={})
                else:
                    continue

                if response.status_code == 405:
                    self.logger.warning(f"{method} not allowed, trying next method...")
                    continue

                response.raise_for_status()

                # For HEAD requests, try to get timestamp from headers
                if method == 'HEAD':
                    last_modified = response.headers.get('Last-Modified')
                    if last_modified:
                        self._raw_timestamp = last_modified
                        try:
                            return parsedate_to_datetime(last_modified)
                        except (ValueError, TypeError):
                            return self.date_parser.parse(last_modified)
                    return None

                return self._parse_json_response(response.text)

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"{method} request failed: {e}")
                continue

        self.logger.error(f"All methods failed for {url}")
        return None

    def _parse_json_response(self, content: str) -> Optional[datetime]:
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return None

        timestamp_field = self.config.get('timestamp_field', 'updated_at')
        fallback_fields = self.config.get('fallback_fields', [
            'lastModified', 'modified', 'updatedAt', 'last_updated',
            'dataUpdatedAt', 'rowsUpdatedAt', 'metadataUpdatedAt'
        ])
        fields_to_check = [timestamp_field] + fallback_fields

        timestamp_value = self._find_timestamp_value(data, fields_to_check)
        if timestamp_value:
            # Convert Unix timestamp to readable format for raw_timestamp
            if isinstance(timestamp_value, (int, float)):
                try:
                    if timestamp_value > 1e12:
                        dt = datetime.fromtimestamp(timestamp_value / 1000)
                    else:
                        dt = datetime.fromtimestamp(timestamp_value)
                    self._raw_timestamp = dt.strftime('%Y-%m-%d %H:%M:%S') + f" (Unix: {int(timestamp_value)})"
                except (ValueError, OSError):
                    self._raw_timestamp = str(timestamp_value)
            else:
                self._raw_timestamp = str(timestamp_value)
            return self._parse_timestamp_value(timestamp_value)
        return None

    def _find_timestamp_value(self, data: Any, fields: List[str]) -> Optional[Any]:
        if isinstance(data, dict):
            for field in fields:
                if field in data:
                    return data[field]
            for value in data.values():
                result = self._find_timestamp_value(value, fields)
                if result:
                    return result
        elif isinstance(data, list) and data:
            return self._find_timestamp_value(data[0], fields)
        return None

    def _parse_timestamp_value(self, value: Any) -> Optional[datetime]:
        if isinstance(value, (int, float)):
            try:
                if value > 1e12:
                    return datetime.fromtimestamp(value / 1000)
                else:
                    return datetime.fromtimestamp(value)
            except (ValueError, OSError):
                return None
        if isinstance(value, str):
            return self.date_parser.parse(value)
        return None


class BS4Handler(BaseHandler):
    """Handler for static HTML pages using BeautifulSoup."""

    def get_method_name(self) -> str:
        return "beautifulsoup"

    def fetch_current_timestamp(self) -> Optional[datetime]:
        url = self.config.get('data_url')
        if not url:
            return None

        try:
            from bs4 import BeautifulSoup
        except ImportError:
            self.logger.error("BeautifulSoup not installed")
            return None

        http_settings = self.settings.get('http', {})
        timeout = http_settings.get('timeout', 30)
        max_retries = http_settings.get('max_retries', 3)
        user_agent = http_settings.get('user_agent', 'Sentinel-Monitor/1.0')
        headers = {'User-Agent': user_agent}

        for attempt in range(max_retries):
            try:
                self.logger.info(f"Fetching HTML from {url} (attempt {attempt + 1})")
                response = requests.get(url, headers=headers, timeout=timeout)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                return self._extract_timestamp(soup, response.text)
            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    return None
        return None

    def _extract_timestamp(self, soup, raw_html: str) -> Optional[datetime]:
        # Try time elements
        for elem in soup.find_all('time'):
            datetime_attr = elem.get('datetime')
            if datetime_attr:
                parsed = self.date_parser.parse(datetime_attr)
                if parsed:
                    self._raw_timestamp = datetime_attr
                    return parsed

        # Try meta tags
        meta_names = ['last-modified', 'dcterms.modified', 'article:modified_time']
        for name in meta_names:
            meta = soup.find('meta', attrs={'name': name}) or soup.find('meta', attrs={'property': name})
            if meta and meta.get('content'):
                parsed = self.date_parser.parse(meta['content'])
                if parsed:
                    self._raw_timestamp = meta['content']
                    return parsed

        # Search with patterns
        patterns = [
            r'Updated[:\s]+(\w+\s+\d{1,2},?\s+\d{4})',
            r'Last\s+(?:Updated|Modified)[:\s]+(\w+\s+\d{1,2},?\s+\d{4})',
        ]
        for pattern in patterns:
            match = re.search(pattern, raw_html, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                parsed = self.date_parser.parse(date_str)
                if parsed:
                    self._raw_timestamp = date_str
                    return parsed
        return None


class CLIHandler(BaseHandler):
    """Handler for command-line based metadata extraction."""

    def get_method_name(self) -> str:
        return "cli"

    def fetch_current_timestamp(self) -> Optional[datetime]:
        import subprocess

        url = self.config.get('data_url')
        if not url:
            return None

        command = self.config.get('command', 'curl -sI')
        full_command = f'{command} "{url}"'
        timeout = self.settings.get('http', {}).get('timeout', 30)

        try:
            self.logger.info(f"Executing: {full_command}")
            result = subprocess.run(full_command, shell=True, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                return None
            return self._parse_headers(result.stdout)
        except subprocess.TimeoutExpired:
            return None
        except Exception:
            return None

    def _parse_headers(self, output: str) -> Optional[datetime]:
        for line in output.strip().split('\n'):
            if line.lower().startswith('last-modified:'):
                value = line.split(':', 1)[1].strip()
                self._raw_timestamp = value
                try:
                    return parsedate_to_datetime(value)
                except (ValueError, TypeError):
                    return self.date_parser.parse(value)
        for line in output.strip().split('\n'):
            if line.lower().startswith('date:'):
                value = line.split(':', 1)[1].strip()
                self._raw_timestamp = value
                try:
                    return parsedate_to_datetime(value)
                except (ValueError, TypeError):
                    return self.date_parser.parse(value)
        return None


class SeleniumHandler(BaseHandler):
    """Handler for JavaScript-rendered pages using browser automation."""

    def get_method_name(self) -> str:
        return "selenium"

    def fetch_current_timestamp(self) -> Optional[datetime]:
        url = self.config.get('data_url')
        if not url:
            return None

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from webdriver_manager.chrome import ChromeDriverManager
        except ImportError as e:
            self.logger.warning(f"Selenium/webdriver-manager not installed: {e}")
            self.logger.warning("Install with: pip install selenium webdriver-manager")
            return None

        # Get timeouts from config/settings
        selenium_settings = self.settings.get('selenium', {})
        page_load_timeout = self.config.get('page_load_timeout', selenium_settings.get('page_load_timeout', 60))
        wait_timeout = self.config.get('wait_timeout', selenium_settings.get('wait_timeout', 30))

        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        # Reduce resource usage
        chrome_options.add_argument('--disable-images')
        chrome_options.add_experimental_option('prefs', {'profile.managed_default_content_settings.images': 2})

        driver = None
        try:
            self.logger.info(f"Starting Selenium for {url}")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(page_load_timeout)
            driver.set_script_timeout(page_load_timeout)

            driver.get(url)

            # Wait for page to be ready
            try:
                WebDriverWait(driver, wait_timeout).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except Exception as wait_err:
                self.logger.warning(f"Wait timeout, continuing anyway: {wait_err}")

            # Extra wait for JavaScript-heavy pages (like FBI CDE)
            import time
            time.sleep(5)  # Let JS render

            # Try to find dates using CSS selectors from config
            selectors = self.config.get('selector', '').split(',')
            for selector in selectors:
                selector = selector.strip()
                if selector:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        for elem in elements:
                            text = elem.text.strip()
                            if text:
                                parsed = self.date_parser.parse(text)
                                if parsed:
                                    self._raw_timestamp = text
                                    self.logger.info(f"Found date via selector '{selector}': {text}")
                                    return parsed
                    except Exception:
                        pass

            # Search page for date patterns
            try:
                page_text = driver.find_element(By.TAG_NAME, "body").text
            except Exception:
                page_text = driver.page_source

            # Extended patterns for various date formats
            patterns = [
                r'(?:Last\s+)?(?:Updated|Modified)[\s:]+(\w+\s+\d{1,2},?\s+\d{4})',
                r'Data\s+(?:as\s+of|through)[\s:]+(\w+\s+\d{1,2},?\s+\d{4})',
                r'(?:Released|Published)[\s:]+(\w+\s+\d{1,2},?\s+\d{4})',
                r'(?:Data\s+)?(?:Current|Available)\s+(?:as\s+of|through)[\s:]+(\w+\s+\d{1,2},?\s+\d{4})',
                r'(\w+\s+\d{1,2},?\s+\d{4})',  # General date like "January 15, 2026"
                r'(\d{1,2}/\d{1,2}/\d{4})',     # MM/DD/YYYY
                r'(\d{4}-\d{2}-\d{2})',          # YYYY-MM-DD
                r'(\d{2}-\d{2}-\d{4})',          # DD-MM-YYYY or MM-DD-YYYY
            ]

            for pattern in patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                for date_str in matches:
                    parsed = self.date_parser.parse(date_str)
                    if parsed:
                        # Validate it's a reasonable date (not too old, not in future)
                        now = datetime.now()
                        if parsed.year >= 2020 and parsed <= now:
                            self._raw_timestamp = date_str
                            self.logger.info(f"Found date via pattern: {date_str}")
                            return parsed

            # Check page source for JSON with dates
            page_source = driver.page_source
            json_patterns = [
                r'"(?:lastUpdated|updatedAt|modified|releaseDate)"[\s]*:[\s]*"([^"]+)"',
                r'"(?:lastUpdated|updatedAt|modified|releaseDate)"[\s]*:[\s]*(\d+)',
            ]
            for pattern in json_patterns:
                match = re.search(pattern, page_source, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    self._raw_timestamp = value
                    parsed = self.date_parser.parse(value)
                    if parsed:
                        self.logger.info(f"Found date in JSON: {value}")
                        return parsed

            self.logger.warning(f"No date found on page: {url}")
            return None
        except Exception as e:
            self.logger.error(f"Selenium error: {e}")
            return None
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass


# =============================================================================
# REGISTRY
# =============================================================================

HANDLER_MAP = {
    'http_head': HTTPHandler,
    'api': APIHandler,
    'selenium': SeleniumHandler,
    'beautifulsoup': BS4Handler,
    'cli': CLIHandler,
}


def load_config(path: str) -> Dict[str, Any]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"Warning: Could not load config {path}: {e}")
        return {}


# =============================================================================
# SENTINEL
# =============================================================================

class Sentinel:
    """Main monitoring agent."""

    def __init__(self):
        self.sources = load_config(os.path.join(BASE_DIR, 'config', 'sources.yaml'))
        self.settings = load_config(os.path.join(BASE_DIR, 'config', 'settings.yaml'))
        self.state_manager = StateManager()
        self.logger = logging.getLogger('Sentinel')

    def check_for_updates(self, dcid: str) -> CheckResult:
        self.logger.info(f"Checking: {dcid}")

        source_config = self.sources.get(dcid)
        if not source_config:
            return CheckResult(dcid=dcid, error=f"Source not found: {dcid}")

        import_name = source_config.get('import_name', dcid)
        data_url = source_config.get('data_url', '')
        script_url = source_config.get('script_url', '')
        method = source_config.get('method', '')

        handler_class = HANDLER_MAP.get(method)
        if not handler_class:
            return CheckResult(
                dcid=dcid, import_name=import_name, data_url=data_url,
                script_url=script_url, method=method,
                error=f"Unknown method: {method}"
            )

        config = {**source_config, 'dcid': dcid}
        handler = handler_class(config, self.settings)

        try:
            current_timestamp = handler.fetch_current_timestamp()
        except Exception as e:
            return CheckResult(
                dcid=dcid, import_name=import_name, data_url=data_url,
                script_url=script_url, method=method, error=str(e)
            )

        stored_timestamp = self.state_manager.get_last_timestamp(dcid)
        changed = handler.compare_with_stored(current_timestamp, stored_timestamp)

        if current_timestamp:
            self.state_manager.update_timestamp(dcid, current_timestamp, handler.get_raw_timestamp())

        return CheckResult(
            dcid=dcid, import_name=import_name, data_url=data_url,
            script_url=script_url, method=method, changed=changed,
            current_timestamp=current_timestamp, previous_timestamp=stored_timestamp,
            raw_timestamp=handler.get_raw_timestamp()
        )

    def check_all_sources(self) -> List[CheckResult]:
        results = []
        for dcid in self.sources.keys():
            result = self.check_for_updates(dcid)
            results.append(result)
        return results

    def export_to_csv(self, results: List[CheckResult], output_path: str) -> str:
        fieldnames = [
            'import_name', 'dcid', 'data_url', 'script_url', 'method',
            'source_last_modified_date', 'source_last_modified_time',
            'raw_timestamp_value', 'data_changed', 'status', 'error'
        ]

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                # Format the last modified timestamp as separate date and time columns
                if result.current_timestamp:
                    last_mod_date = result.current_timestamp.strftime('%Y-%m-%d')
                    last_mod_time = result.current_timestamp.strftime('%H:%M:%S')
                else:
                    last_mod_date = ''
                    last_mod_time = ''

                writer.writerow({
                    'import_name': result.import_name or '',
                    'dcid': result.dcid,
                    'data_url': result.data_url or '',
                    'script_url': result.script_url or '',
                    'method': result.method or '',
                    'source_last_modified_date': last_mod_date,
                    'source_last_modified_time': last_mod_time,
                    'raw_timestamp_value': result.raw_timestamp or '',
                    'data_changed': result.changed,
                    'status': 'success' if not result.error else 'error',
                    'error': result.error or ''
                })

        return output_path


# =============================================================================
# MAIN
# =============================================================================

def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("=" * 60)
    print("Sentinel - Automated Data Source Monitoring Agent")
    print("=" * 60)

    sentinel = Sentinel()

    print(f"\nConfigured sources: {len(sentinel.sources)}")
    for dcid, source in sentinel.sources.items():
        print(f"  - {dcid} ({source.get('method')})")

    print("\n" + "-" * 60)
    print("Starting update checks...")
    print("-" * 60 + "\n")

    results = sentinel.check_all_sources()

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    for result in results:
        status = "ERROR" if result.error else ("UPDATED" if result.changed else "NO CHANGE")
        print(f"\n[{status}] {result.import_name or result.dcid}")
        print(f"  DCID:       {result.dcid}")
        print(f"  Method:     {result.method}")
        if result.data_url:
            url_display = result.data_url[:70] + "..." if len(result.data_url) > 70 else result.data_url
            print(f"  Data URL:   {url_display}")
        if result.current_timestamp:
            print(f"  Last Modified Timestamp:  {result.current_timestamp}")
            if result.raw_timestamp:
                print(f"  Raw Value:               {result.raw_timestamp}")
        if result.error:
            print(f"  Error:      {result.error}")

    output_path = os.path.join(BASE_DIR, 'output.csv')
    sentinel.export_to_csv(results, output_path)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    total = len(results)
    updated = sum(1 for r in results if r.changed)
    unchanged = sum(1 for r in results if not r.changed and not r.error)
    errors = sum(1 for r in results if r.error)

    print(f"  Total Sources:  {total}")
    print(f"  Updated:        {updated}")
    print(f"  Unchanged:      {unchanged}")
    print(f"  Errors:         {errors}")
    print(f"\n  Output file:    {output_path}")
    print("=" * 60)

    return results


if __name__ == '__main__':
    main()

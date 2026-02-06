"""
BeautifulSoup handler for static HTML parsing.
Extracts update dates from HTML pages without JavaScript rendering.
"""

import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
import re

from .base_handler import BaseHandler
from utils.date_parser import DateParser


class BS4Handler(BaseHandler):
    """Handler for static HTML pages using BeautifulSoup."""

    def __init__(self, config: Dict[str, Any], settings: Dict[str, Any] = None):
        super().__init__(config)
        self.settings = settings or {}
        self._raw_timestamp = None
        self._page_content = None  # Store page content for verification
        self.date_parser = DateParser()

    def get_method_name(self) -> str:
        return "beautifulsoup"

    def fetch_current_timestamp(self) -> Optional[datetime]:
        """
        Fetch timestamp by parsing HTML with BeautifulSoup.

        Returns:
            datetime extracted from page, or None if not found
        """
        url = self.config.get('data_url')
        if not url:
            self.logger.error("No data_url configured")
            return None

        try:
            from bs4 import BeautifulSoup
        except ImportError:
            self.logger.error("BeautifulSoup not installed. Run: pip install beautifulsoup4")
            return None

        http_settings = self.settings.get('http', {})
        timeout = http_settings.get('timeout', 30)
        max_retries = http_settings.get('max_retries', 3)
        user_agent = http_settings.get('user_agent', 'Sentinel-Monitor/1.0')

        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml'
        }

        for attempt in range(max_retries):
            try:
                self.logger.info(f"Fetching HTML from {url} (attempt {attempt + 1})")
                response = requests.get(url, headers=headers, timeout=timeout)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')
                self._page_content = response.text  # Store for verification
                return self._extract_timestamp(soup, response.text)

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    self.handle_error(e)
                    return None

        return None

    def _extract_timestamp(self, soup, raw_html: str) -> Optional[datetime]:
        """Extract timestamp from parsed HTML."""
        # Try CSS selectors first
        timestamp = self._find_by_selectors(soup)
        if timestamp:
            return timestamp

        # Try common HTML elements for dates
        timestamp = self._find_in_common_elements(soup)
        if timestamp:
            return timestamp

        # Try meta tags
        timestamp = self._find_in_meta_tags(soup)
        if timestamp:
            return timestamp

        # Search with regex patterns
        timestamp = self._search_with_patterns(raw_html)
        if timestamp:
            return timestamp

        self.logger.warning("No timestamp found in HTML")
        return None

    def _find_by_selectors(self, soup) -> Optional[datetime]:
        """Find timestamp using configured CSS selectors."""
        selectors = self.config.get('selector', '')
        if not selectors:
            return None

        selector_list = [s.strip() for s in selectors.split(',')]

        for selector in selector_list:
            try:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text(strip=True)
                    if text:
                        parsed = self.date_parser.parse(text)
                        if parsed:
                            self._raw_timestamp = text
                            return parsed

                    # Check datetime attribute
                    datetime_attr = element.get('datetime')
                    if datetime_attr:
                        parsed = self.date_parser.parse(datetime_attr)
                        if parsed:
                            self._raw_timestamp = datetime_attr
                            return parsed
            except Exception as e:
                self.logger.debug(f"Selector {selector} failed: {e}")
                continue

        return None

    def _find_in_common_elements(self, soup) -> Optional[datetime]:
        """Search common HTML elements that typically contain dates."""
        # Look for time elements
        time_elements = soup.find_all('time')
        for elem in time_elements:
            datetime_attr = elem.get('datetime')
            if datetime_attr:
                parsed = self.date_parser.parse(datetime_attr)
                if parsed:
                    self._raw_timestamp = datetime_attr
                    return parsed

            text = elem.get_text(strip=True)
            if text:
                parsed = self.date_parser.parse(text)
                if parsed:
                    self._raw_timestamp = text
                    return parsed

        # Look for elements with date-related classes
        date_classes = ['date', 'updated', 'modified', 'last-updated', 'timestamp']
        for class_name in date_classes:
            elements = soup.find_all(class_=re.compile(class_name, re.I))
            for elem in elements:
                text = elem.get_text(strip=True)
                if text:
                    parsed = self.date_parser.parse(text)
                    if parsed:
                        self._raw_timestamp = text
                        return parsed

        return None

    def _find_in_meta_tags(self, soup) -> Optional[datetime]:
        """Search meta tags for date information."""
        meta_names = [
            'last-modified', 'dcterms.modified', 'article:modified_time',
            'og:updated_time', 'date', 'DC.date.modified'
        ]

        for name in meta_names:
            # Try name attribute
            meta = soup.find('meta', attrs={'name': name})
            if meta and meta.get('content'):
                parsed = self.date_parser.parse(meta['content'])
                if parsed:
                    self._raw_timestamp = meta['content']
                    return parsed

            # Try property attribute
            meta = soup.find('meta', attrs={'property': name})
            if meta and meta.get('content'):
                parsed = self.date_parser.parse(meta['content'])
                if parsed:
                    self._raw_timestamp = meta['content']
                    return parsed

        return None

    def _search_with_patterns(self, html: str) -> Optional[datetime]:
        """Search HTML text with date patterns."""
        date_patterns = self.config.get('date_patterns', [])

        # Default patterns if none configured
        if not date_patterns:
            date_patterns = [
                r'Updated[:\s]+(\w+\s+\d{1,2},?\s+\d{4})',
                r'Last\s+(?:Updated|Modified)[:\s]+(\w+\s+\d{1,2},?\s+\d{4})',
                r'Modified[:\s]+(\d{1,2}/\d{1,2}/\d{4})',
                r'Date[:\s]+(\w+\s+\d{1,2},?\s+\d{4})',
            ]

        for pattern in date_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                parsed = self.date_parser.parse(date_str)
                if parsed:
                    self._raw_timestamp = date_str
                    self.logger.info(f"Found date via pattern: {date_str}")
                    return parsed

        return None

"""
Selenium handler for JavaScript-heavy websites.
Uses headless browser to scrape update dates from dynamic content.
"""

from datetime import datetime
from typing import Optional, Dict, Any
import re

from .base_handler import BaseHandler
from utils.date_parser import DateParser


class SeleniumHandler(BaseHandler):
    """Handler for JavaScript-rendered pages requiring browser automation."""

    def __init__(self, config: Dict[str, Any], settings: Dict[str, Any] = None):
        super().__init__(config)
        self.settings = settings or {}
        self._raw_timestamp = None
        self._page_content = None  # Store page content for verification
        self.date_parser = DateParser()

    def get_method_name(self) -> str:
        return "selenium"

    def fetch_current_timestamp(self) -> Optional[datetime]:
        """
        Fetch timestamp using Selenium headless browser.

        Returns:
            datetime extracted from page, or None if not found
        """
        url = self.config.get('data_url')
        if not url:
            self.logger.error("No data_url configured")
            return None

        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.common.exceptions import TimeoutException, WebDriverException
            from webdriver_manager.chrome import ChromeDriverManager
        except ImportError as e:
            self.logger.error(f"Required packages not installed: {e}")
            self.logger.error("Run: pip install selenium webdriver-manager")
            return None

        selenium_settings = self.settings.get('selenium', {})
        headless = selenium_settings.get('headless', True)
        wait_timeout = self.config.get('wait_timeout', selenium_settings.get('wait_timeout', 15))
        page_load_timeout = selenium_settings.get('page_load_timeout', 30)

        # Configure Chrome options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        driver = None
        try:
            self.logger.info(f"Starting Selenium browser for {url}")
            # Use webdriver-manager to automatically download and manage ChromeDriver
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            driver.set_page_load_timeout(page_load_timeout)

            driver.get(url)

            # Wait for page to load
            WebDriverWait(driver, wait_timeout).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Store page content for verification
            self._page_content = driver.page_source

            # Try to find timestamp using configured selectors
            timestamp = self._find_timestamp_on_page(driver, wait_timeout)

            if timestamp:
                return timestamp

            # Fall back to searching entire page text
            return self._search_page_for_date(driver)

        except TimeoutException:
            self.logger.error(f"Timeout loading page: {url}")
            return None
        except WebDriverException as e:
            self.handle_error(e)
            return None
        finally:
            if driver:
                driver.quit()

    def _find_timestamp_on_page(self, driver, wait_timeout: int) -> Optional[datetime]:
        """Try to find timestamp using CSS selectors."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException

        selectors = self.config.get('selector', '')
        if not selectors:
            return None

        # Support multiple selectors separated by comma
        selector_list = [s.strip() for s in selectors.split(',')]

        for selector in selector_list:
            try:
                self.logger.debug(f"Trying selector: {selector}")
                elements = driver.find_elements(By.CSS_SELECTOR, selector)

                for element in elements:
                    text = element.text.strip()
                    if text:
                        self.logger.debug(f"Found text: {text}")
                        parsed = self.date_parser.parse(text)
                        if parsed:
                            self._raw_timestamp = text
                            return parsed

            except Exception as e:
                self.logger.debug(f"Selector {selector} failed: {e}")
                continue

        return None

    def _search_page_for_date(self, driver) -> Optional[datetime]:
        """Search entire page text for date patterns."""
        try:
            page_text = driver.find_element("tag name", "body").text

            # Common date patterns on pages
            date_patterns = [
                r'(?:Last\s+)?(?:Updated|Modified)[\s:]+(\w+\s+\d{1,2},?\s+\d{4})',
                r'(?:Last\s+)?(?:Updated|Modified)[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'(?:Last\s+)?(?:Updated|Modified)[\s:]+(\d{4}[/-]\d{1,2}[/-]\d{1,2})',
                r'Data\s+(?:as\s+of|through)[\s:]+(\w+\s+\d{1,2},?\s+\d{4})',
                r'Release\s+Date[\s:]+(\w+\s+\d{1,2},?\s+\d{4})',
            ]

            for pattern in date_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    date_str = match.group(1)
                    self._raw_timestamp = date_str
                    parsed = self.date_parser.parse(date_str)
                    if parsed:
                        self.logger.info(f"Found date via pattern: {date_str}")
                        return parsed

            self.logger.warning("No date pattern found in page text")
            return None

        except Exception as e:
            self.logger.error(f"Error searching page text: {e}")
            return None

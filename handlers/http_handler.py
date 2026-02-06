"""
HTTP HEAD request handler for direct download sources.
Extracts Last-Modified header or ETag without downloading the file.
"""

import requests
from datetime import datetime
from typing import Optional, Dict, Any
from email.utils import parsedate_to_datetime

from .base_handler import BaseHandler


class HTTPHandler(BaseHandler):
    """Handler for sources that support HTTP HEAD requests."""

    def __init__(self, config: Dict[str, Any], settings: Dict[str, Any] = None):
        super().__init__(config)
        self.settings = settings or {}
        self._raw_timestamp = None
        self._etag = None

    def get_method_name(self) -> str:
        return "http_head"

    def fetch_current_timestamp(self) -> Optional[datetime]:
        """
        Fetch timestamp using HTTP HEAD request.

        Returns:
            datetime from Last-Modified header, or None if not available
        """
        url = self.config.get('data_url')
        if not url:
            self.logger.error("No data_url configured")
            return None

        http_settings = self.settings.get('http', {})
        timeout = http_settings.get('timeout', 30)
        max_retries = http_settings.get('max_retries', 3)
        user_agent = http_settings.get(
            'user_agent',
            'Sentinel-Monitor/1.0'
        )

        headers = {'User-Agent': user_agent}

        for attempt in range(max_retries):
            try:
                self.logger.info(f"Sending HEAD request to {url} (attempt {attempt + 1})")
                response = requests.head(
                    url,
                    headers=headers,
                    timeout=timeout,
                    allow_redirects=True
                )
                response.raise_for_status()

                # Try Last-Modified header first
                last_modified = response.headers.get('Last-Modified')
                if last_modified:
                    self._raw_timestamp = last_modified
                    try:
                        return parsedate_to_datetime(last_modified)
                    except (ValueError, TypeError) as e:
                        self.logger.warning(f"Failed to parse Last-Modified: {last_modified}")

                # Fall back to ETag if available
                etag = response.headers.get('ETag')
                if etag:
                    self._etag = etag
                    self.logger.info(f"No Last-Modified, but found ETag: {etag}")

                # Try Date header as last resort
                date_header = response.headers.get('Date')
                if date_header:
                    self._raw_timestamp = date_header
                    try:
                        return parsedate_to_datetime(date_header)
                    except (ValueError, TypeError):
                        pass

                self.logger.warning(f"No timestamp headers found for {url}")
                return None

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    self.handle_error(e)
                    return None

        return None

    def get_etag(self) -> Optional[str]:
        """Get the ETag if available."""
        return self._etag

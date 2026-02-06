"""
API handler for REST API metadata extraction.
Parses JSON/XML responses to extract update timestamps.
"""

import requests
from datetime import datetime
from typing import Optional, Dict, Any, List
import json

from .base_handler import BaseHandler
from utils.date_parser import DateParser


class APIHandler(BaseHandler):
    """Handler for API-based data sources."""

    def __init__(self, config: Dict[str, Any], settings: Dict[str, Any] = None):
        super().__init__(config)
        self.settings = settings or {}
        self._raw_timestamp = None
        self._page_content = None  # Store response content for verification
        self.date_parser = DateParser()

    def get_method_name(self) -> str:
        return "api"

    def fetch_current_timestamp(self) -> Optional[datetime]:
        """
        Fetch timestamp from API metadata endpoint.

        Returns:
            datetime parsed from API response, or None if not available
        """
        url = self.config.get('data_url')
        if not url:
            self.logger.error("No data_url configured")
            return None

        http_settings = self.settings.get('http', {})
        timeout = http_settings.get('timeout', 30)
        max_retries = http_settings.get('max_retries', 3)
        user_agent = http_settings.get('user_agent', 'Sentinel-Monitor/1.0')

        headers = {
            'User-Agent': user_agent,
            'Accept': 'application/json'
        }

        for attempt in range(max_retries):
            try:
                self.logger.info(f"Fetching API metadata from {url} (attempt {attempt + 1})")
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=timeout
                )
                response.raise_for_status()

                self._page_content = response.text  # Store for verification
                return self._parse_response(response)

            except requests.exceptions.RequestException as e:
                self.logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    self.handle_error(e)
                    return None

        return None

    def _parse_response(self, response: requests.Response) -> Optional[datetime]:
        """Parse the API response to extract timestamp."""
        response_format = self.config.get('response_format', 'json')

        if response_format == 'json':
            return self._parse_json_response(response.text)
        elif response_format == 'xml':
            return self._parse_xml_response(response.text)
        else:
            self.logger.error(f"Unsupported response format: {response_format}")
            return None

    def _parse_json_response(self, content: str) -> Optional[datetime]:
        """Parse JSON response for timestamp fields."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON: {e}")
            return None

        # Fields to check for timestamp
        timestamp_field = self.config.get('timestamp_field', 'updated_at')
        fallback_fields = self.config.get('fallback_fields', [
            'lastModified', 'modified', 'updatedAt', 'last_updated',
            'dataUpdatedAt', 'rowsUpdatedAt', 'metadataUpdatedAt'
        ])

        # Build ordered list of fields to check
        fields_to_check = [timestamp_field] + fallback_fields

        # Search for timestamp in response
        timestamp_value = self._find_timestamp_value(data, fields_to_check)

        if timestamp_value:
            self._raw_timestamp = str(timestamp_value)
            return self._parse_timestamp_value(timestamp_value)

        self.logger.warning("No timestamp field found in API response")
        return None

    def _find_timestamp_value(
        self,
        data: Any,
        fields: List[str]
    ) -> Optional[Any]:
        """Recursively search for timestamp field in data."""
        if isinstance(data, dict):
            for field in fields:
                if field in data:
                    return data[field]
            # Search nested dictionaries
            for value in data.values():
                result = self._find_timestamp_value(value, fields)
                if result:
                    return result
        elif isinstance(data, list) and data:
            # Check first item in list
            return self._find_timestamp_value(data[0], fields)

        return None

    def _parse_timestamp_value(self, value: Any) -> Optional[datetime]:
        """Parse various timestamp formats."""
        if isinstance(value, (int, float)):
            # Unix timestamp (seconds or milliseconds)
            try:
                if value > 1e12:  # Milliseconds
                    return datetime.fromtimestamp(value / 1000)
                else:  # Seconds
                    return datetime.fromtimestamp(value)
            except (ValueError, OSError) as e:
                self.logger.warning(f"Failed to parse Unix timestamp: {value}")
                return None

        if isinstance(value, str):
            return self.date_parser.parse(value)

        return None

    def _parse_xml_response(self, content: str) -> Optional[datetime]:
        """Parse XML response for timestamp fields."""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(content)

            timestamp_field = self.config.get('timestamp_field', 'updated_at')
            fallback_fields = self.config.get('fallback_fields', [])
            fields = [timestamp_field] + fallback_fields

            for field in fields:
                element = root.find(f".//{field}")
                if element is not None and element.text:
                    self._raw_timestamp = element.text
                    return self.date_parser.parse(element.text)

            return None
        except Exception as e:
            self.logger.error(f"Failed to parse XML: {e}")
            return None

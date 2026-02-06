"""
Date Parser utility for handling various date formats.
"""

import re
from datetime import datetime
from typing import Optional, List
import logging


class DateParser:
    """Utility class for parsing various date formats."""

    # Common date format patterns
    DATE_FORMATS = [
        # ISO formats
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",

        # US formats
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
        "%m-%d-%Y",

        # European formats
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%d-%m-%Y",

        # Text formats
        "%B %d, %Y",
        "%b %d, %Y",
        "%B %d %Y",
        "%b %d %Y",
        "%d %B %Y",
        "%d %b %Y",

        # HTTP date format (RFC 7231)
        "%a, %d %b %Y %H:%M:%S GMT",
        "%a, %d %b %Y %H:%M:%S %Z",

        # Other common formats
        "%Y%m%d",
        "%Y%m%d%H%M%S",
    ]

    def __init__(self):
        self.logger = logging.getLogger('DateParser')

    def parse(self, date_string: str) -> Optional[datetime]:
        """
        Parse a date string into a datetime object.

        Args:
            date_string: String containing a date

        Returns:
            datetime object or None if parsing fails
        """
        if not date_string:
            return None

        # Clean up the string
        date_string = self._clean_date_string(date_string)

        # Try dateutil parser first (most flexible)
        try:
            from dateutil import parser as dateutil_parser
            return dateutil_parser.parse(date_string, fuzzy=True)
        except (ImportError, ValueError, TypeError):
            pass

        # Try standard formats
        for fmt in self.DATE_FORMATS:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue

        # Try Unix timestamp
        timestamp = self._try_unix_timestamp(date_string)
        if timestamp:
            return timestamp

        self.logger.debug(f"Could not parse date: {date_string}")
        return None

    def _clean_date_string(self, date_string: str) -> str:
        """Clean and normalize date string."""
        # Remove extra whitespace
        date_string = ' '.join(date_string.split())

        # Remove common prefixes
        prefixes = [
            r'^Last\s+(?:Updated|Modified)\s*[:\-]?\s*',
            r'^Updated\s*[:\-]?\s*',
            r'^Modified\s*[:\-]?\s*',
            r'^Date\s*[:\-]?\s*',
            r'^As\s+of\s*[:\-]?\s*',
        ]
        for prefix in prefixes:
            date_string = re.sub(prefix, '', date_string, flags=re.IGNORECASE)

        # Handle timezone abbreviations
        date_string = re.sub(r'\s*(EST|EDT|PST|PDT|CST|CDT|MST|MDT)\s*$', '', date_string)

        return date_string.strip()

    def _try_unix_timestamp(self, date_string: str) -> Optional[datetime]:
        """Try to parse as Unix timestamp."""
        try:
            # Remove any non-numeric characters
            numeric = re.sub(r'[^\d.]', '', date_string)
            if not numeric:
                return None

            value = float(numeric)

            # Check if milliseconds (13+ digits) or seconds (10 digits)
            if value > 1e12:
                return datetime.fromtimestamp(value / 1000)
            elif value > 1e9:
                return datetime.fromtimestamp(value)

            return None
        except (ValueError, OSError, OverflowError):
            return None

    def extract_date_from_text(self, text: str) -> Optional[datetime]:
        """
        Extract a date from free-form text.

        Args:
            text: Text that may contain a date

        Returns:
            datetime object or None
        """
        # Common patterns for dates in text
        patterns = [
            # "January 15, 2024" or "Jan 15, 2024"
            r'(\w+\s+\d{1,2},?\s+\d{4})',
            # "15 January 2024"
            r'(\d{1,2}\s+\w+\s+\d{4})',
            # "2024-01-15"
            r'(\d{4}-\d{2}-\d{2})',
            # "01/15/2024" or "15/01/2024"
            r'(\d{1,2}/\d{1,2}/\d{4})',
            # "2024/01/15"
            r'(\d{4}/\d{2}/\d{2})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                parsed = self.parse(date_str)
                if parsed:
                    return parsed

        return None

    def format_datetime(self, dt: datetime, format_str: str = None) -> str:
        """
        Format a datetime object to string.

        Args:
            dt: datetime object
            format_str: Optional format string

        Returns:
            Formatted date string
        """
        if format_str is None:
            format_str = "%Y-%m-%d %H:%M:%S"
        return dt.strftime(format_str)

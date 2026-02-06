"""
Tests for date parsing utility.
"""

import pytest
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.date_parser import DateParser


class TestDateParser:
    """Tests for DateParser utility."""

    def setup_method(self):
        self.parser = DateParser()

    def test_parse_iso_format(self):
        """Test parsing ISO 8601 format."""
        result = self.parser.parse("2025-01-15T10:30:00Z")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_http_date(self):
        """Test parsing HTTP date format."""
        result = self.parser.parse("Wed, 15 Jan 2025 10:30:00 GMT")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_us_format(self):
        """Test parsing US date format."""
        result = self.parser.parse("01/15/2025")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_text_format(self):
        """Test parsing text date format."""
        result = self.parser.parse("January 15, 2025")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_with_prefix(self):
        """Test parsing date with 'Last Updated' prefix."""
        result = self.parser.parse("Last Updated: January 15, 2025")
        assert result is not None
        assert result.year == 2025

    def test_extract_date_from_text(self):
        """Test extracting date from free-form text."""
        text = "This data was last modified on January 15, 2025 by the team."
        result = self.parser.extract_date_from_text(text)
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_invalid_date(self):
        """Test parsing invalid date string."""
        result = self.parser.parse("not a date")
        # May return None or try fuzzy parsing
        # Just ensure no exception is raised

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        result = self.parser.parse("")
        assert result is None

    def test_parse_none(self):
        """Test parsing None."""
        result = self.parser.parse(None)
        assert result is None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

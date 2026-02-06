"""
Tests for handler implementations.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.http_handler import HTTPHandler
from handlers.api_handler import APIHandler
from handlers.bs4_handler import BS4Handler
from handlers.cli_handler import CLIHandler


class TestHTTPHandler:
    """Tests for HTTP HEAD handler."""

    def test_get_method_name(self):
        config = {'data_url': 'https://example.com/file.csv'}
        handler = HTTPHandler(config)
        assert handler.get_method_name() == 'http_head'

    @patch('handlers.http_handler.requests.head')
    def test_fetch_timestamp_success(self, mock_head):
        """Test successful timestamp fetch from Last-Modified header."""
        mock_response = Mock()
        mock_response.headers = {
            'Last-Modified': 'Wed, 15 Jan 2025 10:30:00 GMT'
        }
        mock_response.raise_for_status = Mock()
        mock_head.return_value = mock_response

        config = {'data_url': 'https://example.com/file.csv'}
        handler = HTTPHandler(config)

        result = handler.fetch_current_timestamp()

        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    @patch('handlers.http_handler.requests.head')
    def test_fetch_timestamp_no_header(self, mock_head):
        """Test when no Last-Modified header is present."""
        mock_response = Mock()
        mock_response.headers = {}
        mock_response.raise_for_status = Mock()
        mock_head.return_value = mock_response

        config = {'data_url': 'https://example.com/file.csv'}
        handler = HTTPHandler(config)

        result = handler.fetch_current_timestamp()
        assert result is None


class TestAPIHandler:
    """Tests for API handler."""

    def test_get_method_name(self):
        config = {'data_url': 'https://api.example.com/data'}
        handler = APIHandler(config)
        assert handler.get_method_name() == 'api'

    @patch('handlers.api_handler.requests.get')
    def test_fetch_timestamp_json(self, mock_get):
        """Test parsing timestamp from JSON response."""
        mock_response = Mock()
        mock_response.text = '{"updated_at": "2025-01-15T10:30:00Z"}'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        config = {
            'data_url': 'https://api.example.com/data',
            'response_format': 'json',
            'timestamp_field': 'updated_at'
        }
        handler = APIHandler(config)

        result = handler.fetch_current_timestamp()

        assert result is not None
        assert result.year == 2025

    @patch('handlers.api_handler.requests.get')
    def test_fetch_timestamp_unix(self, mock_get):
        """Test parsing Unix timestamp from JSON response."""
        mock_response = Mock()
        mock_response.text = '{"rowsUpdatedAt": 1705315800}'  # 2024-01-15
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        config = {
            'data_url': 'https://api.example.com/data',
            'response_format': 'json',
            'timestamp_field': 'rowsUpdatedAt'
        }
        handler = APIHandler(config)

        result = handler.fetch_current_timestamp()

        assert result is not None


class TestBS4Handler:
    """Tests for BeautifulSoup handler."""

    def test_get_method_name(self):
        config = {'data_url': 'https://example.com/page'}
        handler = BS4Handler(config)
        assert handler.get_method_name() == 'beautifulsoup'

    @patch('handlers.bs4_handler.requests.get')
    def test_fetch_timestamp_from_time_element(self, mock_get):
        """Test extracting timestamp from <time> element."""
        html = '''
        <html>
            <body>
                <time datetime="2025-01-15T10:30:00">January 15, 2025</time>
            </body>
        </html>
        '''
        mock_response = Mock()
        mock_response.text = html
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        config = {'data_url': 'https://example.com/page'}
        handler = BS4Handler(config)

        result = handler.fetch_current_timestamp()

        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15


class TestCLIHandler:
    """Tests for CLI handler."""

    def test_get_method_name(self):
        config = {'data_url': 'https://example.com/file.zip'}
        handler = CLIHandler(config)
        assert handler.get_method_name() == 'cli'

    @patch('handlers.cli_handler.subprocess.run')
    def test_fetch_timestamp_from_curl(self, mock_run):
        """Test parsing curl -I output."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '''HTTP/2 200
date: Wed, 15 Jan 2025 10:30:00 GMT
last-modified: Mon, 13 Jan 2025 08:00:00 GMT
content-type: application/zip
'''
        mock_run.return_value = mock_result

        config = {
            'data_url': 'https://example.com/file.zip',
            'command': 'curl -sI'
        }
        handler = CLIHandler(config)

        result = handler.fetch_current_timestamp()

        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 13


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

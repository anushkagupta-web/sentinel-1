"""
Pytest configuration and fixtures.
"""

import pytest
import os
import tempfile
import json


@pytest.fixture
def temp_state_file():
    """Create a temporary state file for testing."""
    fd, path = tempfile.mkstemp(suffix='.json')
    os.close(fd)
    with open(path, 'w') as f:
        json.dump({}, f)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def sample_config():
    """Sample source configuration for testing."""
    return {
        'test_source': {
            'import_name': 'Test Source',
            'dcid': 'test_source',
            'method': 'http_head',
            'data_url': 'https://example.com/data.csv',
            'script_url': 'https://github.com/example/script.py',
        }
    }


@pytest.fixture
def mock_http_response():
    """Mock HTTP response headers."""
    return {
        'Last-Modified': 'Wed, 15 Jan 2025 10:30:00 GMT',
        'ETag': '"abc123"',
        'Content-Length': '12345',
    }

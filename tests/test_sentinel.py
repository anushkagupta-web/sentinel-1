"""
Tests for the main Sentinel class.
"""

import pytest
import os
import sys
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sentinel import Sentinel
from core.state_manager import StateManager
from models.check_result import CheckResult


class TestStateManager:
    """Tests for StateManager."""

    def test_save_and_load_timestamp(self):
        """Test saving and loading timestamps."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            state_file = f.name

        try:
            from datetime import datetime
            manager = StateManager(state_file)

            # Save timestamp
            ts = datetime(2025, 1, 15, 10, 30, 0)
            manager.update_timestamp('test_dcid', ts)

            # Load timestamp
            loaded = manager.get_last_timestamp('test_dcid')

            assert loaded is not None
            assert loaded.year == 2025
            assert loaded.month == 1
            assert loaded.day == 15

        finally:
            os.unlink(state_file)

    def test_get_nonexistent_timestamp(self):
        """Test getting timestamp for unknown source."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({}, f)
            state_file = f.name

        try:
            manager = StateManager(state_file)
            result = manager.get_last_timestamp('nonexistent')
            assert result is None

        finally:
            os.unlink(state_file)


class TestCheckResult:
    """Tests for CheckResult model."""

    def test_check_result_creation(self):
        """Test creating a CheckResult."""
        from datetime import datetime

        result = CheckResult(
            dcid='test_dcid',
            import_name='Test Source',
            changed=True,
            current_timestamp=datetime(2025, 1, 15)
        )

        assert result.dcid == 'test_dcid'
        assert result.import_name == 'Test Source'
        assert result.changed is True
        assert result.is_success is True

    def test_check_result_with_error(self):
        """Test CheckResult with error."""
        result = CheckResult(
            dcid='test_dcid',
            error='Connection failed'
        )

        assert result.is_success is False
        assert result.status == 'error'

    def test_check_result_to_dict(self):
        """Test serializing CheckResult."""
        from datetime import datetime

        result = CheckResult(
            dcid='test_dcid',
            import_name='Test',
            changed=False,
            current_timestamp=datetime(2025, 1, 15, 10, 30, 0)
        )

        data = result.to_dict()

        assert data['dcid'] == 'test_dcid'
        assert data['changed'] is False
        assert '2025-01-15' in data['current_timestamp']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

"""
State Manager - Handles persistence of last-checked timestamps.
"""

import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from threading import Lock


class StateManager:
    """Manages persistent state for timestamp comparisons."""

    def __init__(self, state_file: str = None):
        """
        Initialize state manager.

        Args:
            state_file: Path to state JSON file
        """
        if state_file is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            state_file = os.path.join(base_dir, 'state', 'last_checked.json')

        self.state_file = state_file
        self._lock = Lock()
        self._state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load state from file."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load state file: {e}")
        return {}

    def _save_state(self) -> None:
        """Save state to file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, indent=2, default=str)
        except IOError as e:
            print(f"Error saving state file: {e}")

    def get_last_timestamp(self, dcid: str) -> Optional[datetime]:
        """
        Get last recorded timestamp for a source.

        Args:
            dcid: Data Commons ID

        Returns:
            datetime or None if not previously checked
        """
        with self._lock:
            source_state = self._state.get(dcid, {})
            timestamp_str = source_state.get('timestamp')

            if timestamp_str:
                try:
                    return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    pass

            return None

    def update_timestamp(
        self,
        dcid: str,
        timestamp: datetime,
        raw_value: str = None,
        etag: str = None
    ) -> None:
        """
        Update stored timestamp for a source.

        Args:
            dcid: Data Commons ID
            timestamp: New timestamp value
            raw_value: Original raw timestamp string
            etag: ETag value if available
        """
        with self._lock:
            if dcid not in self._state:
                self._state[dcid] = {}

            self._state[dcid]['timestamp'] = timestamp.isoformat()
            self._state[dcid]['last_check'] = datetime.now().isoformat()

            if raw_value:
                self._state[dcid]['raw_value'] = raw_value
            if etag:
                self._state[dcid]['etag'] = etag

            self._save_state()

    def get_state(self, dcid: str) -> Optional[Dict[str, Any]]:
        """Get full state for a source."""
        with self._lock:
            return self._state.get(dcid)

    def get_all_states(self) -> Dict[str, Any]:
        """Get all stored states."""
        with self._lock:
            return self._state.copy()

    def clear_state(self, dcid: str) -> None:
        """Clear state for a specific source."""
        with self._lock:
            if dcid in self._state:
                del self._state[dcid]
                self._save_state()

    def clear_all(self) -> None:
        """Clear all stored state."""
        with self._lock:
            self._state = {}
            self._save_state()

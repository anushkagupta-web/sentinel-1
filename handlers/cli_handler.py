"""
CLI handler for command-line based timestamp extraction.
Uses curl, wget, or other shell commands to fetch metadata.
"""

import subprocess
import re
from datetime import datetime
from typing import Optional, Dict, Any
from email.utils import parsedate_to_datetime

from .base_handler import BaseHandler
from utils.date_parser import DateParser


class CLIHandler(BaseHandler):
    """Handler for command-line based metadata extraction."""

    def __init__(self, config: Dict[str, Any], settings: Dict[str, Any] = None):
        super().__init__(config)
        self.settings = settings or {}
        self._raw_timestamp = None
        self.date_parser = DateParser()

    def get_method_name(self) -> str:
        return "cli"

    def fetch_current_timestamp(self) -> Optional[datetime]:
        """
        Fetch timestamp using CLI command (curl -I).

        Returns:
            datetime from Last-Modified header, or None if not available
        """
        url = self.config.get('data_url')
        if not url:
            self.logger.error("No data_url configured")
            return None

        command = self.config.get('command', 'curl -sI')
        full_command = f"{command} \"{url}\""

        http_settings = self.settings.get('http', {})
        timeout = http_settings.get('timeout', 30)

        try:
            self.logger.info(f"Executing: {full_command}")
            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout
            )

            if result.returncode != 0:
                self.logger.error(f"Command failed with code {result.returncode}: {result.stderr}")
                return None

            return self._parse_headers(result.stdout)

        except subprocess.TimeoutExpired:
            self.logger.error(f"Command timed out after {timeout}s")
            return None
        except Exception as e:
            self.handle_error(e)
            return None

    def _parse_headers(self, output: str) -> Optional[datetime]:
        """Parse HTTP headers from curl output."""
        lines = output.strip().split('\n')

        for line in lines:
            # Check for Last-Modified header
            if line.lower().startswith('last-modified:'):
                value = line.split(':', 1)[1].strip()
                self._raw_timestamp = value
                try:
                    return parsedate_to_datetime(value)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Failed to parse Last-Modified: {value}")
                    # Try custom parser
                    return self.date_parser.parse(value)

        # Try Date header as fallback
        for line in lines:
            if line.lower().startswith('date:'):
                value = line.split(':', 1)[1].strip()
                self._raw_timestamp = value
                try:
                    return parsedate_to_datetime(value)
                except (ValueError, TypeError):
                    return self.date_parser.parse(value)

        self.logger.warning("No timestamp headers found in curl output")
        return None

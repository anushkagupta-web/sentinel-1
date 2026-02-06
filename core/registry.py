"""
Source Registry - Maps DCIDs to handlers and configurations.
"""

import os
import yaml
from typing import Dict, Any, Optional, Type

from handlers.base_handler import BaseHandler
from handlers.http_handler import HTTPHandler
from handlers.api_handler import APIHandler
from handlers.selenium_handler import SeleniumHandler
from handlers.bs4_handler import BS4Handler
from handlers.cli_handler import CLIHandler


class SourceRegistry:
    """Registry that manages data source configurations and handler instantiation."""

    # Map method names to handler classes
    HANDLER_MAP: Dict[str, Type[BaseHandler]] = {
        'http_head': HTTPHandler,
        'api': APIHandler,
        'selenium': SeleniumHandler,
        'beautifulsoup': BS4Handler,
        'cli': CLIHandler,
    }

    def __init__(self, config_path: str = None, settings_path: str = None):
        """
        Initialize the registry with configuration files.

        Args:
            config_path: Path to sources.yaml
            settings_path: Path to settings.yaml
        """
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        if config_path is None:
            config_path = os.path.join(self.base_dir, 'config', 'sources.yaml')
        if settings_path is None:
            settings_path = os.path.join(self.base_dir, 'config', 'settings.yaml')

        self.sources = self._load_config(config_path)
        self.settings = self._load_config(settings_path)

    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load YAML configuration file."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"Warning: Config file not found: {path}")
            return {}
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file {path}: {e}")
            return {}

    def get_source(self, dcid: str) -> Optional[Dict[str, Any]]:
        """
        Get source configuration by DCID.

        Args:
            dcid: Data Commons ID

        Returns:
            Source configuration dictionary or None
        """
        return self.sources.get(dcid)

    def get_all_sources(self) -> Dict[str, Dict[str, Any]]:
        """Get all source configurations."""
        return self.sources

    def get_handler(self, dcid: str) -> Optional[BaseHandler]:
        """
        Get appropriate handler instance for a source.

        Args:
            dcid: Data Commons ID

        Returns:
            Handler instance or None if source not found
        """
        source_config = self.get_source(dcid)
        if not source_config:
            print(f"Source not found: {dcid}")
            return None

        method = source_config.get('method')
        if not method:
            print(f"No method specified for source: {dcid}")
            return None

        handler_class = self.HANDLER_MAP.get(method)
        if not handler_class:
            print(f"Unknown method '{method}' for source: {dcid}")
            return None

        # Add dcid to config for logging
        config = {**source_config, 'dcid': dcid}

        return handler_class(config, self.settings)

    def list_sources(self) -> list:
        """List all available DCIDs."""
        return list(self.sources.keys())

    def get_settings(self) -> Dict[str, Any]:
        """Get application settings."""
        return self.settings

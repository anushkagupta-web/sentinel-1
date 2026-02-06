"""
Sentinel - Automated Data Source Monitoring Agent

A lightweight monitoring agent that detects updates in external data sources
by examining metadata (timestamps, ETags) without downloading entire datasets.
"""

from .core.sentinel import Sentinel, check_for_updates
from .core.registry import SourceRegistry
from .core.state_manager import StateManager
from .models.check_result import CheckResult
from .models.source import DataSource

__version__ = "1.0.0"
__all__ = [
    'Sentinel',
    'check_for_updates',
    'SourceRegistry',
    'StateManager',
    'CheckResult',
    'DataSource',
]

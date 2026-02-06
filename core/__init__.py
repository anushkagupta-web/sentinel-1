"""
Core package - Contains main business logic.
"""

from core.registry import SourceRegistry
from core.state_manager import StateManager
from core.sentinel import Sentinel, check_for_updates

__all__ = [
    'SourceRegistry',
    'StateManager',
    'Sentinel',
    'check_for_updates'
]

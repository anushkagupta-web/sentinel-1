"""
Abstract base handler for all retrieval methods.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict, Any
import logging


class BaseHandler(ABC):
    """Abstract base class for all data source handlers."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize handler with source configuration.

        Args:
            config: Source configuration dictionary
        """
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def fetch_current_timestamp(self) -> Optional[datetime]:
        """
        Fetch the current last-modified timestamp from the data source.

        Returns:
            datetime object if timestamp found, None otherwise
        """
        pass

    @abstractmethod
    def get_method_name(self) -> str:
        """
        Get the name of the retrieval method.

        Returns:
            String identifier for this method
        """
        pass

    def get_raw_timestamp(self) -> Optional[str]:
        """
        Get the raw timestamp string before parsing.
        Useful for debugging and logging.

        Returns:
            Raw timestamp string if available
        """
        return getattr(self, '_raw_timestamp', None)

    def compare_with_stored(
        self,
        current: Optional[datetime],
        stored: Optional[datetime]
    ) -> bool:
        """
        Compare current timestamp with stored timestamp.

        Args:
            current: Current timestamp from source
            stored: Previously stored timestamp

        Returns:
            True if source has been updated, False otherwise
        """
        if current is None:
            return False
        if stored is None:
            return True
        return current > stored

    def handle_error(self, exception: Exception) -> None:
        """
        Handle errors during timestamp retrieval.

        Args:
            exception: The exception that occurred
        """
        self.logger.error(
            f"Error fetching timestamp for {self.config.get('dcid', 'unknown')}: "
            f"{type(exception).__name__}: {str(exception)}"
        )

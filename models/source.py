"""
Data Source model.
"""

from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class DataSource:
    """Represents a data source configuration."""

    dcid: str
    import_name: str
    method: str
    data_url: str
    script_url: str = ""
    selector: Optional[str] = None
    wait_timeout: int = 15
    timestamp_field: str = "updated_at"
    response_format: str = "json"
    fallback_fields: List[str] = field(default_factory=list)
    date_patterns: List[str] = field(default_factory=list)
    command: str = "curl -sI"

    @classmethod
    def from_dict(cls, dcid: str, data: dict) -> 'DataSource':
        """Create DataSource from configuration dictionary."""
        return cls(
            dcid=dcid,
            import_name=data.get('import_name', dcid),
            method=data.get('method', 'http_head'),
            data_url=data.get('data_url', ''),
            script_url=data.get('script_url', ''),
            selector=data.get('selector'),
            wait_timeout=data.get('wait_timeout', 15),
            timestamp_field=data.get('timestamp_field', 'updated_at'),
            response_format=data.get('response_format', 'json'),
            fallback_fields=data.get('fallback_fields', []),
            date_patterns=data.get('date_patterns', []),
            command=data.get('command', 'curl -sI'),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'dcid': self.dcid,
            'import_name': self.import_name,
            'method': self.method,
            'data_url': self.data_url,
            'script_url': self.script_url,
            'selector': self.selector,
            'wait_timeout': self.wait_timeout,
            'timestamp_field': self.timestamp_field,
            'response_format': self.response_format,
            'fallback_fields': self.fallback_fields,
            'date_patterns': self.date_patterns,
            'command': self.command,
        }

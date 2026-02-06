"""
Check Result model.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class CheckResult:
    """Represents the result of checking a data source for updates."""

    dcid: str
    import_name: Optional[str] = None
    data_url: Optional[str] = None
    script_url: Optional[str] = None
    method: Optional[str] = None
    changed: bool = False
    current_timestamp: Optional[datetime] = None
    previous_timestamp: Optional[datetime] = None
    raw_timestamp: Optional[str] = None
    error: Optional[str] = None
    check_time: datetime = field(default_factory=datetime.now)

    # Groq verification fields
    is_verified: Optional[bool] = None
    verification_confidence: float = 0.0
    verification_reasoning: Optional[str] = None
    suggested_timestamp: Optional[str] = None

    def __str__(self) -> str:
        status = "UPDATED" if self.changed else "NO CHANGE"
        if self.error:
            status = f"ERROR: {self.error}"

        verification_status = ""
        if self.is_verified is not None:
            verified_str = "VERIFIED" if self.is_verified else "NOT VERIFIED"
            verification_status = f"\n  Verification: {verified_str} (confidence: {self.verification_confidence:.0%})"

        return (
            f"[{status}] {self.import_name or self.dcid}\n"
            f"  Current:  {self.current_timestamp}\n"
            f"  Previous: {self.previous_timestamp}"
            f"{verification_status}"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'dcid': self.dcid,
            'import_name': self.import_name,
            'data_url': self.data_url,
            'script_url': self.script_url,
            'method': self.method,
            'changed': self.changed,
            'current_timestamp': self.current_timestamp.isoformat() if self.current_timestamp else None,
            'previous_timestamp': self.previous_timestamp.isoformat() if self.previous_timestamp else None,
            'raw_timestamp': self.raw_timestamp,
            'error': self.error,
            'check_time': self.check_time.isoformat() if self.check_time else None,
            # Verification fields
            'is_verified': self.is_verified,
            'verification_confidence': self.verification_confidence,
            'verification_reasoning': self.verification_reasoning,
            'suggested_timestamp': self.suggested_timestamp,
        }

    @property
    def is_success(self) -> bool:
        """Check if the operation was successful."""
        return self.error is None

    @property
    def status(self) -> str:
        """Get status string."""
        if self.error:
            return 'error'
        return 'updated' if self.changed else 'unchanged'

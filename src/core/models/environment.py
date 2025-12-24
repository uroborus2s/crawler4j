"""Environment model.

Represents a browser environment binding Ctrip account, Labor account, and browser profile.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EnvironmentStatus(str, Enum):
    """Environment status enumeration."""
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"


@dataclass
class Environment:
    """Browser environment model.
    
    An environment binds:
    - One Ctrip account
    - One Labor account
    - One browser profile (fingerprint browser)
    
    This binding is persistent - when reopening the environment,
    both platforms should remain logged in.
    
    Attributes:
        id: Unique identifier.
        ctrip_account_id: Associated Ctrip account ID.
        labor_account_id: Associated Labor account ID.
        browser_profile_id: Browser profile ID from BitBrowser/VirtualBrowser.
        status: Environment status (idle/running/error).
        last_run_at: Last execution timestamp.
        created_at: Environment creation timestamp.
    """
    
    ctrip_account_id: int
    labor_account_id: int
    browser_profile_id: str
    id: int | None = None
    status: EnvironmentStatus = EnvironmentStatus.IDLE
    last_run_at: datetime | None = None
    created_at: datetime | None = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "Environment":
        """Create instance from dictionary."""
        status = data.get("status", "idle")
        if isinstance(status, str):
            status = EnvironmentStatus(status)
        
        return cls(
            id=data.get("id"),
            ctrip_account_id=data["ctrip_account_id"],
            labor_account_id=data["labor_account_id"],
            browser_profile_id=data["browser_profile_id"],
            status=status,
            last_run_at=data.get("last_run_at"),
            created_at=data.get("created_at"),
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "ctrip_account_id": self.ctrip_account_id,
            "labor_account_id": self.labor_account_id,
            "browser_profile_id": self.browser_profile_id,
            "status": self.status.value if isinstance(self.status, EnvironmentStatus) else self.status,
            "last_run_at": self.last_run_at,
            "created_at": self.created_at,
        }
    
    @property
    def is_idle(self) -> bool:
        """Check if environment is idle."""
        return self.status == EnvironmentStatus.IDLE
    
    @property
    def is_running(self) -> bool:
        """Check if environment is running."""
        return self.status == EnvironmentStatus.RUNNING
    
    @property
    def display_id(self) -> str:
        """Get display ID for UI."""
        return f"ENV-{self.id}" if self.id else "ENV-NEW"

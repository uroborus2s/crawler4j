"""Labor account model.

Represents a Labor platform account with task statistics.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AccountStatus(str, Enum):
    """Account status enumeration."""
    ACTIVE = "active"
    BLACKLISTED = "blacklisted"
    DISABLED = "disabled"


@dataclass
class LaborAccount:
    """Labor platform account model.
    
    Attributes:
        id: Unique identifier.
        phone: Login phone number/username.
        password: Login password.
        status: Account status (active/blacklisted/disabled).
        completed_count: Number of completed tasks.
        discarded_count: Number of discarded tasks.
        approved_count: Number of approved tasks.
        rejected_count: Number of rejected tasks.
        created_at: Account creation timestamp.
        updated_at: Last update timestamp.
    """
    
    phone: str
    password: str
    id: int | None = None
    status: AccountStatus = AccountStatus.ACTIVE
    completed_count: int = 0
    discarded_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "LaborAccount":
        """Create instance from dictionary."""
        status = data.get("status", "active")
        if isinstance(status, str):
            status = AccountStatus(status)
        
        return cls(
            id=data.get("id"),
            phone=data["phone"],
            password=data["password"],
            status=status,
            completed_count=data.get("completed_count", 0),
            discarded_count=data.get("discarded_count", 0),
            approved_count=data.get("approved_count", 0),
            rejected_count=data.get("rejected_count", 0),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "phone": self.phone,
            "password": self.password,
            "status": self.status.value if isinstance(self.status, AccountStatus) else self.status,
            "completed_count": self.completed_count,
            "discarded_count": self.discarded_count,
            "approved_count": self.approved_count,
            "rejected_count": self.rejected_count,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @property
    def total_tasks(self) -> int:
        """Total number of tasks processed."""
        return self.completed_count + self.discarded_count
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate (approved / completed)."""
        if self.completed_count == 0:
            return 0.0
        return self.approved_count / self.completed_count
    
    @property
    def is_active(self) -> bool:
        """Check if account is active."""
        return self.status == AccountStatus.ACTIVE

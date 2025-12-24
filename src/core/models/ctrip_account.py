"""Ctrip account model.

Represents a Ctrip platform account with SMS verification configuration.
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
class CtripAccount:
    """Ctrip platform account model.
    
    Attributes:
        id: Unique identifier.
        phone: Login phone number.
        password: Login password (optional if using SMS).
        status: Account status (active/blacklisted/disabled).
        sms_platform_url: SMS verification platform API URL.
        sms_platform_key: SMS verification platform API key.
        sms_platform_type: SMS platform type identifier.
        created_at: Account creation timestamp.
        updated_at: Last update timestamp.
    """
    
    phone: str
    id: int | None = None
    password: str | None = None
    status: AccountStatus = AccountStatus.ACTIVE
    sms_platform_url: str | None = None
    sms_platform_key: str | None = None
    sms_platform_type: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "CtripAccount":
        """Create instance from dictionary."""
        status = data.get("status", "active")
        if isinstance(status, str):
            status = AccountStatus(status)
        
        return cls(
            id=data.get("id"),
            phone=data["phone"],
            password=data.get("password"),
            status=status,
            sms_platform_url=data.get("sms_platform_url"),
            sms_platform_key=data.get("sms_platform_key"),
            sms_platform_type=data.get("sms_platform_type"),
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
            "sms_platform_url": self.sms_platform_url,
            "sms_platform_key": self.sms_platform_key,
            "sms_platform_type": self.sms_platform_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @property
    def masked_phone(self) -> str:
        """Return masked phone number for display."""
        if len(self.phone) >= 7:
            return f"{self.phone[:3]}****{self.phone[-4:]}"
        return self.phone
    
    @property
    def is_active(self) -> bool:
        """Check if account is active."""
        return self.status == AccountStatus.ACTIVE
    
    @property
    def has_sms_config(self) -> bool:
        """Check if SMS verification is configured."""
        return bool(self.sms_platform_url and self.sms_platform_key)

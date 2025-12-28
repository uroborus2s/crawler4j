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
        country_code: Country code for phone number (default +86).
        phone_number: Login phone number.
        password: Login password (optional if using SMS).
        status: Account status (active/blacklisted/disabled).
        consecutive_task_count: Number of consecutive tasks before break.
        task_interval_max: Maximum interval between tasks (minutes).
        sms_platform_url: SMS verification platform API URL.
        sms_platform_key: SMS verification platform API key.
        sms_platform_type: SMS platform type identifier.
        created_at: Account creation timestamp.
        updated_at: Last update timestamp.
    """
    
    phone_number: str
    id: int | None = None
    country_code: str = "+86"
    password: str | None = None
    status: AccountStatus = AccountStatus.ACTIVE
    consecutive_task_count: int = 5
    task_interval_max: int = 15
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
            country_code=data.get("country_code", "+86"),
            phone_number=data.get("phone_number", data.get("phone", "")),
            password=data.get("password"),
            status=status,
            consecutive_task_count=data.get("consecutive_task_count", 5),
            task_interval_max=data.get("task_interval_max", 15),
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
            "country_code": self.country_code,
            "phone_number": self.phone_number,
            "password": self.password,
            "status": self.status.value if isinstance(self.status, AccountStatus) else self.status,
            "consecutive_task_count": self.consecutive_task_count,
            "task_interval_max": self.task_interval_max,
            "sms_platform_url": self.sms_platform_url,
            "sms_platform_key": self.sms_platform_key,
            "sms_platform_type": self.sms_platform_type,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @property
    def full_phone(self) -> str:
        """Return full phone with country code."""
        return f"{self.country_code}{self.phone_number}"
    
    @property
    def masked_phone(self) -> str:
        """Return masked phone number for display."""
        phone = self.phone_number
        if len(phone) >= 7:
            return f"{self.country_code}{phone[:3]}****{phone[-4:]}"
        return f"{self.country_code}{phone}"
    
    @property
    def is_active(self) -> bool:
        """Check if account is active."""
        return self.status == AccountStatus.ACTIVE
    
    @property
    def has_sms_config(self) -> bool:
        """Check if SMS verification is configured."""
        return bool(self.sms_platform_url and self.sms_platform_key)

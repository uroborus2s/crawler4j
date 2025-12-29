"""Ctrip account model.

Represents a Ctrip platform account with SMS verification configuration.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class AccountStatus(str, Enum):
    """Account status enumeration."""
    IDLE = "idle"              # 空闲，可绑定
    ACTIVE = "active"          # 已绑定，待运行
    RUNNING = "running"        # 运行中
    BLACKLISTED = "blacklisted"  # 黑名单
    DISABLED = "disabled"      # 禁用


class AccountType(str, Enum):
    """账号创建类型。"""
    MANUAL = "manual"   # 手动创建
    API = "api"         # API 自动创建


class SmsVerifyType(str, Enum):
    """短信验证类型。"""
    MANUAL = "manual"   # 手动接码
    AUTO = "auto"       # 自动接码平台


@dataclass
class CtripAccount:
    """Ctrip platform account model.
    
    Attributes:
        id: Unique identifier.
        country_code: Country code for phone number (default +86).
        phone_number: Login phone number.
        password: Login password (optional if using SMS).
        status: Account status (idle/active/running/blacklisted/disabled).
        account_type: Account creation type (manual/api).
        sms_verify_type: SMS verification method (manual/auto).
        consecutive_task_count: Number of consecutive tasks before break.
        task_interval_max: Maximum interval between tasks (minutes).
        sms_platform_url: SMS verification platform API URL.
        sms_platform_key: SMS verification platform API key.
        sms_platform_type: Legacy field, replaced by sms_verify_type.
        created_at: Account creation timestamp.
        updated_at: Last update timestamp.
    """
    
    phone_number: str
    id: int | None = None
    country_code: str = "+86"
    password: str | None = None
    status: AccountStatus = AccountStatus.IDLE
    account_type: AccountType = AccountType.MANUAL
    sms_verify_type: SmsVerifyType = SmsVerifyType.MANUAL
    consecutive_task_count: int = 5
    task_interval_max: int = 15
    sms_platform_url: str | None = None
    sms_platform_key: str | None = None
    sms_platform_type: str | None = None  # 兑容旧字段
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "CtripAccount":
        """Create instance from dictionary."""
        status = data.get("status", "idle")
        if isinstance(status, str):
            try:
                status = AccountStatus(status)
            except ValueError:
                status = AccountStatus.IDLE
        
        account_type = data.get("account_type", "manual")
        if isinstance(account_type, str):
            try:
                account_type = AccountType(account_type)
            except ValueError:
                account_type = AccountType.MANUAL
        
        # sms_verify_type 优先继承旧的 sms_platform_type 语义
        sms_verify_type = data.get("sms_verify_type") or data.get("sms_platform_type") or "manual"
        if isinstance(sms_verify_type, str):
            if sms_verify_type in ("manual", "auto"):
                sms_verify_type = SmsVerifyType(sms_verify_type)
            else:
                sms_verify_type = SmsVerifyType.MANUAL
        
        return cls(
            id=data.get("id"),
            country_code=data.get("country_code", "+86"),
            phone_number=data.get("phone_number", data.get("phone", "")),
            password=data.get("password"),
            status=status,
            account_type=account_type,
            sms_verify_type=sms_verify_type,
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
            "account_type": self.account_type.value if isinstance(self.account_type, AccountType) else self.account_type,
            "sms_verify_type": self.sms_verify_type.value if isinstance(self.sms_verify_type, SmsVerifyType) else self.sms_verify_type,
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

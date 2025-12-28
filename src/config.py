"""Configuration loader module.

Provides access to application settings from the database.
"""

from typing import Any

from src.utils.storage import SettingsRepository


class Config:
    """Application configuration manager.
    
    Reads and writes settings from the database settings table.
    Provides typed access to common settings.
    
    Usage:
        config = Config()
        browser_type = config.browser_type
        config.concurrency_limit = 20
    """
    
    _instance: "Config | None" = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._repo = SettingsRepository()
        self._cache: dict[str, Any] = {}
        self._initialized = True
    
    def _get(self, key: str, default: Any = None) -> Any:
        """Get a setting value with caching."""
        if key not in self._cache:
            self._cache[key] = self._repo.get(key, default)
        return self._cache[key]
    
    def _set(self, key: str, value: Any) -> None:
        """Set a setting value and update cache."""
        self._repo.set(key, value)
        self._cache[key] = value
    
    def reload(self) -> None:
        """Clear cache and reload all settings."""
        self._cache.clear()
    
    # Browser settings
    
    @property
    def browser_type(self) -> str:
        """Browser type: 'bitbrowser' or 'virtualbrowser'."""
        return self._get("browser_type", "bitbrowser")
    
    @browser_type.setter
    def browser_type(self, value: str) -> None:
        self._set("browser_type", value)
    
    @property
    def browser_api_url(self) -> str:
        """Browser API URL."""
        return self._get("browser_api_url", "http://127.0.0.1:54345")
    
    @browser_api_url.setter
    def browser_api_url(self, value: str) -> None:
        self._set("browser_api_url", value)
    
    # Task settings
    
    @property
    def concurrency_limit(self) -> int:
        """Maximum number of concurrent environments."""
        return self._get("concurrency_limit", 10)
    
    @concurrency_limit.setter
    def concurrency_limit(self, value: int) -> None:
        self._set("concurrency_limit", max(1, min(20, value)))
    
    @property
    def task_interval(self) -> int:
        """Interval between tasks in seconds."""
        return self._get("task_interval", 5)
    
    @task_interval.setter
    def task_interval(self, value: int) -> None:
        self._set("task_interval", max(1, min(60, value)))
    
    @property
    def retry_count(self) -> int:
        """Number of retries on failure."""
        return self._get("retry_count", 3)
    
    @retry_count.setter
    def retry_count(self, value: int) -> None:
        self._set("retry_count", max(0, min(5, value)))
    
    # SMS platform settings
    
    @property
    def default_sms_platform(self) -> str:
        """Default SMS platform type."""
        return self._get("default_sms_platform", "")
    
    @default_sms_platform.setter
    def default_sms_platform(self, value: str) -> None:
        self._set("default_sms_platform", value)
    
    @property
    def default_sms_url(self) -> str:
        """Default SMS platform API URL."""
        return self._get("default_sms_url", "")
    
    @default_sms_url.setter
    def default_sms_url(self, value: str) -> None:
        self._set("default_sms_url", value)
    
    @property
    def default_sms_key(self) -> str:
        """Default SMS platform API key."""
        return self._get("default_sms_key", "")
    
    @default_sms_key.setter
    def default_sms_key(self, value: str) -> None:
        self._set("default_sms_key", value)
    
    # Custom path settings
    
    @property
    def bitbrowser_path(self) -> str:
        """Custom path for BitBrowser."""
        return self._get("bitbrowser_path", "")
    
    @bitbrowser_path.setter
    def bitbrowser_path(self, value: str) -> None:
        self._set("bitbrowser_path", value)
        
    @property
    def virtualbrowser_path(self) -> str:
        """Custom path for VirtualBrowser."""
        return self._get("virtualbrowser_path", "")
    
    @virtualbrowser_path.setter
    def virtualbrowser_path(self, value: str) -> None:
        self._set("virtualbrowser_path", value)

    def to_dict(self) -> dict[str, Any]:
        """Get all settings as a dictionary."""
        return {
            "browser_type": self.browser_type,
            "browser_api_url": self.browser_api_url,
            "concurrency_limit": self.concurrency_limit,
            "task_interval": self.task_interval,
            "retry_count": self.retry_count,
            "default_sms_platform": self.default_sms_platform,
            "default_sms_url": self.default_sms_url,
            "default_sms_key": self.default_sms_key,
            "bitbrowser_path": self.bitbrowser_path,
            "virtualbrowser_path": self.virtualbrowser_path,
        }


# Global config instance
config = Config()

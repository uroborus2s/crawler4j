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
            try:
                # Use a fresh repository instance to avoid circular imports or stale state
                # Note: We rely on _repo initialized in __init__ which is fine for now
                # but for dynamic loading we might want to ensure fresh read
                val = self._repo.get(key)
                self._cache[key] = val if val is not None else default
            except Exception:
                # If DB is not ready or error, return default and don't cache
                return default
        return self._cache[key]

    def _set(self, key: str, value: Any) -> None:
        """Set a setting value and update cache."""
        try:
            self._repo.set(key, value)
            self._cache[key] = value
        except Exception as e:
            print(f"Failed to save setting {key}: {e}")

    def refresh(self, key: str) -> Any:
        """Force refresh a specific key from DB."""
        if key in self._cache:
            del self._cache[key]
        return self._get(key)

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

    @property
    def daily_auto_env_creation_limit(self) -> int:
        """每日自动创建环境（接码）的数量限制。"""
        return self._get("daily_auto_env_creation_limit", 50)

    @daily_auto_env_creation_limit.setter
    def daily_auto_env_creation_limit(self, value: int) -> None:
        self._set("daily_auto_env_creation_limit", max(1, min(200, value)))

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

    # SMS Platform settings (接码平台)

    @property
    def sms_platform_host(self) -> str:
        """接码平台域名，格式如 3.112.30.233:8000"""
        return self._get("sms_platform_host", "")

    @sms_platform_host.setter
    def sms_platform_host(self, value: str) -> None:
        self._set("sms_platform_host", value)

    @property
    def sms_platform_username(self) -> str:
        """接码平台用户名。"""
        return self._get("sms_platform_username", "")

    @sms_platform_username.setter
    def sms_platform_username(self, value: str) -> None:
        self._set("sms_platform_username", value)

    @property
    def sms_platform_password(self) -> str:
        """接码平台密码。"""
        return self._get("sms_platform_password", "")

    @sms_platform_password.setter
    def sms_platform_password(self, value: str) -> None:
        self._set("sms_platform_password", value)

    @property
    def sms_platform_product_id(self) -> str:
        """接码平台项目ID。"""
        return self._get("sms_platform_product_id", "")

    @sms_platform_product_id.setter
    def sms_platform_product_id(self, value: str) -> None:
        self._set("sms_platform_product_id", value)

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
            "sms_platform_host": self.sms_platform_host,
            "sms_platform_username": self.sms_platform_username,
            "sms_platform_password": self.sms_platform_password,
            "sms_platform_product_id": self.sms_platform_product_id,
        }


# Global config instance
config = Config()

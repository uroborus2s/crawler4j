"""偏好设置服务。

封装系统级配置的读写，提供：
- 统一的配置键管理
- 配置变更事件
- 默认值处理
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from src.core.persistence import get_config_store


class PreferenceKey(str, Enum):
    """偏好设置键枚举。"""

    # General
    LOCALE = "system.locale"
    THEME = "system.theme"
    AUTO_UPDATE = "system.auto_update"
    AUTOSTART = "system.autostart"
    MINIMIZE_ON_START = "system.minimize_on_start"

    # Network
    PROXY_MODE = "network.proxy_mode"
    HTTP_PROXY = "network.http_proxy"

    # Resources
    # (Removed MAX_CONCURRENCY, delegated to strategy)

    # Browser
    BITBROWSER_PORT = "browser.bitbrowser.port"
    BITBROWSER_PATH = "browser.bitbrowser.path"
    VIRTUALBROWSER_PORT = "browser.virtualbrowser.port"
    VIRTUALBROWSER_PATH = "browser.virtualbrowser.path"
    VIRTUALBROWSER_API_KEY = "browser.virtualbrowser.apikey"

    # Logging
    LOG_LEVEL = "logging.level"
    LOG_RETENTION = "logging.retention_days"
    
    # REM (Runtime Environment Manager)
    ENV_MAX_INSTANCES = "rem.max_instances"


# 默认值映射
PREFERENCE_DEFAULTS: dict[PreferenceKey, Any] = {
    PreferenceKey.LOCALE: "system",
    PreferenceKey.THEME: "dark",
    PreferenceKey.AUTO_UPDATE: True,
    PreferenceKey.AUTOSTART: False,
    PreferenceKey.MINIMIZE_ON_START: False,
    PreferenceKey.PROXY_MODE: "system",
    PreferenceKey.HTTP_PROXY: "",
    PreferenceKey.BITBROWSER_PORT: 54345,
    PreferenceKey.BITBROWSER_PATH: "",
    PreferenceKey.VIRTUALBROWSER_PORT: 9002,
    PreferenceKey.VIRTUALBROWSER_PATH: "",
    PreferenceKey.VIRTUALBROWSER_API_KEY: "",
    PreferenceKey.LOG_LEVEL: "INFO",
    PreferenceKey.LOG_RETENTION: 29,
    PreferenceKey.ENV_MAX_INSTANCES: 50,
}

# 需要重启才能生效的配置
REQUIRES_RESTART: set[PreferenceKey] = {
    PreferenceKey.LOCALE,
    PreferenceKey.PROXY_MODE,
}


class PreferencesService(QObject):
    """偏好设置服务。

    Signals:
        preference_changed: 配置变更时发出 (key, value, requires_restart)
    """

    preference_changed = pyqtSignal(str, object, bool)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._store = get_config_store()

    def get(self, key: PreferenceKey | str, default: Any = None) -> Any:
        """获取配置值。

        Args:
            key: 配置键 (PreferenceKey 或字符串)
            default: 默认值（如为 None 则使用预定义默认值）

        Returns:
            配置值
        """
        import json
        
        key_str = key.value if isinstance(key, PreferenceKey) else key

        # 从 settings 表获取
        value_str = self._store.get_setting(key_str)
        if value_str is not None:
            return json.loads(value_str)

        # 回退到默认值
        if default is not None:
            return default

        if isinstance(key, PreferenceKey) and key in PREFERENCE_DEFAULTS:
            return PREFERENCE_DEFAULTS[key]

        return None

    def set(self, key: PreferenceKey | str, value: Any) -> bool:
        """设置配置值。

        Args:
            key: 配置键
            value: 配置值

        Returns:
            True 如果需要重启生效
        """
        import json
        
        key_str = key.value if isinstance(key, PreferenceKey) else key
        value_str = json.dumps(value, ensure_ascii=False)

        # 更新 settings 表
        self._store.set_setting(key_str, value_str)

        # 判断是否需要重启
        requires_restart = (
            isinstance(key, PreferenceKey) and key in REQUIRES_RESTART
        )

        # 发出变更信号
        self.preference_changed.emit(key_str, value, requires_restart)

        return requires_restart

    def get_all(self) -> dict[str, Any]:
        """获取所有配置。"""
        import json
        
        # 从 settings 表获取所有值
        stored = self._store.get_all_settings()

        # 合并默认值
        result = {}
        for key in PreferenceKey:
            if key.value in stored:
                result[key.value] = json.loads(stored[key.value])
            else:
                result[key.value] = PREFERENCE_DEFAULTS.get(key)

        return result

    def reset_to_defaults(self) -> None:
        """重置为默认值。"""
        for key, value in PREFERENCE_DEFAULTS.items():
            self.set(key, value)


# 单例
_preferences_service: Optional[PreferencesService] = None


def get_preferences_service() -> PreferencesService:
    """获取 PreferencesService 单例。"""
    global _preferences_service
    if _preferences_service is None:
        _preferences_service = PreferencesService()
    return _preferences_service
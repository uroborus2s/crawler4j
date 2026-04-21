"""System 模块 - 系统基础能力。

提供 Framework Core 的基础系统能力：
- VersionService: 版本管理
- UpdateService: 应用更新
- PreferencesService: 偏好设置
"""

from src.core.system.preferences_service import (
    PreferencesService,
    get_preferences_service,
)
from src.core.system.update_service import (
    UpdateService,
    get_update_service,
)
from src.core.system.version_service import (
    BuildInfo,
    VersionService,
    get_version_service,
)

__all__ = [
    # Version
    "BuildInfo",
    "VersionService",
    "get_version_service",
    # Update
    "UpdateService",
    "get_update_service",
    # Preferences
    "PreferencesService",
    "get_preferences_service",
]

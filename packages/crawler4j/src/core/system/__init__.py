"""System 模块 - 系统基础能力。

提供 Framework Core 的基础系统能力：
- VersionService: 版本管理
- UpdateService: 应用更新
- ConfigCenterService: 配置中心
"""

from src.core.system.config_center import (
    ConfigCenterService,
    get_config_center,
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
    # Config Center
    "ConfigCenterService",
    "get_config_center",
]

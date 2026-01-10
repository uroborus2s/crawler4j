"""运行环境管理 (Runtime Environment Management)。

规格参考: docs/srs/05-framework-core/05-2-runtime-environment-management.md

导出:
    - Environment, EnvLease, EnvRequirement: 数据模型
    - EnvKind, EnvStatus: 枚举
    - EnvironmentManager, get_environment_manager: 环境管理器
    - BaseProvider, PlaywrightProvider: Provider
"""

from src.core.rem.manager import EnvironmentManager, get_environment_manager
from src.core.rem.models import (
    EnvCleanupFailedError,
    EnvError,
    Environment,
    EnvKind,
    EnvLease,
    EnvRequirement,
    EnvStatus,
    EnvUnavailableError,
    EnvUnhealthyError,
)
from src.core.rem.pool import EnvPool, LeaseManager
from src.core.rem.provider import (
    BaseProvider,
    PlaywrightProvider,
    get_provider,
    list_providers,
    register_provider,
)

__all__ = [
    # 数据模型
    "Environment",
    "EnvLease",
    "EnvRequirement",
    # 枚举
    "EnvKind",
    "EnvStatus",
    # 错误
    "EnvError",
    "EnvUnavailableError",
    "EnvUnhealthyError",
    "EnvCleanupFailedError",
    # Provider
    "BaseProvider",
    "PlaywrightProvider",
    "register_provider",
    "get_provider",
    "list_providers",
    # Pool
    "EnvPool",
    "LeaseManager",
    # Manager
    "EnvironmentManager",
    "get_environment_manager",
]

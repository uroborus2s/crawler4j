"""运行环境管理 (Runtime Environment Management)。

规格参考: docs/srs/05-framework-core/05-2-runtime-environment-management.md

导出:
    - Environment, EnvLease, EnvRequirement: 数据模型
    - EnvKind, EnvStatus, ProxyMode: 枚举
    - ProxyConfig, FingerprintConfig: 配置类
    - EnvironmentManager, get_environment_manager: 环境管理器
    - BaseProvider: Provider
    - IPPool, IPEntry, IPPoolManager: IP 池管理
    - ExternalSyncManager: 外部状态同步
    - FingerprintProvider: 指纹配置协议
"""

from src.core.rem.fingerprint import FingerprintNotSupportedError, FingerprintProvider, supports_fingerprint
from src.core.rem.ip_pool import IPEntry, IPPool, IPPoolManager, IPStrategy, get_ip_pool_manager
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
    FingerprintConfig,
    PostCreateAction,
    ProxyConfig,
    ProxyMode,
)
from src.core.rem.pool import EnvPool, LeaseManager
from src.core.rem.provider import (
    BaseProvider,
    BitBrowserProvider,
    VirtualBrowserProvider,
    get_provider,
    list_providers,
    register_provider,
)
from src.core.rem.sync import ExternalSyncManager

__all__ = [
    # 数据模型
    "Environment",
    "EnvLease",
    "EnvRequirement",
    # 枚举
    "EnvKind",
    "EnvStatus",
    "PostCreateAction",
    "ProxyMode",
    "IPStrategy",
    # 配置类
    "ProxyConfig",
    "FingerprintConfig",
    # 错误
    "EnvError",
    "EnvUnavailableError",
    "EnvUnhealthyError",
    "EnvCleanupFailedError",
    "FingerprintNotSupportedError",
    # Provider
    "BaseProvider",
    "BitBrowserProvider",
    "VirtualBrowserProvider",
    "register_provider",
    "get_provider",
    "list_providers",
    # Pool
    "EnvPool",
    "LeaseManager",
    # Manager
    "EnvironmentManager",
    "get_environment_manager",
    # IP 池
    "IPEntry",
    "IPPool",
    "IPPoolManager",
    "get_ip_pool_manager",
    # 外部同步
    "ExternalSyncManager",
    # 指纹
    "FingerprintProvider",
    "supports_fingerprint",
]

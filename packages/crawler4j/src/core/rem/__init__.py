"""运行环境管理 (Runtime Environment Management) 的延迟导出入口。

该包会被 ATM 执行器、REM 管理器和导入任务服务交叉引用。这里不做 eager import，
避免导入 `src.core.rem.manager` 时触发 `import_job_service -> atm.dispatcher -> execution_runner`
的循环初始化。
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    "FingerprintNotSupportedError": "src.core.rem.fingerprint",
    "FingerprintProvider": "src.core.rem.fingerprint",
    "supports_fingerprint": "src.core.rem.fingerprint",
    "ExistingEnvImportJobService": "src.core.rem.import_job_service",
    "get_existing_env_import_job_service": "src.core.rem.import_job_service",
    "IPEntry": "src.core.rem.ip_pool",
    "IPEntryStatus": "src.core.rem.ip_pool",
    "IPPool": "src.core.rem.ip_pool",
    "IPPoolManager": "src.core.rem.ip_pool",
    "IPStrategy": "src.core.rem.ip_pool",
    "get_ip_pool_manager": "src.core.rem.ip_pool",
    "EnvironmentManager": "src.core.rem.manager",
    "get_environment_manager": "src.core.rem.manager",
    "EnvCleanupFailedError": "src.core.rem.models",
    "EnvError": "src.core.rem.models",
    "Environment": "src.core.rem.models",
    "EnvKind": "src.core.rem.models",
    "EnvLease": "src.core.rem.models",
    "EnvRequirement": "src.core.rem.models",
    "EnvStatus": "src.core.rem.models",
    "EnvUnavailableError": "src.core.rem.models",
    "EnvUnhealthyError": "src.core.rem.models",
    "FingerprintConfig": "src.core.rem.models",
    "ProviderEnvInfo": "src.core.rem.models",
    "ProxyConfig": "src.core.rem.models",
    "ProxyMode": "src.core.rem.models",
    "EnvPool": "src.core.rem.pool",
    "LeaseManager": "src.core.rem.pool",
    "BaseProvider": "src.core.rem.provider",
    "BitBrowserProvider": "src.core.rem.provider",
    "VirtualBrowserProvider": "src.core.rem.provider",
    "get_provider": "src.core.rem.provider",
    "list_providers": "src.core.rem.provider",
    "register_provider": "src.core.rem.provider",
    "ExternalSyncManager": "src.core.rem.sync",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value

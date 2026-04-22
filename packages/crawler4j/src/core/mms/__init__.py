"""模块管理系统 (Module Management System)。

规格参考: docs/02-requirements/reference-srs/05-framework-core/05-1-module-management.md

导出:
    - ModuleInfo, ModuleManifest, etc.: 数据模型
    - ModuleScanner: 模块扫描器
    - ModuleRegistry: 模块注册表
"""

from src.core.mms.dev_links import DevModuleLinkStore, get_dev_module_link_store
from src.core.mms.github_credentials import GitHubCredentialStore, get_github_credential_store
from src.core.mms.models import (
    DevModuleLink,
    ModuleDiscoveryError,
    ModuleError,
    ModuleInfo,
    ModuleInstallError,
    ModuleManifest,
    ModuleParseError,
    ModuleSource,
    ModuleStatus,
    UIPageInfo,
    UpgradeSourceInfo,
    ModuleValidationError,
    UIExtensionInfo,
    WorkflowInfo,
)
from src.core.mms.release_service import (
    ModulePackagePreview,
    ModuleReleaseInfo,
    ModuleReleaseService,
    ModuleUpdateInfo,
    get_module_release_service,
)
from src.core.mms.registry import (
    ModuleRegistry,
    get_module_registry,
)
from src.core.mms.settings_store import ModuleSettingsStore, get_module_settings_store
from src.core.mms.scanner import (
    ModuleScanner,
    get_module_scanner,
)

__all__ = [
    # 数据模型
    "ModuleInfo",
    "ModuleManifest",
    "ModuleSource",
    "ModuleStatus",
    "WorkflowInfo",
    "DevModuleLink",
    "UIPageInfo",
    "UIExtensionInfo",
    "UpgradeSourceInfo",
    # 错误
    "ModuleError",
    "ModuleDiscoveryError",
    "ModuleParseError",
    "ModuleValidationError",
    "ModuleInstallError",
    # 扫描器
    "ModuleScanner",
    "get_module_scanner",
    # 注册表
    "ModuleRegistry",
    "get_module_registry",
    "ModuleReleaseInfo",
    "ModuleUpdateInfo",
    "ModulePackagePreview",
    "ModuleReleaseService",
    "get_module_release_service",
    "ModuleSettingsStore",
    "get_module_settings_store",
    "DevModuleLinkStore",
    "get_dev_module_link_store",
    "GitHubCredentialStore",
    "get_github_credential_store",
]

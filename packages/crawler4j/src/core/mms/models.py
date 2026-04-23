"""MMS 数据模型定义。

规格参考: docs/02-requirements/reference-srs/05-framework-core/05-1-module-management.md

定义模块管理的核心数据实体：
    - ModuleStatus: 模块状态
    - ModuleSource: 模块来源
    - ModuleManifest: 模块清单
    - ModuleInfo: 模块注册信息
"""

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ModuleStatus(StrEnum):
    """模块状态。
    
    规格 5.1.3.3:
        - enabled: 已启用
        - disabled: 已禁用
        - incompatible: 不兼容
        - invalid: 无效
    """
    ENABLED = "enabled"
    DISABLED = "disabled"
    INCOMPATIBLE = "incompatible"
    INVALID = "invalid"


class ModuleSource(StrEnum):
    """模块来源。
    
    规格 5.1.3.3:
        - builtin: 内置模块
        - external: 外部安装模块
        - dev_link: 本地开发链接模块
    """
    BUILTIN = "builtin"
    EXTERNAL = "external"
    DEV_LINK = "dev_link"


@dataclass
class DevModuleLink:
    """本地开发模块链接。"""

    module_name: str
    source_path: str
    created_at: int = 0
    updated_at: int = 0


@dataclass
class WorkflowInfo:
    """工作流信息。"""
    name: str
    display_name: str = ""
    description: str = ""
    entry_class: str = ""
    tasks: list[str] = field(default_factory=list)


@dataclass
class UIPageInfo:
    """模块宿主页入口声明。"""

    id: str
    icon: str = "📋"
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "icon": self.icon,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "UIPageInfo":
        if not isinstance(data, dict):
            raise ValueError("ui_extension.pages 中的每一项都必须是 YAML 映射对象")

        allowed_keys = {"id", "icon", "label"}
        unknown_keys = sorted(set(data) - allowed_keys)
        if unknown_keys:
            raise ValueError(
                "ui_extension.pages 包含不支持的字段: " + ", ".join(unknown_keys)
            )

        return cls(
            id=str(data.get("id", "") or "").strip(),
            icon=str(data.get("icon", "📋") or "📋").strip() or "📋",
            label=str(data.get("label", "") or "").strip(),
        )


@dataclass
class UIExtensionInfo:
    """UI 扩展信息。

    当前只保留宿主页入口列表契约。
    """

    pages: list[UIPageInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pages": [page.to_dict() for page in self.pages],
        }

    @classmethod
    def from_dict(cls, data: Any) -> "UIExtensionInfo":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("ui_extension 必须是 YAML 映射对象")

        allowed_keys = {"pages"}
        unknown_keys = sorted(set(data) - allowed_keys)
        if unknown_keys:
            raise ValueError("ui_extension 包含不支持的字段: " + ", ".join(unknown_keys))

        raw_pages = data.get("pages", [])
        if raw_pages is None:
            raw_pages = []
        if not isinstance(raw_pages, list):
            raise ValueError("ui_extension.pages 必须是数组")

        return cls(pages=[UIPageInfo.from_dict(item) for item in raw_pages])


@dataclass
class ConfigDefaultsInfo:
    """模块默认配置模板。"""

    module: dict[str, Any] = field(default_factory=dict)
    workflows: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "workflows": self.workflows,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ConfigDefaultsInfo":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("config_defaults 必须是 YAML 映射对象")

        module_defaults = data.get("module", {})
        if module_defaults is None:
            module_defaults = {}
        if not isinstance(module_defaults, dict):
            raise ValueError("config_defaults.module 必须是 YAML 映射对象")

        workflow_defaults = data.get("workflows", {})
        if workflow_defaults is None:
            workflow_defaults = {}
        if not isinstance(workflow_defaults, dict):
            raise ValueError("config_defaults.workflows 必须是 YAML 映射对象")

        normalized_workflows: dict[str, dict[str, Any]] = {}
        for workflow_name, payload in workflow_defaults.items():
            workflow_key = str(workflow_name).strip()
            if not workflow_key:
                raise ValueError("config_defaults.workflows 里的 workflow 名称不能为空")
            if payload is None:
                normalized_workflows[workflow_key] = {}
                continue
            if not isinstance(payload, dict):
                raise ValueError(
                    f"config_defaults.workflows.{workflow_key} 必须是 YAML 映射对象"
                )
            normalized_workflows[workflow_key] = payload

        return cls(module=module_defaults, workflows=normalized_workflows)


@dataclass
class UpgradeSourceInfo:
    """模块升级源配置。"""

    type: str = "github_release"
    repo: str = ""
    allow_prerelease: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "repo": self.repo,
            "allow_prerelease": self.allow_prerelease,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "UpgradeSourceInfo":
        if data is None:
            return cls()
        if not isinstance(data, dict):
            raise ValueError("upgrade_source 必须是 YAML 映射对象")
        return cls(
            type=str(data.get("type", "github_release") or "github_release").strip() or "github_release",
            repo=str(data.get("repo", "") or "").strip(),
            allow_prerelease=bool(data.get("allow_prerelease", False)),
        )


@dataclass
class ModuleManifest:
    """模块清单 (module.yaml)。
    
    规格参考: 第 7 章模块规范
    """
    name: str
    runtime_api: str = ""
    version: str = "1.0.0"
    display_name: str = ""
    description: str = ""
    author: str = ""
    workflows: list[WorkflowInfo] = field(default_factory=list)
    default_workflow: str = ""
    ui_extension: UIExtensionInfo = field(default_factory=UIExtensionInfo)
    config_defaults: ConfigDefaultsInfo = field(default_factory=ConfigDefaultsInfo)
    upgrade_source: UpgradeSourceInfo = field(default_factory=UpgradeSourceInfo)
    
    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "name": self.name,
            "runtime_api": self.runtime_api,
            "version": self.version,
            "display_name": self.display_name,
            "description": self.description,
            "author": self.author,
            "upgrade_source": self.upgrade_source.to_dict(),
            "workflows": [
                {
                    "name": w.name,
                    "display_name": w.display_name,
                    "description": w.description,
                    "entry_class": w.entry_class,
                    "tasks": w.tasks,
                }
                for w in self.workflows
            ],
            "default_workflow": self.default_workflow,
            "ui_extension": self.ui_extension.to_dict(),
            "config_defaults": self.config_defaults.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModuleManifest":
        """从字典反序列化。"""
        workflows = []
        for w in data.get("workflows", []):
            workflows.append(WorkflowInfo(
                name=w.get("name", ""),
                display_name=w.get("display_name", ""),
                description=w.get("description", ""),
                entry_class=w.get("entry_class", ""),
                tasks=w.get("tasks", []),
            ))
        
        ui_extension = UIExtensionInfo.from_dict(data.get("ui_extension"))
        config_defaults = ConfigDefaultsInfo.from_dict(data.get("config_defaults"))
        upgrade_source = UpgradeSourceInfo.from_dict(data.get("upgrade_source"))

        return cls(
            name=data.get("name", ""),
            runtime_api=data.get("runtime_api", ""),
            version=data.get("version", "1.0.0"),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            author=data.get("author", ""),
            workflows=workflows,
            default_workflow=data.get("default_workflow", ""),
            ui_extension=ui_extension,
            config_defaults=config_defaults,
            upgrade_source=upgrade_source,
        )


@dataclass
class ModuleInfo:
    """模块注册信息。
    
    规格 5.1.3.3 Module Registry:
        - 模块元信息
        - 来源（builtin/external）
        - 状态（enabled/disabled/incompatible/invalid）
        - 工作流声明与任务索引
    """
    name: str
    manifest: ModuleManifest
    source: ModuleSource = ModuleSource.EXTERNAL
    status: ModuleStatus = ModuleStatus.ENABLED
    path: Path | None = None
    error: str = ""  # 加载失败时的错误信息
    hint: str = ""  # 修复建议
    
    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "name": self.name,
            "manifest": self.manifest.to_dict(),
            "source": self.source.value,
            "status": self.status.value,
            "path": str(self.path) if self.path else None,
            "error": self.error,
            "hint": self.hint,
        }


class ModuleError(Exception):
    """模块管理错误基类。
    
    规格 5.1.3.2: 错误必须可诊断，包含 stage 和 hint。
    """
    def __init__(self, message: str, stage: str = "", hint: str = ""):
        super().__init__(message)
        self.stage = stage
        self.hint = hint


class ModuleDiscoveryError(ModuleError):
    """模块发现错误。"""
    pass


class ModuleParseError(ModuleError):
    """模块解析错误。"""
    pass


class ModuleValidationError(ModuleError):
    """模块校验错误。"""
    pass


class ModuleInstallError(ModuleError):
    """模块安装错误。"""
    pass

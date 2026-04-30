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

from src.core.mms.data_contract import normalize_manifest_data


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


WORKFLOW_PARAMETER_TYPES = {"string", "text", "integer", "number", "boolean", "enum"}


@dataclass
class WorkflowParameterOptionInfo:
    """工作流运行参数的枚举选项。"""

    label: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "WorkflowParameterOptionInfo":
        if isinstance(data, dict):
            allowed_keys = {"label", "value"}
            unknown_keys = sorted(set(data) - allowed_keys)
            if unknown_keys:
                raise ValueError("workflow parameter option 包含不支持的字段: " + ", ".join(unknown_keys))
            if "value" not in data:
                raise ValueError("workflow parameter option.value 不能为空")
            raw_label = data.get("label")
            if raw_label is None:
                raw_label = data.get("value")
            label = str(raw_label).strip()
            if not label:
                raise ValueError("workflow parameter option.label 不能为空")
            return cls(label=label, value=data.get("value"))

        return cls(label=str(data), value=data)


@dataclass
class WorkflowParameterInfo:
    """工作流运行参数声明。"""

    name: str
    label: str = ""
    type: str = "string"
    description: str = ""
    required: bool = False
    default: Any = None
    options: list[WorkflowParameterOptionInfo] = field(default_factory=list)
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    placeholder: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "label": self.label,
            "type": self.type,
        }
        if self.description:
            payload["description"] = self.description
        if self.required:
            payload["required"] = self.required
        if self.default is not None:
            payload["default"] = self.default
        if self.options:
            payload["options"] = [option.to_dict() for option in self.options]
        if self.min is not None:
            payload["min"] = self.min
        if self.max is not None:
            payload["max"] = self.max
        if self.step is not None:
            payload["step"] = self.step
        if self.placeholder:
            payload["placeholder"] = self.placeholder
        return payload

    @classmethod
    def from_dict(cls, data: Any) -> "WorkflowParameterInfo":
        if not isinstance(data, dict):
            raise ValueError("workflows.parameters 中的每一项都必须是 YAML 映射对象")

        allowed_keys = {
            "name",
            "label",
            "type",
            "description",
            "required",
            "default",
            "options",
            "min",
            "max",
            "step",
            "placeholder",
        }
        unknown_keys = sorted(set(data) - allowed_keys)
        if unknown_keys:
            raise ValueError("workflows.parameters 包含不支持的字段: " + ", ".join(unknown_keys))

        parameter_type = str(data.get("type", "string") or "string").strip().lower()
        if parameter_type not in WORKFLOW_PARAMETER_TYPES:
            raise ValueError(f"workflows.parameters.type 不受支持: {parameter_type}")

        raw_options = data.get("options", [])
        if raw_options is None:
            raw_options = []
        if not isinstance(raw_options, list):
            raise ValueError("workflows.parameters.options 必须是数组")
        options = [WorkflowParameterOptionInfo.from_dict(item) for item in raw_options]
        if parameter_type == "enum" and not options:
            raise ValueError("workflows.parameters.options 不能为空")

        return cls(
            name=str(data.get("name", "") or "").strip(),
            label=str(data.get("label", "") or "").strip(),
            type=parameter_type,
            description=str(data.get("description", "") or "").strip(),
            required=bool(data.get("required", False)),
            default=data.get("default"),
            options=options,
            min=data.get("min"),
            max=data.get("max"),
            step=data.get("step"),
            placeholder=str(data.get("placeholder", "") or "").strip(),
        )


@dataclass
class WorkflowInfo:
    """工作流信息。"""
    name: str
    display_name: str = ""
    description: str = ""
    tasks: list[str] = field(default_factory=list)
    host_scenarios: list[str] = field(default_factory=list)
    parameters: list[WorkflowParameterInfo] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "tasks": self.tasks,
            **({"host_scenarios": self.host_scenarios} if self.host_scenarios else {}),
            **({"parameters": [item.to_dict() for item in self.parameters]} if self.parameters else {}),
        }

    @classmethod
    def from_dict(cls, data: Any) -> "WorkflowInfo":
        if not isinstance(data, dict):
            raise ValueError("workflows 中的每一项都必须是 YAML 映射对象")
        if "entry_class" in data:
            raise ValueError("workflows 包含已移除字段: entry_class")

        raw_tasks = data.get("tasks", [])
        if raw_tasks is None:
            raw_tasks = []
        if not isinstance(raw_tasks, list):
            raise ValueError("workflows.tasks 必须是数组")

        raw_host_scenarios = data.get("host_scenarios", [])
        if raw_host_scenarios is None:
            raw_host_scenarios = []
        if not isinstance(raw_host_scenarios, list):
            raise ValueError("workflows.host_scenarios 必须是数组")

        raw_parameters = data.get("parameters", [])
        if raw_parameters is None:
            raw_parameters = []
        if not isinstance(raw_parameters, list):
            raise ValueError("workflows.parameters 必须是数组")
        parameters = [WorkflowParameterInfo.from_dict(item) for item in raw_parameters]
        parameter_names = [item.name for item in parameters]
        if any(not name for name in parameter_names):
            raise ValueError("workflows.parameters.name 不能为空")
        if len(parameter_names) != len(set(parameter_names)):
            raise ValueError("workflows.parameters.name 不能重复")

        return cls(
            name=str(data.get("name", "") or "").strip(),
            display_name=str(data.get("display_name", "") or "").strip(),
            description=str(data.get("description", "") or "").strip(),
            tasks=[str(item) for item in raw_tasks],
            host_scenarios=[str(item) for item in raw_host_scenarios],
            parameters=parameters,
        )


@dataclass
class ResourcePoolInfo:
    """模块声明的资源池。"""

    name: str
    display_name: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "ResourcePoolInfo":
        if not isinstance(data, dict):
            raise ValueError("resource_pools 中的每一项都必须是 YAML 映射对象")

        allowed_keys = {"name", "display_name", "description"}
        unknown_keys = sorted(set(data) - allowed_keys)
        if unknown_keys:
            raise ValueError("resource_pools 包含不支持的字段: " + ", ".join(unknown_keys))

        return cls(
            name=str(data.get("name", "") or "").strip(),
            display_name=str(data.get("display_name", "") or "").strip(),
            description=str(data.get("description", "") or "").strip(),
        )


@dataclass
class UIPageInfo:
    """宿主页导航视图模型。"""

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
            raise ValueError("页面导航项必须是 YAML 映射对象")

        allowed_keys = {"id", "icon", "label"}
        unknown_keys = sorted(set(data) - allowed_keys)
        if unknown_keys:
            raise ValueError("页面导航项包含不支持的字段: " + ", ".join(unknown_keys))

        return cls(
            id=str(data.get("id", "") or "").strip(),
            icon=str(data.get("icon", "📋") or "📋").strip() or "📋",
            label=str(data.get("label", "") or "").strip(),
        )


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
    config_defaults: ConfigDefaultsInfo = field(default_factory=ConfigDefaultsInfo)
    upgrade_source: UpgradeSourceInfo = field(default_factory=UpgradeSourceInfo)
    resource_pools: list[ResourcePoolInfo] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=lambda: normalize_manifest_data(None))
    
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
            "workflows": [w.to_dict() for w in self.workflows],
            "default_workflow": self.default_workflow,
            "config_defaults": self.config_defaults.to_dict(),
            "resource_pools": [pool.to_dict() for pool in self.resource_pools],
            "data": self.data,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ModuleManifest":
        """从字典反序列化。"""
        if "ui_extension" in data:
            raise ValueError("ui_extension 已移除；页面请使用 @page(...) 装饰器声明")

        workflows = []
        for w in data.get("workflows", []):
            workflows.append(WorkflowInfo.from_dict(w))
        
        config_defaults = ConfigDefaultsInfo.from_dict(data.get("config_defaults"))
        upgrade_source = UpgradeSourceInfo.from_dict(data.get("upgrade_source"))
        raw_resource_pools = data.get("resource_pools", [])
        if raw_resource_pools is None:
            raw_resource_pools = []
        if not isinstance(raw_resource_pools, list):
            raise ValueError("resource_pools 必须是数组")
        resource_pools = [ResourcePoolInfo.from_dict(item) for item in raw_resource_pools]
        module_data = normalize_manifest_data(data.get("data"))

        return cls(
            name=data.get("name", ""),
            runtime_api=data.get("runtime_api", ""),
            version=data.get("version", "1.0.0"),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            author=data.get("author", ""),
            workflows=workflows,
            default_workflow=data.get("default_workflow", ""),
            config_defaults=config_defaults,
            upgrade_source=upgrade_source,
            resource_pools=resource_pools,
            data=module_data,
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

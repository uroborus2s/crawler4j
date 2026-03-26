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
class NavItemInfo:
    """模块导航项信息。
    
    模块可声明自己的侧边栏导航项。
    """
    icon: str = "📦"  # 导航图标 (emoji 或图标名)
    label: str = ""   # 导航标签
    path: str = ""    # 路由路径 (默认为模块名)


@dataclass
class DetailMenuItem:
    """模块详情页自定义菜单项。
    
    模块可在详情页左侧二级导航中添加自定义菜单。
    固定菜单（基本信息、任务链）由 Core 提供，无需声明。
    """
    id: str           # 菜单唯一 ID
    icon: str = "📋"  # 菜单图标
    label: str = ""   # 显示标签
    entry: str = ""   # 入口类名 (模块内的 Widget 类，如 "ui:AccountConfigPage")


@dataclass
class UIExtensionInfo:
    """UI 扩展信息。
    
    规格 5.1.3.3:
        - declarative: 声明式 UI (YAML/JSON)
        - micro_app: 代码型 UI
        - none: 无 UI 扩展
    """
    type: str = "none"  # declarative | micro_app | none
    entry: str = ""  # 入口文件或配置
    trusted: bool = False  # 是否受信
    available: bool = True  # 是否可用
    nav_item: NavItemInfo | None = None  # 模块导航项 (可选，已弃用)
    detail_menu: list[DetailMenuItem] = field(default_factory=list)  # 详情页自定义菜单


@dataclass
class ModuleManifest:
    """模块清单 (module.yaml)。
    
    规格参考: 第 7 章模块规范
    """
    name: str
    version: str = "1.0.0"
    display_name: str = ""
    description: str = ""
    author: str = ""
    sdk_version_range: str = ">=1.0.0"
    workflows: list[WorkflowInfo] = field(default_factory=list)
    ui_extension: UIExtensionInfo = field(default_factory=UIExtensionInfo)
    config_schema: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "name": self.name,
            "version": self.version,
            "display_name": self.display_name,
            "description": self.description,
            "author": self.author,
            "sdk_version_range": self.sdk_version_range,
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
            "ui_extension": {
                "type": self.ui_extension.type,
                "entry": self.ui_extension.entry,
                "trusted": self.ui_extension.trusted,
                "available": self.ui_extension.available,
                "nav_item": (
                    {
                        "icon": self.ui_extension.nav_item.icon,
                        "label": self.ui_extension.nav_item.label,
                        "path": self.ui_extension.nav_item.path,
                    }
                    if self.ui_extension.nav_item
                    else None
                ),
                "detail_menu": [
                    {
                        "id": item.id,
                        "icon": item.icon,
                        "label": item.label,
                        "entry": item.entry,
                    }
                    for item in self.ui_extension.detail_menu
                ],
            },
            "config_schema": self.config_schema,
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
        
        ui_data = data.get("ui_extension", {})
        nav_data = ui_data.get("nav_item")
        nav_item = None
        if nav_data:
            nav_item = NavItemInfo(
                icon=nav_data.get("icon", "📦"),
                label=nav_data.get("label", ""),
                path=nav_data.get("path", ""),
            )
        
        # 解析详情页自定义菜单
        detail_menu = []
        for item in ui_data.get("detail_menu", []):
            detail_menu.append(DetailMenuItem(
                id=item.get("id", ""),
                icon=item.get("icon", "📋"),
                label=item.get("label", ""),
                entry=item.get("entry", ""),
            ))
        
        ui_extension = UIExtensionInfo(
            type=ui_data.get("type", "none"),
            entry=ui_data.get("entry", ""),
            trusted=bool(ui_data.get("trusted", False)),
            available=bool(ui_data.get("available", True)),
            nav_item=nav_item,
            detail_menu=detail_menu,
        )
        
        return cls(
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            author=data.get("author", ""),
            sdk_version_range=data.get("sdk_version_range", ">=1.0.0"),
            workflows=workflows,
            ui_extension=ui_extension,
            config_schema=data.get("config_schema", {}),
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

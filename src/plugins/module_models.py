"""任务模块数据模型

定义模块、任务链和子任务的数据结构。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Type

if TYPE_CHECKING:
    from crawler4j_sdk import TaskFlow, TaskScript


@dataclass
class WorkflowInfo:
    """任务链信息"""
    name: str
    display_name: str = ""
    description: str = ""
    config: dict = field(default_factory=dict)


@dataclass
class ModuleInfo:
    """模块元信息
    
    从 module.yaml 解析得到。
    """
    name: str
    display_name: str = ""
    description: str = ""
    version: str = "1.0.0"
    author: str = ""
    path: Path = field(default_factory=Path)
    
    # 模块默认配置
    config: dict = field(default_factory=dict)
    
    # 任务链信息列表
    workflows: list[WorkflowInfo] = field(default_factory=list)
    
    # 子任务名称列表
    tasks: list[str] = field(default_factory=list)


@dataclass
class Module:
    """完整的已加载模块
    
    包含元信息和实际加载的类。
    """
    info: ModuleInfo
    
    # 已加载的任务链类
    workflows: dict[str, Type["TaskFlow"]] = field(default_factory=dict)
    
    # 已加载的子任务类
    tasks: dict[str, Type["TaskScript"]] = field(default_factory=dict)
    
    def get_workflow(self, name: str) -> Type["TaskFlow"] | None:
        """获取任务链类"""
        return self.workflows.get(name)
    
    def get_task(self, name: str) -> Type["TaskScript"] | None:
        """获取子任务类"""
        return self.tasks.get(name)
    
    def get_workflow_config(self, name: str) -> dict:
        """获取任务链配置"""
        for wf in self.info.workflows:
            if wf.name == name:
                # 合并模块配置和任务链配置
                merged = dict(self.info.config)
                merged.update(wf.config)
                return merged
        return dict(self.info.config)

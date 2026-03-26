"""准入控制器。

最新方案中并发由 Job 控制，策略侧不再维护并发配额。
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from src.core.tsm.models import TaskStrategy


class AdmissionResult(StrEnum):
    """准入结果。"""
    ADMITTED = "admitted"       # 允许执行
    QUEUED = "queued"          # 需要排队
    REJECTED = "rejected"       # 拒绝


@dataclass
class AdmissionDecision:
    """准入决策。
    
    Attributes:
        result: 准入结果
        reason: 原因说明
        wait_hint: 等待提示
        priority: 队列优先级
    """
    result: AdmissionResult
    reason: str = ""
    wait_hint: str = ""
    priority: int = 100


@dataclass
class TaskSubmission:
    """任务提交请求。
    
    Attributes:
        task_id: 任务ID
        module_name: 模块名
        workflow_name: 工作流名
        tags: 任务标签（用于配额桶匹配）
        priority: 优先级覆盖
    """
    task_id: str
    module_name: str
    workflow_name: str = ""
    tags: dict[str, str] | None = None
    priority: int | None = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


class AdmissionController:
    """准入控制器 (V2)。
    
    策略层仅负责资源与执行配置，准入默认放行。
    
    Usage:
        controller = AdmissionController()
        decision = controller.check(submission, strategy, current_state)
    """
    
    def __init__(self):
        """初始化准入控制器。"""
        pass
    
    def check(
        self,
        submission: TaskSubmission,
        strategy: TaskStrategy,
        running_tasks: list[dict[str, Any]],
    ) -> AdmissionDecision:
        """检查任务是否可以准入执行。"""
        _ = (submission, strategy, running_tasks)
        return AdmissionDecision(
            result=AdmissionResult.ADMITTED,
            reason="ok",
            priority=100,
        )


# 全局单例
_admission_controller: AdmissionController | None = None


def get_admission_controller() -> AdmissionController:
    """获取全局 AdmissionController 实例。"""
    global _admission_controller
    if _admission_controller is None:
        _admission_controller = AdmissionController()
    return _admission_controller

"""准入控制器。

规格参考: docs/srs/05-framework-core/05-3-task-strategy-management.md (5.3.3)

AdmissionController 负责：
    - 并发配额检查
    - 决定任务是否可以立即执行
    - 不满足条件时返回排队原因
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
    
    基于 TaskStrategy 的 ScalingPolicy 检查并发配额。
    
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
        """检查任务是否可以准入执行。
        
        检查逻辑：
            1. 检查最大并发配额（来自 strategy.scaling.max_concurrency）
            2. 检查同模块并发（从运行任务中统计）
        
        Args:
            submission: 任务提交请求
            strategy: V2 策略配置
            running_tasks: 当前运行中的任务列表
        
        Returns:
            准入决策
        """
        max_concurrency = strategy.scaling.max_concurrency
        
        # 1. 检查全局并发
        if len(running_tasks) >= max_concurrency:
            return AdmissionDecision(
                result=AdmissionResult.QUEUED,
                reason="global_quota_exceeded",
                wait_hint=f"并发已满 ({len(running_tasks)}/{max_concurrency})",
                priority=submission.priority or 100,
            )
        
        # 2. 检查同模块并发（同一模块的任务数不应超过 max_concurrency）
        if submission.module_name:
            module_running = sum(
                1 for t in running_tasks
                if t.get("module") == submission.module_name
            )
            if module_running >= max_concurrency:
                return AdmissionDecision(
                    result=AdmissionResult.QUEUED,
                    reason="module_quota_exceeded",
                    wait_hint=f"模块并发已满: {submission.module_name} ({module_running}/{max_concurrency})",
                    priority=submission.priority or 100,
                )
        
        # 3. 通过准入
        return AdmissionDecision(
            result=AdmissionResult.ADMITTED,
            reason="ok",
            priority=submission.priority or 100,
        )


# 全局单例
_admission_controller: AdmissionController | None = None


def get_admission_controller() -> AdmissionController:
    """获取全局 AdmissionController 实例。"""
    global _admission_controller
    if _admission_controller is None:
        _admission_controller = AdmissionController()
    return _admission_controller

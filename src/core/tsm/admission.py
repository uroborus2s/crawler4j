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

from src.core.tsm.models import StrategyProfile


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
        wait_hint: 等待提示（如 "Waiting for quota: module:ctrip"）
        priority: 队列优先级（用于排队时确定顺序）
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
    tags: dict[str, str] = None
    priority: int | None = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = {}


class AdmissionController:
    """准入控制器。
    
    规格 5.3.3: 通过 AdmissionController 解释并发配额策略。
    
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
        strategy: StrategyProfile,
        running_tasks: list[dict[str, Any]],
    ) -> AdmissionDecision:
        """检查任务是否可以准入执行。
        
        规格 5.3.3 准入检查：
            1. 检查全局并发配额
            2. 检查分组配额（模块、优先级等）
        
        Args:
            submission: 任务提交请求
            strategy: 策略配置
            running_tasks: 当前运行中的任务列表
        
        Returns:
            准入决策
        """
        concurrency = strategy.concurrency
        priority = submission.priority or strategy.scheduling.default_priority
        
        # 1. 检查全局并发
        if len(running_tasks) >= concurrency.global_max:
            return AdmissionDecision(
                result=AdmissionResult.QUEUED,
                reason="global_quota_exceeded",
                wait_hint=f"全局并发已满 ({len(running_tasks)}/{concurrency.global_max})",
                priority=priority,
            )
        
        # 2. 检查分组配额（只检查当前任务所匹配的桶）
        for bucket_key, bucket_limit in concurrency.group_buckets.items():
            # 先判断当前提交的任务是否匹配该配额桶
            if not self._submission_matches_bucket_key(submission, bucket_key):
                continue  # 当前任务不匹配该桶，跳过检查
            
            matching_count = self._count_matching_tasks(bucket_key, running_tasks, submission)
            
            if matching_count >= bucket_limit:
                return AdmissionDecision(
                    result=AdmissionResult.QUEUED,
                    reason="bucket_quota_exceeded",
                    wait_hint=f"配额已满: {bucket_key} ({matching_count}/{bucket_limit})",
                    priority=priority,
                )
        
        # 3. 通过准入
        return AdmissionDecision(
            result=AdmissionResult.ADMITTED,
            reason="ok",
            priority=priority,
        )
    
    def _count_matching_tasks(
        self,
        bucket_key: str,
        running_tasks: list[dict[str, Any]],
        submission: TaskSubmission,
    ) -> int:
        """统计匹配配额桶的任务数量。
        
        配额桶格式: "key:value"
            - "module:ctrip" -> 匹配模块名
            - "priority:high" -> 匹配优先级标签
            - "tag:vip" -> 匹配任务标签
        """
        if ":" not in bucket_key:
            return 0
        
        key_type, key_value = bucket_key.split(":", 1)
        count = 0
        
        for task in running_tasks:
            if self._task_matches_bucket(task, key_type, key_value):
                count += 1
        
        return count
    
    def _task_matches_bucket(
        self,
        task: dict[str, Any],
        key_type: str,
        key_value: str,
    ) -> bool:
        """检查运行中的任务是否匹配配额桶。"""
        if key_type == "module":
            return task.get("module") == key_value
        elif key_type == "priority":
            # 假设 priority:high 表示优先级 >= 200
            if key_value == "high":
                return task.get("priority", 100) >= 200
            elif key_value == "low":
                return task.get("priority", 100) < 100
        elif key_type == "tag":
            tags = task.get("tags", {})
            return key_value in tags or tags.get(key_value) is not None
        
        return False
    
    def _submission_matches_bucket_key(
        self,
        submission: TaskSubmission,
        bucket_key: str,
    ) -> bool:
        """检查提交的任务是否匹配配额桶。
        
        例如: "module:ctrip" 只匹配 module_name="ctrip" 的任务
        """
        if ":" not in bucket_key:
            return False
        
        key_type, key_value = bucket_key.split(":", 1)
        
        if key_type == "module":
            return submission.module_name == key_value
        elif key_type == "priority":
            priority = submission.priority or 100
            if key_value == "high":
                return priority >= 200
            elif key_value == "low":
                return priority < 100
        elif key_type == "tag":
            return key_value in submission.tags
        
        return False


# 全局单例
_admission_controller: AdmissionController | None = None


def get_admission_controller() -> AdmissionController:
    """获取全局 AdmissionController 实例。"""
    global _admission_controller
    if _admission_controller is None:
        _admission_controller = AdmissionController()
    return _admission_controller

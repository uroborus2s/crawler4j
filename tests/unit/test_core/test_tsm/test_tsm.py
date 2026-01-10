"""TSM 策略模型和准入控制单元测试。"""

import pytest

from src.core.tsm.admission import (
    AdmissionController,
    AdmissionResult,
    TaskSubmission,
)
from src.core.tsm.models import (
    DEFAULT_STRATEGY,
    ConcurrencyConfig,
    ProvisioningConfig,
    ProvisioningMode,
    StrategyProfile,
)


class TestStrategyProfile:
    """测试 StrategyProfile。"""
    
    def test_default_values(self):
        """测试默认值。"""
        strategy = StrategyProfile()
        
        assert strategy.concurrency.global_max == 10
        assert strategy.provisioning.mode == ProvisioningMode.HYBRID
        assert strategy.reliability.max_retries == 3
    
    def test_to_dict(self):
        """测试序列化。"""
        strategy = StrategyProfile()
        data = strategy.to_dict()
        
        assert data["concurrency"]["global_max"] == 10
        assert data["provisioning"]["mode"] == "hybrid"
    
    def test_from_dict(self):
        """测试反序列化。"""
        data = {
            "metadata": {"name": "test"},
            "concurrency": {"global_max": 5},
            "provisioning": {"mode": "dynamic"},
        }
        
        strategy = StrategyProfile.from_dict(data)
        
        assert strategy.metadata.name == "test"
        assert strategy.concurrency.global_max == 5
        assert strategy.provisioning.mode == ProvisioningMode.DYNAMIC
    
    def test_merge(self):
        """测试策略合并。"""
        base = StrategyProfile(
            concurrency=ConcurrencyConfig(global_max=10, group_buckets={"module:a": 2})
        )
        override = StrategyProfile(
            concurrency=ConcurrencyConfig(global_max=5, group_buckets={"module:b": 3})
        )
        
        result = base.merge(override)
        
        assert result.concurrency.global_max == 5
        assert result.concurrency.group_buckets == {"module:a": 2, "module:b": 3}


class TestAdmissionController:
    """测试 AdmissionController。"""
    
    def test_admit_when_empty(self):
        """测试无任务时准入。"""
        controller = AdmissionController()
        submission = TaskSubmission(
            task_id="task-1",
            module_name="ctrip",
        )
        strategy = DEFAULT_STRATEGY
        
        decision = controller.check(submission, strategy, running_tasks=[])
        
        assert decision.result == AdmissionResult.ADMITTED
    
    def test_queue_when_global_full(self):
        """测试全局并发满时排队。"""
        controller = AdmissionController()
        submission = TaskSubmission(
            task_id="task-11",
            module_name="test",
        )
        strategy = StrategyProfile(
            concurrency=ConcurrencyConfig(global_max=2)
        )
        running = [
            {"task_id": "task-1", "module": "a"},
            {"task_id": "task-2", "module": "b"},
        ]
        
        decision = controller.check(submission, strategy, running_tasks=running)
        
        assert decision.result == AdmissionResult.QUEUED
        assert "全局并发已满" in decision.wait_hint
    
    def test_queue_when_module_bucket_full(self):
        """测试模块配额满时排队。"""
        controller = AdmissionController()
        submission = TaskSubmission(
            task_id="task-3",
            module_name="ctrip",
        )
        strategy = StrategyProfile(
            concurrency=ConcurrencyConfig(
                global_max=10,
                group_buckets={"module:ctrip": 2}
            )
        )
        running = [
            {"task_id": "task-1", "module": "ctrip"},
            {"task_id": "task-2", "module": "ctrip"},
        ]
        
        decision = controller.check(submission, strategy, running_tasks=running)
        
        assert decision.result == AdmissionResult.QUEUED
        assert "module:ctrip" in decision.wait_hint
    
    def test_admit_when_different_module(self):
        """测试不同模块时准入。"""
        controller = AdmissionController()
        submission = TaskSubmission(
            task_id="task-3",
            module_name="labor",  # 不同模块
        )
        strategy = StrategyProfile(
            concurrency=ConcurrencyConfig(
                global_max=10,
                group_buckets={"module:ctrip": 2}
            )
        )
        running = [
            {"task_id": "task-1", "module": "ctrip"},
            {"task_id": "task-2", "module": "ctrip"},
        ]
        
        decision = controller.check(submission, strategy, running_tasks=running)
        
        assert decision.result == AdmissionResult.ADMITTED

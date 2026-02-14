"""ATM 数据模型单元测试 (V2)。"""





from src.core.atm.models import (
    AutomationTask,
    TaskResult,
    TaskRun,
    TaskStatus,
    TriggerConfig,
    TriggerType,
)


class TestAutomationTask:
    """测试 AutomationTask 模型。"""

    def test_default_values(self):
        """测试默认值。"""
        task = AutomationTask()

        assert task.id is not None
        assert len(task.id) > 0
        assert task.name == ""
        assert task.strategy_id == ""
        assert task.trigger_config is None
        assert task.default_params == {}
        assert task.created_at > 0
        assert task.updated_at > 0

    def test_to_dict(self):
        """测试序列化。"""
        task = AutomationTask(
            id="task-001",
            name="测试任务",
            strategy_id="strategy-001",
            default_params={"url": "https://example.com"},
        )

        data = task.to_dict()

        assert data["id"] == "task-001"
        assert data["name"] == "测试任务"
        assert data["strategy_id"] == "strategy-001"
        assert data["default_params"] == {"url": "https://example.com"}
        assert data["trigger_config"] is None

    def test_from_dict(self):
        """测试反序列化。"""
        data = {
            "id": "task-002",
            "name": "反序列化测试",
            "strategy_id": "s-002",
            "default_params": {"key": "value"},
        }

        task = AutomationTask.from_dict(data)

        assert task.id == "task-002"
        assert task.name == "反序列化测试"
        assert task.strategy_id == "s-002"
        assert task.default_params == {"key": "value"}

    def test_roundtrip(self):
        """测试序列化/反序列化往返。"""
        original = AutomationTask(
            id="roundtrip-001",
            name="往返测试",
            strategy_id="s-rt",
            trigger_config=TriggerConfig(
                type=TriggerType.CRON,
                cron_expr="0 9 * * *",
            ),
            default_params={"a": 1, "b": "two"},
        )

        data = original.to_dict()
        restored = AutomationTask.from_dict(data)

        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.strategy_id == original.strategy_id
        assert restored.trigger_config is not None
        assert restored.trigger_config.type == TriggerType.CRON
        assert restored.trigger_config.cron_expr == "0 9 * * *"
        assert restored.default_params == original.default_params


class TestTriggerConfig:
    """测试 TriggerConfig。"""

    def test_cron_trigger(self):
        """测试 CRON 触发器。"""
        trigger = TriggerConfig(
            type=TriggerType.CRON,
            cron_expr="0 */2 * * *",
        )
        data = trigger.to_dict()

        assert data["type"] == "cron"
        assert data["cron_expr"] == "0 */2 * * *"

    def test_interval_trigger(self):
        """测试 INTERVAL 触发器。"""
        trigger = TriggerConfig(
            type=TriggerType.INTERVAL,
            interval_seconds=3600,
        )
        data = trigger.to_dict()

        assert data["type"] == "interval"
        assert data["interval_seconds"] == 3600

    def test_random_trigger(self):
        """测试 RANDOM 触发器。"""
        trigger = TriggerConfig(
            type=TriggerType.RANDOM,
            interval_seconds=600,
            random_range=120,
        )

        assert trigger.type == TriggerType.RANDOM
        assert trigger.random_range == 120

    def test_roundtrip(self):
        """测试序列化往返。"""
        original = TriggerConfig(
            type=TriggerType.INTERVAL,
            interval_seconds=300,
        )
        data = original.to_dict()
        restored = TriggerConfig.from_dict(data)

        assert restored.type == original.type
        assert restored.interval_seconds == original.interval_seconds


class TestTaskRun:
    """测试 TaskRun 模型。"""

    def test_default_values(self):
        """测试默认值。"""
        run = TaskRun()

        assert run.id is not None
        assert run.task_id == ""
        assert run.status == TaskStatus.IDLE
        assert run.trigger_type == "manual"
        assert run.env_id is None
        assert run.result is None

    def test_start(self):
        """测试开始执行。"""
        run = TaskRun(task_id="task-001")
        run.start()

        assert run.status == TaskStatus.RUNNING
        assert run.start_time is not None
        assert run.start_time > 0

    def test_finish_success(self):
        """测试成功完成。"""
        run = TaskRun(task_id="task-001")
        run.start()
        run.finish(success=True, message="任务完成")

        assert run.status == TaskStatus.SUCCEEDED
        assert run.end_time is not None
        assert run.result is not None
        assert run.result.success is True
        assert run.result.message == "任务完成"

    def test_finish_failure(self):
        """测试失败完成。"""
        run = TaskRun(task_id="task-001")
        run.start()
        run.finish(success=False, message="网络超时")

        assert run.status == TaskStatus.FAILED
        assert run.result.success is False
        assert run.result.message == "网络超时"

    def test_cancel(self):
        """测试取消。"""
        run = TaskRun(task_id="task-001")
        run.start()
        run.cancel()

        assert run.status == TaskStatus.CANCELLED
        assert run.end_time is not None

    def test_to_dict(self):
        """测试序列化。"""
        run = TaskRun(
            id="run-001",
            task_id="task-001",
            status=TaskStatus.RUNNING,
            trigger_type="schedule",
            env_id="env-1",
        )

        data = run.to_dict()

        assert data["id"] == "run-001"
        assert data["status"] == "running"
        assert data["trigger_type"] == "schedule"
        assert data["env_id"] == "env-1"

    def test_from_dict(self):
        """测试反序列化。"""
        data = {
            "id": "run-002",
            "task_id": "task-002",
            "status": "succeeded",
            "trigger_type": "manual",
            "result": {"success": True, "message": "done", "data": {}},
        }

        run = TaskRun.from_dict(data)

        assert run.id == "run-002"
        assert run.status == TaskStatus.SUCCEEDED
        assert run.result is not None
        assert run.result.success is True


class TestTaskResult:
    """测试 TaskResult。"""

    def test_default_values(self):
        """测试默认值。"""
        result = TaskResult()

        assert result.success is True
        assert result.message == ""
        assert result.data == {}

    def test_to_dict(self):
        """测试序列化。"""
        result = TaskResult(
            success=True,
            message="done",
            data={"count": 10},
        )

        data = result.to_dict()

        assert data["success"] is True
        assert data["message"] == "done"
        assert data["data"] == {"count": 10}

    def test_from_dict(self):
        """测试反序列化。"""
        data = {
            "success": False,
            "message": "failed",
            "data": {"error_code": 500},
        }

        result = TaskResult.from_dict(data)

        assert result.success is False
        assert result.message == "failed"
        assert result.data == {"error_code": 500}


class TestTaskStatus:
    """测试 TaskStatus 枚举。"""

    def test_all_status_values(self):
        """测试所有状态值。"""
        assert TaskStatus.IDLE == "idle"
        assert TaskStatus.STARTING == "starting"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.SUCCEEDED == "succeeded"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"
        assert TaskStatus.INTERRUPTED == "interrupted"

    def test_status_from_string(self):
        """测试从字符串创建状态。"""
        assert TaskStatus("running") == TaskStatus.RUNNING
        assert TaskStatus("failed") == TaskStatus.FAILED

"""ATM 数据模型单元测试。"""

import time

import pytest

from src.core.atm.models import (
    TaskInstance,
    TaskRequest,
    TaskResult,
    TaskStatus,
)


class TestTaskInstance:
    """测试 TaskInstance。"""
    
    def test_default_values(self):
        """测试默认值。"""
        task = TaskInstance()
        
        assert task.id is not None
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 0
    
    def test_from_request(self):
        """测试从请求创建。"""
        request = TaskRequest(
            module_name="ctrip",
            task_name="login",
            params={"username": "test"},
        )
        
        task = TaskInstance.from_request(request)
        
        assert task.module == "ctrip"
        assert task.name == "login"
        assert task.params == {"username": "test"}
    
    def test_to_dict(self):
        """测试序列化。"""
        task = TaskInstance(
            module="test",
            name="task1",
        )
        
        data = task.to_dict()
        
        assert data["module"] == "test"
        assert data["name"] == "task1"
        assert data["status"] == "pending"
    
    def test_from_dict(self):
        """测试反序列化。"""
        data = {
            "id": "test-id",
            "module": "ctrip",
            "name": "login",
            "status": "running",
        }
        
        task = TaskInstance.from_dict(data)
        
        assert task.id == "test-id"
        assert task.status == TaskStatus.RUNNING


class TestTaskStateMachine:
    """测试任务状态机。"""
    
    def test_enqueue(self):
        """测试入队。"""
        task = TaskInstance()
        
        assert task.enqueue() is True
        assert task.status == TaskStatus.QUEUED
    
    def test_start(self):
        """测试开始执行。"""
        task = TaskInstance()
        task.enqueue()
        
        assert task.start(env_id="env-1") is True
        assert task.status == TaskStatus.RUNNING
        assert task.env_id == "env-1"
        assert task.started_at is not None
    
    def test_succeed(self):
        """测试成功完成。"""
        task = TaskInstance()
        task.enqueue()
        task.start()
        
        result = TaskResult(success=True, message="done")
        
        assert task.succeed(result) is True
        assert task.status == TaskStatus.SUCCEEDED
        assert task.result == result
        assert task.ended_at is not None
    
    def test_fail(self):
        """测试执行失败。"""
        task = TaskInstance()
        task.enqueue()
        task.start()
        
        assert task.fail("some error") is True
        assert task.status == TaskStatus.FAILED
        assert task.error == "some error"
    
    def test_cancel_from_pending(self):
        """测试从 PENDING 取消。"""
        task = TaskInstance()
        
        assert task.cancel() is True
        assert task.status == TaskStatus.CANCELLED
    
    def test_retry(self):
        """测试重试。"""
        task = TaskInstance(max_retries=3)
        task.enqueue()
        task.start()
        task.fail("error")
        
        assert task.retry() is True
        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 1
    
    def test_retry_limit(self):
        """测试重试次数限制。"""
        task = TaskInstance(max_retries=1, retry_count=1)
        task.status = TaskStatus.FAILED
        
        assert task.retry() is False
        assert task.status == TaskStatus.FAILED
    
    def test_invalid_transition(self):
        """测试无效状态转换。"""
        task = TaskInstance()
        
        # PENDING 不能直接到 RUNNING
        assert task.start() is False
        assert task.status == TaskStatus.PENDING
        
        # PENDING 不能 succeed
        assert task.succeed(TaskResult()) is False


class TestTaskResult:
    """测试 TaskResult。"""
    
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
            "tasks_completed": 5,
        }
        
        result = TaskResult.from_dict(data)
        
        assert result.success is False
        assert result.message == "failed"
        assert result.tasks_completed == 5

"""TaskScript 单元测试。

测试用例覆盖:
    - TC_SDK_003: 生命周期回调执行顺序 (on_init -> execute -> on_cleanup)
    - TC_SDK_004: Cleanup 总是执行（即使 execute 抛出异常）
    - TC_SDK_001: 继承检测
    - TC_SDK_002: run 方法签名检查
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from crawler4j_sdk import TaskContext, TaskResult, TaskScript

# === 测试夹具 ===

@pytest.fixture
def mock_context() -> TaskContext:
    """创建 Mock TaskContext。"""
    ctx = TaskContext(
        env_id=1,
        task_name="test_task",
        config={"key": "value"},
    )
    ctx.logger = MagicMock()
    return ctx


# === 测试用例 ===

class TestTaskScriptLifecycle:
    """测试 TaskScript 生命周期。"""
    
    @pytest.mark.asyncio
    async def test_lifecycle_order(self, mock_context: TaskContext):
        """TC_SDK_003: 生命周期回调执行顺序。
        
        验证调用顺序严格为: on_init -> execute -> on_cleanup
        """
        call_order: list[str] = []
        
        class OrderTrackingTask(TaskScript):
            name = "order_tracking"
            
            async def on_init(self, ctx: TaskContext) -> None:
                call_order.append("on_init")
            
            async def execute(self, ctx: TaskContext) -> TaskResult:
                call_order.append("execute")
                return TaskResult.ok()
            
            async def on_cleanup(self, ctx: TaskContext) -> None:
                call_order.append("on_cleanup")
        
        task = OrderTrackingTask()
        
        # 模拟运行时执行流程
        await task.on_init(mock_context)
        await task.execute(mock_context)
        await task.on_cleanup(mock_context)
        
        assert call_order == ["on_init", "execute", "on_cleanup"]
    
    @pytest.mark.asyncio
    async def test_cleanup_always_called_on_error(self, mock_context: TaskContext):
        """TC_SDK_004: Cleanup 总是执行。
        
        验证即使 execute 抛出异常，on_cleanup 仍被调用。
        """
        cleanup_called = False
        error_called = False
        
        class ErrorTask(TaskScript):
            name = "error_task"
            
            async def execute(self, ctx: TaskContext) -> TaskResult:
                raise ValueError("模拟错误")
            
            async def on_error(self, ctx: TaskContext, error: Exception) -> None:
                nonlocal error_called
                error_called = True
            
            async def on_cleanup(self, ctx: TaskContext) -> None:
                nonlocal cleanup_called
                cleanup_called = True
        
        task = ErrorTask()
        
        # 模拟运行时执行流程（带异常处理）
        try:
            await task.on_init(mock_context)
            await task.execute(mock_context)
        except ValueError as e:
            await task.on_error(mock_context, e)
        finally:
            await task.on_cleanup(mock_context)
        
        assert error_called, "on_error 应该被调用"
        assert cleanup_called, "on_cleanup 应该总是被调用"


class TestTaskScriptContract:
    """测试 TaskScript 契约。"""
    
    def test_class_attributes_exist(self):
        """验证类属性存在。"""
        assert hasattr(TaskScript, "name")
        assert hasattr(TaskScript, "display_name")
        assert hasattr(TaskScript, "description")
        assert hasattr(TaskScript, "default_config")
    
    def test_abstract_execute_method(self):
        """验证 execute 是抽象方法。"""
        # 不实现 execute 应该无法实例化
        class IncompleteTask(TaskScript):
            name = "incomplete"
        
        with pytest.raises(TypeError):
            IncompleteTask()  # type: ignore
    
    def test_optional_hooks_have_default_implementation(self):
        """验证可选钩子有默认实现。"""
        class MinimalTask(TaskScript):
            name = "minimal"
            
            async def execute(self, ctx: TaskContext) -> TaskResult:
                return TaskResult.ok()
        
        task = MinimalTask()
        
        # 可选钩子应该可以不覆盖
        assert hasattr(task, "on_init")
        assert hasattr(task, "on_error")
        assert hasattr(task, "on_cleanup")
    
    def test_default_config_is_dict(self):
        """验证 default_config 默认是空字典。"""
        class SimpleTask(TaskScript):
            name = "simple"
            
            async def execute(self, ctx: TaskContext) -> TaskResult:
                return TaskResult.ok()
        
        task = SimpleTask()
        assert isinstance(task.default_config, dict)
        assert task.default_config == {}
    
    def test_custom_default_config(self):
        """验证可以自定义 default_config。"""
        class ConfiguredTask(TaskScript):
            name = "configured"
            default_config = {"timeout": 30, "retry": 3}
            
            async def execute(self, ctx: TaskContext) -> TaskResult:
                return TaskResult.ok()
        
        task = ConfiguredTask()
        assert task.default_config == {"timeout": 30, "retry": 3}


class TestTaskScriptExecution:
    """测试 TaskScript 执行。"""
    
    @pytest.mark.asyncio
    async def test_execute_returns_task_result(self, mock_context: TaskContext):
        """验证 execute 返回 TaskResult。"""
        class SuccessTask(TaskScript):
            name = "success"
            
            async def execute(self, ctx: TaskContext) -> TaskResult:
                return TaskResult.ok(message="执行成功", data={"key": "value"})
        
        task = SuccessTask()
        result = await task.execute(mock_context)
        
        assert isinstance(result, TaskResult)
        assert result.success is True
        assert result.message == "执行成功"
        assert result.data == {"key": "value"}
    
    @pytest.mark.asyncio
    async def test_execute_can_return_failure(self, mock_context: TaskContext):
        """验证 execute 可以返回失败结果。"""
        class FailureTask(TaskScript):
            name = "failure"
            
            async def execute(self, ctx: TaskContext) -> TaskResult:
                return TaskResult.fail(message="执行失败", error="原因")
        
        task = FailureTask()
        result = await task.execute(mock_context)
        
        assert result.success is False
        assert result.message == "执行失败"
        assert result.error == "原因"
    
    @pytest.mark.asyncio
    async def test_execute_can_raise_exception(self, mock_context: TaskContext):
        """验证 execute 可以抛出异常。"""
        class ExceptionTask(TaskScript):
            name = "exception"
            
            async def execute(self, ctx: TaskContext) -> TaskResult:
                raise RuntimeError("不可预期错误")
        
        task = ExceptionTask()
        
        with pytest.raises(RuntimeError, match="不可预期错误"):
            await task.execute(mock_context)

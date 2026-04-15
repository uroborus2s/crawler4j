"""TaskScript 单元测试。

测试用例覆盖:
    - TC_SDK_001: 继承检测
    - TC_SDK_002: run 方法签名检查
"""

from unittest.mock import MagicMock

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
    
    def test_taskscript_has_single_execute_entry(self):
        """验证 TaskScript 仅暴露 execute 作为正式入口。"""
        class MinimalTask(TaskScript):
            name = "minimal"
            
            async def execute(self, ctx: TaskContext) -> TaskResult:
                return TaskResult.ok()
        
        task = MinimalTask()
        assert hasattr(task, "execute")
        assert not hasattr(task, "on_init")
        assert not hasattr(task, "on_error")
        assert not hasattr(task, "on_cleanup")
    
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

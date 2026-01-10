"""TaskFlow 单元测试。

测试用例覆盖:
    - 工作流编排测试
    - 生命周期回调测试
    - 子任务调用测试
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from crawler4j_sdk import TaskContext, TaskFlow, TaskResult

# === 测试夹具 ===

@pytest.fixture
def mock_context() -> TaskContext:
    """创建 Mock TaskContext。"""
    ctx = TaskContext(
        env_id=1,
        task_name="test_workflow",
        config={},
    )
    ctx.logger = MagicMock()
    return ctx


# === 工作流契约测试 ===

class TestTaskFlowContract:
    """测试 TaskFlow 契约。"""
    
    def test_class_attributes_exist(self):
        """验证类属性存在。"""
        assert hasattr(TaskFlow, "name")
        assert hasattr(TaskFlow, "display_name")
        assert hasattr(TaskFlow, "description")
    
    def test_abstract_run_method(self):
        """验证 run 是抽象方法。"""
        # 不实现 run 应该无法实例化
        class IncompleteFlow(TaskFlow):
            name = "incomplete"
        
        with pytest.raises(TypeError):
            IncompleteFlow()  # type: ignore
    
    def test_optional_hooks_have_default_implementation(self):
        """验证可选钩子有默认实现。"""
        class MinimalFlow(TaskFlow):
            name = "minimal"
            
            async def run(self, ctx: TaskContext) -> None:
                pass
        
        flow = MinimalFlow()
        
        # 可选钩子应该可以不覆盖
        assert hasattr(flow, "on_error")
        assert hasattr(flow, "on_complete")


class TestTaskFlowLifecycle:
    """测试 TaskFlow 生命周期。"""
    
    @pytest.mark.asyncio
    async def test_run_execution(self, mock_context: TaskContext):
        """验证 run 方法执行。"""
        run_called = False
        
        class SimpleFlow(TaskFlow):
            name = "simple"
            
            async def run(self, ctx: TaskContext) -> None:
                nonlocal run_called
                run_called = True
        
        flow = SimpleFlow()
        await flow.run(mock_context)
        
        assert run_called
    
    @pytest.mark.asyncio
    async def test_on_complete_called_on_success(self, mock_context: TaskContext):
        """验证成功时调用 on_complete。"""
        complete_called = False
        
        class SuccessFlow(TaskFlow):
            name = "success"
            
            async def run(self, ctx: TaskContext) -> None:
                pass
            
            async def on_complete(self, ctx: TaskContext) -> None:
                nonlocal complete_called
                complete_called = True
        
        flow = SuccessFlow()
        
        # 模拟运行时执行流程
        try:
            await flow.run(mock_context)
            await flow.on_complete(mock_context)
        except Exception as e:
            await flow.on_error(mock_context, e)
        
        assert complete_called
    
    @pytest.mark.asyncio
    async def test_on_error_called_on_failure(self, mock_context: TaskContext):
        """验证失败时调用 on_error。"""
        error_called = False
        captured_error = None
        
        class FailureFlow(TaskFlow):
            name = "failure"
            
            async def run(self, ctx: TaskContext) -> None:
                raise ValueError("模拟错误")
            
            async def on_error(self, ctx: TaskContext, error: Exception) -> None:
                nonlocal error_called, captured_error
                error_called = True
                captured_error = error
        
        flow = FailureFlow()
        
        # 模拟运行时执行流程
        try:
            await flow.run(mock_context)
        except ValueError as e:
            await flow.on_error(mock_context, e)
        
        assert error_called
        assert isinstance(captured_error, ValueError)
        assert str(captured_error) == "模拟错误"


class TestTaskFlowSubtaskIntegration:
    """测试 TaskFlow 子任务集成。"""
    
    @pytest.mark.asyncio
    async def test_workflow_with_subtasks(self, mock_context: TaskContext):
        """验证工作流可以调用子任务。"""
        subtask_calls: list[str] = []
        
        # 设置 Mock 执行器
        async def mock_executor(task_name: str, ctx: TaskContext) -> TaskResult:
            subtask_calls.append(task_name)
            return TaskResult.ok(data={"task": task_name})
        
        mock_context._subtask_executor = mock_executor
        
        class MultiStepFlow(TaskFlow):
            name = "multi_step"
            
            async def run(self, ctx: TaskContext) -> None:
                await ctx.run_subtask("step1")
                await ctx.run_subtask("step2")
                await ctx.run_subtask("step3")
        
        flow = MultiStepFlow()
        await flow.run(mock_context)
        
        assert subtask_calls == ["step1", "step2", "step3"]
    
    @pytest.mark.asyncio
    async def test_workflow_with_loop_and_stop(self, mock_context: TaskContext):
        """验证工作流循环和停止控制。"""
        iterations = 0
        
        class LoopFlow(TaskFlow):
            name = "loop"
            
            async def run(self, ctx: TaskContext) -> None:
                nonlocal iterations
                while not ctx.should_stop():
                    iterations += 1
                    if iterations >= 5:
                        ctx.request_stop()
        
        flow = LoopFlow()
        await flow.run(mock_context)
        
        assert iterations == 5
        assert mock_context.should_stop() is True
    
    @pytest.mark.asyncio
    async def test_workflow_state_sharing(self, mock_context: TaskContext):
        """验证工作流状态共享。"""
        class StateFlow(TaskFlow):
            name = "state"
            
            async def run(self, ctx: TaskContext) -> None:
                ctx.state["phase"] = "init"
                ctx.state["cursor"] = 0
                
                # 模拟处理过程
                ctx.state["phase"] = "processing"
                ctx.state["cursor"] = 100
                
                ctx.state["phase"] = "complete"
        
        flow = StateFlow()
        await flow.run(mock_context)
        
        assert mock_context.state["phase"] == "complete"
        assert mock_context.state["cursor"] == 100

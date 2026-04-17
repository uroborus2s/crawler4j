"""TaskFlow 单元测试。"""

from unittest.mock import MagicMock

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
    
    def test_taskflow_has_single_run_entry(self):
        """验证 TaskFlow 仅暴露主编排入口。"""
        class MinimalFlow(TaskFlow):
            name = "minimal"
            
            async def run(self, ctx: TaskContext) -> None:
                pass
        
        flow = MinimalFlow()
        assert hasattr(flow, "run")
        assert not hasattr(flow, "on_error")
        assert not hasattr(flow, "on_complete")


class TestTaskFlowExecution:
    """测试 TaskFlow 执行。"""

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
    async def test_workflow_receives_falsey_mapping_for_failed_subtask(self, mock_context: TaskContext):
        """验证失败子任务对工作流仍保持 falsey，但可读取结构化错误。"""

        async def mock_executor(task_name: str, ctx: TaskContext) -> TaskResult:
            del task_name, ctx
            return TaskResult.fail(
                message="labor login failed",
                error="invalid_labor_credentials",
            )

        mock_context._subtask_executor = mock_executor

        class FailureAwareFlow(TaskFlow):
            name = "failure_aware"

            async def run(self, ctx: TaskContext) -> None:
                result = await ctx.run_subtask("login_labor_task")
                ctx.state["subtask_result"] = result
                ctx.state["subtask_truthy"] = bool(result)

        flow = FailureAwareFlow()
        await flow.run(mock_context)

        subtask_result = mock_context.state["subtask_result"]
        assert isinstance(subtask_result, dict)
        assert mock_context.state["subtask_truthy"] is False
        assert subtask_result["status"] == "failed"
        assert subtask_result["error"] == "invalid_labor_credentials"
    
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

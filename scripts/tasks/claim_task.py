"""领题子任务

封装劳保平台领题流程。
"""

from crawler4j_sdk import TaskContext, TaskResult, TaskScript


class ClaimTask(TaskScript):
    """领题任务"""
    
    name = "claim_task"
    display_name = "领取任务"
    description = "从劳保平台领取一个任务"
    
    default_config = {
        "max_attempts": 6,
        "wait_seconds": 30,
    }
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        """执行领题"""
        from src.automation.workflows.labor_claim_task import LaborClaimTaskWorkflow
        from src.core.models.labor_task import TaskState
        
        if not ctx.page:
            return TaskResult.fail(message="浏览器Page未初始化")
        
        workflow = LaborClaimTaskWorkflow(ctx.page)
        
        max_attempts = ctx.get_config("max_attempts", 6)
        wait_seconds = ctx.get_config("wait_seconds", 30)
        
        ctx.logger.info(f"📋 开始领题 (最多尝试 {max_attempts} 次)")
        
        task = await workflow.claim_task(
            max_attempts=max_attempts,
            wait_seconds=wait_seconds
        )
        
        if task.is_complete:
            ctx.logger.info(f"✅ 领题成功: {task.hotel_name}")
            # 将任务信息存入state供后续子任务使用
            ctx.state["current_task"] = task
            return TaskResult.ok(
                tasks_completed=1,
                message=f"领取到任务: {task.hotel_name}",
                data={"task": task}
            )
        elif task.state == TaskState.NO_TASK:
            ctx.logger.warning("暂无可领取的任务")
            return TaskResult.fail(message="暂无任务")
        else:
            ctx.logger.error(f"领题失败: {task.state}")
            return TaskResult.fail(message=f"领题失败: {task.state}")
    
    async def on_error(self, ctx: TaskContext, error: Exception):
        """错误处理"""
        ctx.logger.error(f"领题出错: {error}")
        await ctx.screenshot("claim_task_error")

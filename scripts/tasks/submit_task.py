"""提交结果子任务

封装劳保平台结果提交流程。
"""

from crawler4j_sdk import TaskContext, TaskResult, TaskScript


class SubmitTask(TaskScript):
    """提交任务"""
    
    name = "labor_submit"
    display_name = "提交结果"
    description = "向劳保平台提交采集结果"
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        """执行提交"""
        from src.automation.workflows.labor_submit import LaborSubmitWorkflow
        
        if not ctx.page:
            return TaskResult.fail(message="浏览器Page未初始化")
        
        # 从state获取采集数据
        hotel_data = ctx.state.get("hotel_data")
        if not hotel_data:
            return TaskResult.fail(message="未找到待提交的采集数据")
        
        workflow = LaborSubmitWorkflow(ctx.page)
        
        ctx.logger.info("📤 开始提交结果")
        
        success = await workflow.submit_result(hotel_data)
        
        if success:
            ctx.logger.info("✅ 提交成功")
            return TaskResult.ok(
                tasks_completed=1,
                message="提交成功"
            )
        else:
            ctx.logger.error("❌ 提交失败")
            return TaskResult.fail(message="提交失败")
    
    async def on_error(self, ctx: TaskContext, error: Exception):
        """错误处理"""
        ctx.logger.error(f"提交出错: {error}")
        await ctx.screenshot("submit_error")

"""携程搜索子任务

封装携程酒店搜索和数据采集流程。
"""

from crawler4j_sdk import TaskContext, TaskResult, TaskScript


class CtripSearchTask(TaskScript):
    """携程搜索任务"""
    
    name = "ctrip_search"
    display_name = "携程搜索"
    description = "在携程搜索酒店并采集数据"
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        """执行搜索采集"""
        from src.automation.workflows.ctrip_search import CtripSearchWorkflow
        from src.automation.workflows.labor_claim_task import LaborClaimTaskWorkflow
        
        if not ctx.page:
            return TaskResult.fail(message="浏览器Page未初始化")
        
        # 从state获取任务信息
        task = ctx.state.get("current_task")
        if not task:
            return TaskResult.fail(message="未找到待采集的任务信息")
        
        # 创建工作流
        claim_workflow = LaborClaimTaskWorkflow(ctx.page)
        search_workflow = CtripSearchWorkflow(ctx.page, claim_workflow=claim_workflow)
        
        ctx.logger.info(f"🔍 开始搜索采集: {task.hotel_name}")
        
        hotel_data = await search_workflow.search_and_capture(task)
        
        # 检查账号被封
        if search_workflow.is_account_blacklisted():
            ctx.logger.error("🚫 携程账号被封")
            ctx.state["ctrip_blacklisted"] = True
            return TaskResult.fail(message="携程账号被封")
        
        # 处理结果
        if hotel_data == "废弃重领":
            ctx.logger.warning("酒店匹配失败，已废弃题目")
            return TaskResult.ok(
                tasks_completed=0,
                message="废弃重领",
                data={"action": "discard_and_reclaim"}
            )
        elif hotel_data is None or hotel_data == "搜索不到":
            ctx.logger.warning("搜索失败或搜索不到")
            return TaskResult.fail(message="搜索失败")
        elif isinstance(hotel_data, dict):
            ctx.logger.info("✅ 采集成功")
            ctx.state["hotel_data"] = hotel_data
            return TaskResult.ok(
                tasks_completed=1,
                message="采集成功",
                data={"hotel_data": hotel_data}
            )
        else:
            return TaskResult.fail(message=f"未知数据类型: {type(hotel_data)}")
    
    async def on_error(self, ctx: TaskContext, error: Exception):
        """错误处理"""
        ctx.logger.error(f"携程搜索出错: {error}")
        await ctx.screenshot("ctrip_search_error")

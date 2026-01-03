"""劳保登录子任务

封装劳保平台登录流程为独立的子任务脚本。
"""

from crawler4j_sdk import TaskContext, TaskResult, TaskScript


class LaborLoginTask(TaskScript):
    """劳保平台登录任务"""
    
    name = "labor_login"
    display_name = "劳保登录"
    description = "登录劳保平台"
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        """执行登录流程"""
        from src.automation.workflows.labor_login import LaborLoginWorkflow
        from src.core.models.labor_account import LaborAccount
        
        if not ctx.page:
            return TaskResult.fail(message="浏览器Page未初始化")
        
        # 获取账号信息
        labor_info = ctx.labor_account
        if not labor_info:
            return TaskResult.fail(message="未提供劳保账号信息")
        
        # 构造LaborAccount对象
        account = LaborAccount(
            id=labor_info.id,
            phone=labor_info.phone_number,
            password=labor_info.password,
        )
        
        # 创建工作流实例
        workflow = LaborLoginWorkflow(ctx.page)
        
        # 执行登录
        ctx.logger.info(f"🔐 开始劳保登录: {account.phone}")
        success = await workflow.ensure_logged_in(account)
        
        if success:
            ctx.logger.info("✅ 劳保登录成功")
            ctx.state["labor_logged_in"] = True
            return TaskResult.ok(
                tasks_completed=1,
                message="登录成功"
            )
        else:
            ctx.logger.error("❌ 劳保登录失败")
            return TaskResult.fail(message="劳保登录失败")
    
    async def on_error(self, ctx: TaskContext, error: Exception):
        """错误处理"""
        ctx.logger.error(f"劳保登录出错: {error}")
        await ctx.screenshot("labor_login_error")

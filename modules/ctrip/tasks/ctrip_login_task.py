"""携程登录子任务

封装携程登录流程为独立的子任务脚本。
"""

from crawler4j_sdk import TaskContext, TaskResult, TaskScript


class CtripLoginTask(TaskScript):
    """携程登录任务
    
    执行携程账号的登录流程，包括：
    1. 导航到登录页面
    2. 输入手机号
    3. 处理验证码（滑块/点选）
    4. 获取短信验证码
    5. 完成登录
    """
    
    name = "ctrip_login"
    display_name = "携程登录"
    description = "登录携程账号"
    
    default_config = {
        "max_retries": 2,
    }
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        """执行登录流程"""
        from src.automation.workflows.ctrip_login import CtripLoginWorkflow
        from src.core.models.ctrip_account import CtripAccount
        
        if not ctx.page:
            return TaskResult.fail(message="浏览器Page未初始化")
        
        # 获取账号信息
        ctrip_info = ctx.ctrip_account
        if not ctrip_info:
            return TaskResult.fail(message="未提供携程账号信息")
        
        # 构造CtripAccount对象
        account = CtripAccount(
            id=ctrip_info.id,
            phone_number=ctrip_info.phone_number,
            country_code=ctrip_info.country_code,
        )
        
        # 创建工作流实例
        workflow = CtripLoginWorkflow(ctx.page)
        
        # 检查是否已登录
        if await workflow.is_logged_in():
            ctx.logger.info("✅ 携程已登录，跳过登录流程")
            ctx.state["ctrip_logged_in"] = True
            return TaskResult.ok(
                tasks_completed=1,
                message="已登录",
                data={"status": "already_logged_in"}
            )
        
        # 执行登录
        ctx.logger.info(f"🔐 开始携程登录: {account.phone_number}")
        result = await workflow.login(account, input_callback=ctx.input_callback)
        
        if result:
            ctx.logger.info("✅ 携程登录成功")
            ctx.state["ctrip_logged_in"] = True
            return TaskResult.ok(
                tasks_completed=1,
                message="登录成功",
                data={"phone": result}
            )
        else:
            ctx.logger.error("❌ 携程登录失败")
            return TaskResult.fail(message="携程登录失败")
    
    async def on_error(self, ctx: TaskContext, error: Exception):
        """错误处理"""
        ctx.logger.error(f"携程登录出错: {error}")
        await ctx.screenshot("ctrip_login_error")

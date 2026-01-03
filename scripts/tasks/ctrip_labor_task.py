"""携程劳保采集任务脚本

基于LaborWorkflowRunner封装的标准任务脚本。
"""

from crawler4j_sdk import TaskContext, TaskResult, TaskScript


class CtripLaborTask(TaskScript):
    """携程劳保采集任务
    
    执行完整的劳保平台任务流程：
    1. 劳保登录
    2. 领题
    3. 携程搜索采集
    4. 提交答案
    """
    
    name = "ctrip_labor_task"
    display_name = "携程劳保采集"
    description = "自动化执行携程酒店信息采集并提交到劳保平台"
    
    default_config = {
        "max_consecutive_tasks": 10,      # 连续做题数量
        "task_interval_min": 1,           # 任务间隔最小秒数
        "task_interval_max": 5,           # 任务间隔最大秒数
        "search_timeout": 15,             # 搜索超时秒数
        "retry_on_fail": True,            # 失败时重试
    }
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        """执行任务"""
        # 延迟导入框架内部模块
        from src.automation.workflows.labor_workflow_runner import LaborWorkflowRunner
        from src.core.models.ctrip_account import CtripAccount
        from src.core.models.labor_account import LaborAccount
        
        if not ctx.page:
            return TaskResult.fail("Page未初始化")
        
        if not ctx.labor_account:
            return TaskResult.fail("劳保账号未配置")
        
        if not ctx.ctrip_account:
            return TaskResult.fail("携程账号未配置")
        
        ctx.logger.info(f"开始执行携程劳保采集任务")
        ctx.logger.info(f"劳保账号: {ctx.labor_account.phone_number}")
        ctx.logger.info(f"配置: {ctx.config}")
        
        # 创建工作流运行器
        runner = LaborWorkflowRunner(ctx.page)
        
        # 构建账号对象
        labor_acc = LaborAccount(
            id=ctx.labor_account.id,
            phone_number=ctx.labor_account.phone_number,
            password=ctx.labor_account.password,
        )
        
        ctrip_acc = CtripAccount(
            id=ctx.ctrip_account.id,
            phone_number=ctx.ctrip_account.phone_number,
            country_code=ctx.ctrip_account.country_code,
        )
        
        try:
            # 执行自动任务
            await runner.run_auto_tasks(
                labor_account=labor_acc,
                ctrip_account=ctrip_acc,
                env_id=ctx.env_id,
            )
            
            # 获取统计结果
            completed = runner.stats_completed
            failed = runner.stats_failed
            
            ctx.logger.info(f"任务完成: 成功{completed}, 失败{failed}")
            
            return TaskResult.ok(
                tasks_completed=completed,
                message=f"完成{completed}个任务",
                completed=completed,
                failed=failed,
            )
            
        except Exception as e:
            ctx.logger.error(f"任务执行失败: {e}")
            return TaskResult.fail(str(e), error=str(e))
    
    async def on_error(self, ctx: TaskContext, error: Exception):
        """错误处理"""
        ctx.logger.error(f"携程劳保任务异常: {error}")
        await ctx.screenshot("error_ctrip_labor")

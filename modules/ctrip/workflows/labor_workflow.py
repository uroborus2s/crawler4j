"""标准劳保工作流

复合任务：编排所有子任务，实现完整的做题流程。
"""

from crawler4j_sdk import TaskContext, TaskFlow


class StandardLaborWorkflow(TaskFlow):
    """标准劳保做题工作流
    
    完整流程：
    1. 携程登录
    2. 劳保登录
    3. 循环：领题 -> 搜索采集 -> 提交
    """
    
    name = "standard_labor_workflow"
    display_name = "标准劳保工作流"
    description = "完整的劳保做题流程"
    
    async def run(self, ctx: TaskContext) -> None:
        """执行工作流"""
        max_tasks = ctx.get_config("max_tasks", 10)
        completed = 0
        
        ctx.logger.info(f"🚀 启动标准劳保工作流 (目标: {max_tasks} 个任务)")
        
        # 1. 携程登录
        login_result = await ctx.run_subtask("ctrip_login")
        if not login_result:
            ctx.logger.error("携程登录失败，终止工作流")
            return
        
        # 2. 劳保登录
        labor_result = await ctx.run_subtask("labor_login")
        if not labor_result:
            ctx.logger.error("劳保登录失败，终止工作流")
            return
        
        # 3. 任务循环
        while not ctx.should_stop() and completed < max_tasks:
            ctx.logger.info(f"--- 执行第 {completed + 1}/{max_tasks} 个任务 ---")
            
            # 3.1 领题
            claim_result = await ctx.run_subtask("claim_task")
            if not claim_result:
                ctx.logger.warning("领题失败，结束工作流")
                break
            
            # 3.2 搜索采集
            search_result = await ctx.run_subtask("ctrip_search")
            
            # 检查账号被封
            if ctx.state.get("ctrip_blacklisted"):
                ctx.logger.error("🚫 携程账号被封，终止工作流")
                break
            
            # 处理废弃重领
            if search_result and search_result.get("action") == "discard_and_reclaim":
                ctx.logger.info("重新领题...")
                continue
            
            if not search_result:
                ctx.logger.warning("搜索失败，跳过本次")
                continue
            
            # 3.3 提交结果
            submit_result = await ctx.run_subtask("labor_submit")
            if submit_result:
                completed += 1
                ctx.logger.info(f"✅ 任务完成 ({completed}/{max_tasks})")
            else:
                ctx.logger.warning("提交失败")
            
            # 任务间隔
            if completed < max_tasks and not ctx.should_stop():
                import asyncio
                import random
                wait_time = random.uniform(60, 180)  # 1-3分钟
                ctx.logger.info(f"☕️ 等待 {wait_time/60:.1f} 分钟后继续...")
                await asyncio.sleep(wait_time)
        
        ctx.logger.info(f"🏁 工作流完成，共完成 {completed} 个任务")
    
    async def on_complete(self, ctx: TaskContext) -> None:
        """工作流完成"""
        completed = ctx.state.get("completed_tasks", 0)
        ctx.logger.info(f"标准劳保工作流执行完毕，完成 {completed} 个任务")

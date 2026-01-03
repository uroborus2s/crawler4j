"""示例任务脚本

演示如何编写一个任务脚本。
"""

from crawler4j_sdk import TaskContext, TaskResult, TaskScript


class ExampleTask(TaskScript):
    """示例任务脚本"""
    
    name = "example_task"
    display_name = "示例任务"
    description = "这是一个示例任务脚本，演示基本用法"
    
    default_config = {
        "target_url": "https://example.com",
        "max_items": 10,
    }
    
    async def execute(self, ctx: TaskContext) -> TaskResult:
        """主执行方法"""
        ctx.logger.info("开始执行示例任务")
        
        # 获取配置
        target_url = ctx.get_config("target_url", "https://example.com")
        max_items = ctx.get_config("max_items", 10)
        
        ctx.logger.info(f"目标URL: {target_url}")
        ctx.logger.info(f"最大条数: {max_items}")
        
        # 访问页面
        if ctx.page:
            await ctx.page.goto(target_url)
            ctx.logger.info("页面加载完成")
            
            # 获取标题
            title = await ctx.page.title()
            ctx.logger.info(f"页面标题: {title}")
            
            # 截图
            await ctx.screenshot("example_page")
        
        # 等待一下
        await ctx.wait(1)
        
        # 返回成功结果
        return TaskResult.ok(
            tasks_completed=1,
            message="示例任务执行成功",
            title=title if ctx.page else "N/A",
        )
    
    async def on_error(self, ctx: TaskContext, error: Exception):
        """错误处理"""
        ctx.logger.error(f"任务出错: {error}")
        await ctx.screenshot("error_screenshot")

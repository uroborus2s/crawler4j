"""Labor task claim workflow module.

Handles claiming (taking) a new task from the platform.
"""


from src.automation.workflows.base import BaseWorkflow
from src.utils.logger import logger


class LaborClaimTaskWorkflow(BaseWorkflow):
    """Workflow for claiming tasks on the Labor platform."""
    
    CLAIM_URL = "http://labour.project.com/tasks/claim" # Placeholder
    
    async def claim_task(self) -> str | None:
        """Claim a new task and return the task keyword/ID.
        
        Returns:
            The search keyword/task text if successful, None otherwise.
        """
        logger.info("尝试领取新任务...")
        
        try:
            await self.page.goto(self.CLAIM_URL)
            
            # Click "Claim" button
            claim_btn = "button.btn-claim:not([disabled])"
            if await self.is_visible(claim_btn):
                await self.page.click(claim_btn)
                await self.page.wait_for_timeout(2000)
                
                # Extract task text (e.g., search keyword)
                task_text_selector = ".task-info .keyword"
                if await self.is_visible(task_text_selector):
                    keyword = await self.page.inner_text(task_text_selector)
                    keyword = keyword.strip()
                    logger.info(f"成功领取任务, 搜索关键词: {keyword}")
                    return keyword
                else:
                    logger.warning("成功点击领取，但未找到任务关键词")
            else:
                logger.info("当前没有可领取的工作")
                
            return None
                
        except Exception as e:
            logger.error(f"领取任务异常: {e}")
            return None

"""Labor task submit workflow module.

Handles submitting results back to the platform.
"""


from src.automation.workflows.base import BaseWorkflow
from src.utils.logger import logger


class LaborSubmitWorkflow(BaseWorkflow):
    """Workflow for submitting task results to the Labor platform."""
    
    async def submit_result(self, result: str = "success") -> bool:
        """Submit the task result.
        
        Args:
            result: Result text or status.
            
        Returns:
            True if submission successful.
        """
        logger.info("正在提交任务结果...")
        
        try:
            # Switch back to labor platform tab if needed
            # (Assuming we are already on the submission page)
            
            # Fill result (if any)
            # await self.page.fill("textarea#result", result)
            
            # Click submit
            submit_btn = "button:has-text('提交')"
            await self.wait_and_click(submit_btn)
            
            # Wait for confirmation
            await self.page.wait_for_timeout(2000)
            
            if await self.is_visible(".alert-success") or "success" in self.page.url:
                logger.info("任务结果提交成功")
                return True
            else:
                logger.error("提交确认失败")
                return False
                
        except Exception as e:
            logger.error(f"提交任务异常: {e}")
            return False

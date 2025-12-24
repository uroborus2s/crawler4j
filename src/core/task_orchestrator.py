"""Task orchestrator module.

Coordinates the execution of multiple workflows within a single environment.
"""

from playwright.async_api import Page

from src.automation.workflows.ctrip_login import CtripLoginWorkflow
from src.automation.workflows.labor_login import LaborLoginWorkflow
from src.automation.workflows.labor_claim_task import LaborClaimTaskWorkflow
from src.automation.workflows.ctrip_search import CtripSearchWorkflow
from src.automation.workflows.labor_submit import LaborSubmitWorkflow
from src.core.models.ctrip_account import CtripAccount
from src.core.models.labor_account import LaborAccount
from src.utils.logger import logger


class TaskOrchestrator:
    """Orchestrates the full automation loop for an environment."""
    
    def __init__(self, page: Page):
        self.page = page
        
    async def run_loop_once(self, ctrip: CtripAccount, labor: LaborAccount) -> bool:
        """Run a single 'Claim -> Search -> Submit' loop.
        
        Args:
            ctrip: Ctrip account to use for searching.
            labor: Labor account to use for claiming/submitting.
            
        Returns:
            True if one task was successfully completed.
        """
        try:
            # 1. Ensure logged in to both platforms
            # (In a real scenario, we might optimize by checking cookies/state first)
            
            ctrip_workflow = CtripLoginWorkflow(self.page)
            if not await ctrip_workflow.login(ctrip):
                logger.error(f"携程账号 {ctrip.phone} 登录失败")
                return False
                
            labor_workflow = LaborLoginWorkflow(self.page)
            if not await labor_workflow.login(labor):
                logger.error(f"劳保账号 {labor.phone} 登录失败")
                return False
                
            # 2. Claim a task
            claim_workflow = LaborClaimTaskWorkflow(self.page)
            keyword = await claim_workflow.claim_task()
            
            if not keyword:
                logger.info("当前无有效任务可做")
                return False
                
            # 3. Perform search on Ctrip
            search_workflow = CtripSearchWorkflow(self.page)
            if not await search_workflow.search(keyword):
                logger.error(f"携程搜索失败, 关键词: {keyword}")
                return False
                
            # 4. Submit result back to Labor platform
            submit_workflow = LaborSubmitWorkflow(self.page)
            if not await submit_workflow.submit_result():
                logger.error("劳保平台提交失败")
                return False
                
            logger.info(f"✨ 成功完成一轮自动化任务: {keyword}")
            return True
            
        except Exception as e:
            logger.error(f"任务编排执行异常: {e}")
            return False

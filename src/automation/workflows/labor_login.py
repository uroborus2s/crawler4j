"""Labor platform login workflow module.

Handles login to the project management platform.
"""


from src.automation.workflows.base import BaseWorkflow
from src.core.models.labor_account import LaborAccount
from src.utils.logger import logger


class LaborLoginWorkflow(BaseWorkflow):
    """Workflow for logging into the Labor platform."""
    
    URL = "http://labour.project.com/login" # Placeholder URL
    
    async def login(self, account: LaborAccount) -> bool:
        """Execute login process.
        
        Args:
            account: LaborAccount model with phone/password.
            
        Returns:
            True if login successful.
        """
        logger.info(f"开始劳保平台登录: {account.phone}")
        
        try:
            await self.page.goto(self.URL)
            
            # Check if already logged in
            if "login" not in self.page.url:
                logger.info("检测到已处于登录状态")
                return True
                
            # Type credentials
            await self.wait_and_type("input[name='username']", account.phone)
            await self.wait_and_type("input[name='password']", account.password)
            
            # Click login button
            submit_btn = "button[type='submit']"
            await self.wait_and_click(submit_btn)
            
            # Wait for success - usually redirects to dashboard/index
            await self.page.wait_for_timeout(3000)
            
            if "login" not in self.page.url or await self.is_visible(".nav-user"):
                logger.info(f"劳保平台登录成功: {account.phone}")
                return True
            else:
                logger.error(f"劳保平台登录失败: {account.phone} (停留于 {self.page.url})")
                await self.screenshot(f"labor_login_fail_{account.phone}")
                return False
                
        except Exception as e:
            logger.error(f"劳保平台登录异常: {e}")
            await self.screenshot(f"labor_login_error_{account.phone}")
            return False

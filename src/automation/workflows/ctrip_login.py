"""Ctrip login workflow module.

Handles login to Ctrip platform via SMS verification or password.
"""


from src.automation.workflows.base import BaseWorkflow
from src.automation.workflows.sms_receiver import SMSReceiver
from src.core.models.ctrip_account import CtripAccount
from src.utils.logger import logger


class CtripLoginWorkflow(BaseWorkflow):
    """Workflow for logging into Ctrip."""
    
    URL = "https://passport.ctrip.com/user/login"
    
    async def login(self, account: CtripAccount) -> bool:
        """Execute login process.
        
        Args:
            account: CtripAccount model with credentials and SMS config.
            
        Returns:
            True if login successful.
        """
        logger.info(f"开始携程登录: {account.phone}")
        
        try:
            await self.page.goto(self.URL)
            
            # Check if already logged in (redirected to home)
            if "login" not in self.page.url:
                logger.info("检测到已处于登录状态")
                return True
                
            # Click SMS login tab if available
            sms_tab_selector = ".pop-box .pop-nav li:last-child" # Placeholder
            if await self.is_visible(sms_tab_selector):
                await self.page.click(sms_tab_selector)
                
            # Type phone
            await self.wait_and_type("input[placeholder='请输入手机号']", account.phone)
            
            # Check if password or SMS
            if account.password and await self.is_visible("input[type='password']"):
                logger.debug("尝试使用密码登录")
                await self.page.fill("input[type='password']", account.password)
                await self.page.click("button.login-btn")
            else:
                logger.debug("尝试使用短信验证码登录")
                # Trigger SMS
                get_code_btn = "button:has-text('获取验证码')"
                await self.wait_and_click(get_code_btn)
                
                # Fetch code from SMS platform
                if not account.has_sms_config:
                    logger.error("未配置接码平台，无法执行短信登录")
                    return False
                    
                code = await SMSReceiver.fetch(
                    phone=account.phone,
                    url=account.sms_platform_url,
                    key=account.sms_platform_key,
                    p_type=account.sms_platform_type
                )
                
                if not code:
                    logger.error("获取短信验证码失败")
                    return False
                    
                # Input code
                await self.wait_and_type("input[placeholder='请输入验证码']", code)
                
                # Click login
                await self.page.click("button:has-text('登录')")
                
            # Wait for navigation or success indicator
            await self.page.wait_for_timeout(3000)
            
            if "login" not in self.page.url or await self.is_visible(".user-info"):
                logger.info(f"携程登录成功: {account.phone}")
                return True
            else:
                logger.error(f"携程登录失败: {account.phone} (停留于 {self.page.url})")
                await self.screenshot(f"ctrip_login_fail_{account.phone}")
                return False
                
        except Exception as e:
            logger.error(f"携程登录异常: {e}")
            await self.screenshot(f"ctrip_login_error_{account.phone}")
            return False
            
    async def is_logged_in(self) -> bool:
        """Check if currently logged in."""
        try:
            await self.page.goto(self.URL, wait_until="networkidle")
            return "login" not in self.page.url
        except Exception:
            return False

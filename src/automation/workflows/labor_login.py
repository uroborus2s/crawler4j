"""Labor platform login workflow module.

Handles login to the Labor (劳保保) platform at frontend.lobaobao97.com.
"""

import asyncio
import random

from playwright.async_api import Page

from src.automation.workflows.base import BaseWorkflow
from src.core.models.labor_account import LaborAccount
from src.utils.logger import logger


class LaborLoginWorkflow(BaseWorkflow):
    """Workflow for logging into the Labor platform (劳保保)."""
    
    # 劳保平台真实URL
    LOGIN_URL = "https://frontend.lobaobao97.com/login"
    HOME_URL = "https://frontend.lobaobao97.com/mark"
    
    # DOM 选择器 (基于 content.js 第 2947-2976 行分析)
    ACCOUNT_INPUT = "#account"
    PASSWORD_INPUT = "#secret_key"
    LOGIN_BUTTON = "button:has-text('登录')"
    
    # 登录成功后的标识
    DAILY_OUTPUT_TEXT = "当日产量"
    
    async def _human_type(self, selector: str, text: str):
        """模拟人类输入，带随机延迟。"""
        await self.page.click(selector)
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        for char in text:
            await self.page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.03, 0.12))
    
    async def _human_click(self, selector: str):
        """模拟人类点击，带随机延迟。"""
        await asyncio.sleep(random.uniform(0.1, 0.3))
        await self.page.click(selector)
    
    async def is_logged_in(self) -> bool:
        """检查是否已登录。
        
        通过检测页面URL或特定元素判断登录状态。
        
        Returns:
            True if logged in, False otherwise.
        """
        try:
            current_url = self.page.url
            
            # 1. URL 检查：如果不在登录页，可能已登录
            if "login" not in current_url.lower():
                # 进一步验证：检查做题页面特有元素
                if await self.is_visible(f"text={self.DAILY_OUTPUT_TEXT}", timeout=2000):
                    return True
                    
            # 2. 检查是否有"选择城市"按钮（做题页面标识）
            if await self.is_visible("button:has-text('选择城市')", timeout=2000):
                return True
                
            return False
            
        except Exception as e:
            logger.debug(f"登录状态检查异常: {e}")
            return False
    
    async def navigate_to_login(self) -> bool:
        """导航到登录页面。
        
        Returns:
            True if navigation successful.
        """
        try:
            await self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.error(f"导航到登录页失败: {e}")
            return False
    
    async def navigate_to_task_page(self) -> bool:
        """导航到做题页面。
        
        Returns:
            True if navigation successful.
        """
        try:
            await self.page.goto(self.HOME_URL, wait_until="domcontentloaded")
            await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.error(f"导航到做题页失败: {e}")
            return False
    
    async def login(self, account: LaborAccount) -> bool:
        """执行登录流程。
        
        Args:
            account: LaborAccount 包含 phone/password 的账号信息。
            
        Returns:
            True if login successful.
        """
        logger.info(f"开始劳保平台登录: {account.phone}")
        
        try:
            # 1. 先检查是否已登录
            if await self.is_logged_in():
                logger.info("检测到已处于登录状态")
                return True
            
            # 2. 导航到登录页
            if not await self.navigate_to_login():
                return False
            
            # 3. 等待登录表单加载
            try:
                await self.page.wait_for_selector(self.ACCOUNT_INPUT, state="visible", timeout=10000)
            except Exception:
                logger.error("登录表单加载超时")
                await self.screenshot(f"labor_login_form_timeout")
                return False
            
            # 4. 清空并输入账号
            await self.page.fill(self.ACCOUNT_INPUT, "")
            await self._human_type(self.ACCOUNT_INPUT, account.phone)
            
            # 5. 清空并输入密码
            await self.page.fill(self.PASSWORD_INPUT, "")
            await self._human_type(self.PASSWORD_INPUT, account.password)
            
            # 6. 点击登录按钮
            await asyncio.sleep(random.uniform(0.3, 0.6))
            await self._human_click(self.LOGIN_BUTTON)
            
            # 7. 等待登录结果
            logger.info("正在登录...")
            await asyncio.sleep(3)
            
            # 8. 验证登录成功
            # 检查是否跳转到做题页面或出现做题页面元素
            for _ in range(5):  # 最多等待5秒
                if await self.is_logged_in():
                    logger.info(f"劳保平台登录成功: {account.phone}")
                    return True
                await asyncio.sleep(1)
            
            # 登录失败
            logger.error(f"劳保平台登录失败: {account.phone}")
            await self.screenshot(f"labor_login_fail_{account.phone}")
            
            # 检查是否有错误提示
            error_msg = await self._get_error_message()
            if error_msg:
                logger.error(f"错误信息: {error_msg}")
            
            return False
                
        except Exception as e:
            logger.error(f"劳保平台登录异常: {e}")
            await self.screenshot(f"labor_login_error_{account.phone}")
            return False
    
    async def _get_error_message(self) -> str | None:
        """获取页面上的错误提示信息。"""
        try:
            # 常见错误提示选择器
            error_selectors = [
                ".error-message",
                ".toast-message",
                ".adm-toast-text",
                "[class*='error']",
            ]
            
            for selector in error_selectors:
                if await self.is_visible(selector, timeout=1000):
                    return await self.page.inner_text(selector)
            
            return None
        except Exception:
            return None
    
    async def ensure_logged_in(self, account: LaborAccount) -> bool:
        """确保已登录，如未登录则执行登录。
        
        这是一个便捷方法，先检查登录状态，未登录再执行登录流程。
        
        Args:
            account: 劳保账号信息
            
        Returns:
            True if logged in (either already or after login).
        """
        if await self.is_logged_in():
            logger.info("劳保平台已登录")
            return True
        
        return await self.login(account)

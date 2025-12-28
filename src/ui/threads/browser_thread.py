"""Browser launcher thread.

Handles opening the browser via API and executing auto-login automation.
"""

import asyncio

from playwright.async_api import async_playwright
from PyQt6.QtCore import QThread, pyqtSignal

from src.automation.workflows.ctrip_login import CtripLoginWorkflow
from src.automation.workflows.labor_login import LaborLoginWorkflow
from src.core.browser_api import BrowserAPI
from src.core.models.ctrip_account import CtripAccount
from src.core.models.labor_account import LaborAccount
from src.utils.logger import logger
from src.utils.storage import (
    CtripAccountRepository,
    EnvironmentRepository,
    LaborAccountRepository,
)


class BrowserLauncherThread(QThread):
    """Thread to open browser and run automation."""
    
    finished_signal = pyqtSignal(bool, str)  # success, message
    input_signal = pyqtSignal(dict, object)  # container, event
    
    def __init__(
        self,
        profile_id: str,
        ctrip_account_id: int | None = None,
        labor_account_id: int | None = None,
        env_id: int | None = None,
    ):
        super().__init__()
        self.profile_id = profile_id
        self.ctrip_account_id = ctrip_account_id
        self.labor_account_id = labor_account_id
        self.env_id = env_id
        self.ctrip_repo = CtripAccountRepository()
        self.labor_repo = LaborAccountRepository()
        self.env_repo = EnvironmentRepository()
        
    def get_user_input(self, title: str, label: str, default: str = "", text: str = "") -> str | None:
        """Request input from UI thread safely."""
        import threading
        event = threading.Event()
        
        display_text = text if text else default
        container = {"title": title, "label": label, "text": display_text, "value": None}
        
        self.input_signal.emit(container, event)
        event.wait()  # Block until UI responds
        
        return container.get("value")
        
    def run(self):
        """Execute the thread."""
        try:
            # 1. Open Browser
            logger.info(f"正在打开浏览器: {self.profile_id}")
            res = BrowserAPI.open_browser(self.profile_id)
            ws_endpoint = res.get("ws_endpoint")
            http_endpoint = res.get("http_endpoint")
            
            if not ws_endpoint:
                raise RuntimeError("Failed to get Websocket endpoint")
            
            # Update DB state to Running
            if self.env_id:
                self.env_repo.update_connection_info(self.env_id, ws_endpoint, http_endpoint, None)
                self.env_repo.update_status(self.env_id, "running", last_run_at="now")
                
            # 2. Load accounts
            ctrip_account = None
            labor_account = None
            
            if self.ctrip_account_id:
                acc_data = self.ctrip_repo.get_by_id(self.ctrip_account_id)
                if acc_data:
                    ctrip_account = CtripAccount(**acc_data)
                else:
                    logger.warning("携程账号不存在，将尝试手动输入模式")
            
            if self.labor_account_id:
                labor_data = self.labor_repo.get_by_id(self.labor_account_id)
                if labor_data:
                    labor_account = LaborAccount.from_dict(labor_data)
                else:
                    logger.warning("劳保账号不存在，尝试自动分配")
                    self.labor_account_id = None  # Reset to trigger auto-bind
            
            # 智能绑定：如果未绑定劳保账号，自动选择绑定次数最少的账号
            if not self.labor_account_id and self.env_id:
                least_bound = self.labor_repo.get_least_bound()
                if least_bound:
                    # 绑定到环境并增加计数
                    self.env_repo.update(self.env_id, {"labor_account_id": least_bound["id"]})
                    self.labor_repo.increment_bind_count(least_bound["id"])
                    self.labor_account_id = least_bound["id"]
                    labor_account = LaborAccount.from_dict(least_bound)
                    logger.info(f"✅ 自动绑定劳保账号: {labor_account.phone} (bind_count: {least_bound.get('bind_count', 0) + 1})")
                else:
                    logger.warning("没有可用的劳保账号进行自动绑定")

            # 3. Run async automation
            logger.info(f"准备执行自动化: 携程={self.ctrip_account_id}, 劳保={self.labor_account_id}")
            asyncio.run(self._run_automation(ws_endpoint, ctrip_account, labor_account))
            
            self.finished_signal.emit(True, "操作完成")
            
        except Exception as e:
            logger.error(f"浏览器启动或自动化失败: {e}")
            if self.env_id:
                self.env_repo.update_status(self.env_id, "error")
            self.finished_signal.emit(False, str(e))
            
    async def _run_automation(
        self,
        ws_endpoint: str,
        ctrip_account: CtripAccount | None,
        labor_account: LaborAccount | None,
    ):
        """Connect to browser and run dual login flow."""
        async with async_playwright() as p:
            try:
                # Connect to existing browser
                browser = await p.chromium.connect_over_cdp(ws_endpoint)
                context = browser.contexts[0]
                
                # Get or create page
                page = context.pages[0] if context.pages else await context.new_page()
                
                # ========== Step 1: 携程登录 ==========
                logger.info("=== 步骤1: 携程登录 ===")
                ctrip_workflow = CtripLoginWorkflow(page)
                
                if await ctrip_workflow.is_logged_in():
                    logger.info("✅ 携程已登录，跳过")
                else:
                    login_phone = await ctrip_workflow.login(
                        ctrip_account, input_callback=self.get_user_input
                    )
                    
                    if login_phone and self.env_id:
                        # Update Environment binding
                        logger.info(f"携程登录成功: {login_phone}")
                        
                        # Find or Create Account in DB
                        all_accounts = self.ctrip_repo.get_all()
                        # Parse login_phone to extract country_code and phone_number
                        import re
                        match = re.match(r"(\+\d+)(.*)", login_phone)
                        if match:
                            cc, pn = match.group(1), match.group(2)
                        else:
                            cc, pn = "+86", login_phone
                        
                        target_acc = next(
                            (a for a in all_accounts if a.get("country_code") == cc and a.get("phone_number") == pn), None
                        )
                        
                        if target_acc:
                            acc_id = target_acc["id"]
                        else:
                            acc_id = self.ctrip_repo.create(phone_number=pn, country_code=cc)
                            logger.info(f"创建新账号记录: {login_phone} -> ID {acc_id}")
                            
                        # Bind to Environment
                        if acc_id:
                            self.env_repo.update(self.env_id, {"ctrip_account_id": acc_id})
                            logger.info(f"环境 {self.env_id} 已绑定携程账号 {login_phone}")
                    elif not login_phone:
                        logger.error("❌ 携程登录失败，正在关闭环境...")
                        from src.core.browser_api import BrowserAPI
                        BrowserAPI.close_browser(self.profile_id)
                        raise RuntimeError("携程账号登录失败")
                
                # ========== Step 2: 劳保登录 ==========
                if labor_account:
                    logger.info("=== 步骤2: 劳保登录 ===")
                    labor_workflow = LaborLoginWorkflow(page)
                    
                    if await labor_workflow.is_logged_in():
                        logger.info("✅ 劳保已登录，跳过")
                    else:
                        success = await labor_workflow.login(labor_account)
                        if success:
                            logger.info(f"✅ 劳保登录成功: {labor_account.phone}")
                        else:
                            logger.error(f"❌ 劳保登录失败: {labor_account.phone}")
                else:
                    logger.info("未配置劳保账号，跳过劳保登录")
                
                # Detach (不关闭浏览器，保持会话)
                browser.contexts[0]  # Keep reference
                logger.info("自动化流程完成，浏览器保持运行")
                
            except Exception as e:
                logger.error(f"自动化执行出错: {e}")
                raise

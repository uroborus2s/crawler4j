"""统一环境工作流程执行器。

封装完整的 登录 -> 领题 -> 做题 -> 交题 流程，
供手动启动和自动调度器共同调用。
"""

import asyncio
from dataclasses import dataclass
from enum import Enum, auto
from typing import Callable

from playwright.async_api import async_playwright

from src.automation.workflows.ctrip_login import CtripLoginWorkflow
from src.automation.workflows.labor_login import LaborLoginWorkflow
from src.automation.workflows.labor_workflow_runner import LaborWorkflowRunner
from src.core.browser_api import BrowserAPI
from src.core.models.ctrip_account import CtripAccount
from src.core.models.environment import Environment
from src.core.models.labor_account import LaborAccount
from src.utils.logger import logger
from src.utils.storage import EnvironmentRepository


class WorkflowResultType(Enum):
    """工作流执行结果类型。"""
    SUCCESS = auto()
    CTRIP_LOGIN_FAILED = auto()
    LABOR_LOGIN_FAILED = auto()
    NO_TASK = auto()
    TASK_FAILED = auto()
    BROWSER_ERROR = auto()
    ERROR = auto()


@dataclass
class WorkflowResult:
    """工作流执行结果。"""
    result_type: WorkflowResultType
    tasks_completed: int = 0
    message: str = ""
    ctrip_blacklisted: bool = False


async def execute_environment_workflow(
    environment: Environment,
    ctrip_account: CtripAccount,
    labor_account: LaborAccount,
    input_callback: Callable | None = None,
) -> WorkflowResult:
    """执行环境的完整工作流程。
    
    流程: 连接浏览器 → 携程登录 → 劳保登录 → 循环做题
    
    Args:
        environment: 目标环境
        ctrip_account: 携程账号
        labor_account: 劳保账号
        input_callback: 输入回调（用于手动模式的验证码等）
        
    Returns:
        WorkflowResult 包含执行结果
    """
    profile_id = environment.browser_profile_id
    env_id = environment.id
    env_repo = EnvironmentRepository()
    
    logger.info(f"[ENV-{env_id}] 开始执行工作流")
    logger.info(f"  携程账号: {ctrip_account.phone_number}")
    logger.info(f"  劳保账号: {labor_account.phone}")
    
    try:
        # 1. 打开浏览器
        logger.info(f"[ENV-{env_id}] 正在打开浏览器...")
        conn_info = BrowserAPI.open_browser(profile_id)
        ws_endpoint = conn_info.get("ws_endpoint")
        http_endpoint = conn_info.get("http_endpoint")
        
        if not ws_endpoint:
            return WorkflowResult(
                result_type=WorkflowResultType.BROWSER_ERROR,
                message="无法获取浏览器 WebSocket 端点"
            )
        
        # 更新环境连接信息
        if env_id:
            env_repo.update_connection_info(env_id, ws_endpoint, http_endpoint, None)
        
        # 2. 连接并执行自动化
        result = await _run_automation(
            ws_endpoint, ctrip_account, labor_account, input_callback, env_id
        )
        
        return result
        
    except Exception as e:
        logger.error(f"[ENV-{env_id}] 工作流执行异常: {e}")
        return WorkflowResult(
            result_type=WorkflowResultType.ERROR,
            message=str(e)
        )
    finally:
        # 3. 关闭浏览器
        try:
            logger.info(f"[ENV-{env_id}] 正在关闭浏览器...")
            BrowserAPI.close_browser(profile_id)
        except Exception as e:
            logger.warning(f"关闭浏览器失败: {e}")
        
        # 清理连接信息
        if env_id:
            env_repo.update_connection_info(env_id, None, None, None)


async def _run_automation(
    ws_endpoint: str,
    ctrip_account: CtripAccount,
    labor_account: LaborAccount,
    input_callback: Callable | None,
    env_id: int | None,
) -> WorkflowResult:
    """执行自动化流程。"""
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(ws_endpoint)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()
        
        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)
        
        # === Step 1: 携程登录 ===
        logger.info(f"[ENV-{env_id}] === 步骤1: 携程登录 ===")
        ctrip_workflow = CtripLoginWorkflow(page)
        
        try:
            await page.goto("https://www.ctrip.com/", wait_until="domcontentloaded", timeout=30000)
        except Exception as e:
            logger.warning(f"导航到携程首页超时: {e}")
        
        await asyncio.sleep(1)
        
        if not await ctrip_workflow.is_logged_in():
            if input_callback is None:
                # 自动模式：无法处理验证码，记录警告但继续尝试
                logger.warning("携程未登录，自动模式可能无法完成登录")
            
            login_result = await ctrip_workflow.login(ctrip_account, input_callback=input_callback)
            if not login_result:
                return WorkflowResult(
                    result_type=WorkflowResultType.CTRIP_LOGIN_FAILED,
                    message="携程登录失败"
                )
            logger.info(f"[ENV-{env_id}] ✅ 携程登录成功")
        else:
            logger.info(f"[ENV-{env_id}] ✅ 携程已登录，跳过")
        
        # === Step 2: 劳保登录 ===
        logger.info(f"[ENV-{env_id}] === 步骤2: 劳保登录 ===")
        labor_workflow = LaborLoginWorkflow(page)
        
        if not await labor_workflow.ensure_logged_in(labor_account):
            return WorkflowResult(
                result_type=WorkflowResultType.LABOR_LOGIN_FAILED,
                message=f"劳保登录失败: {labor_account.phone}"
            )
        logger.info(f"[ENV-{env_id}] ✅ 劳保登录成功: {labor_account.phone}")
        
        # === Step 3: 执行任务循环 ===
        logger.info(f"[ENV-{env_id}] === 步骤3: 开始自动化做题 ===")
        runner = LaborWorkflowRunner(page)
        await runner.run_auto_tasks(labor_account, ctrip_account)
        
        completed = runner.stats.get("completed", 0)
        
        logger.info(f"[ENV-{env_id}] ✅ 工作流完成，共完成 {completed} 个任务")
        
        return WorkflowResult(
            result_type=WorkflowResultType.SUCCESS if completed > 0 else WorkflowResultType.NO_TASK,
            tasks_completed=completed,
            message=f"完成 {completed} 个任务"
        )

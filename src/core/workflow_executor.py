"""统一环境工作流程执行器。

封装完整的 登录 -> 领题 -> 做题 -> 交题 流程，
供手动启动和自动调度器共同调用。

职责：
1. 加载携程账号数据
2. 打开浏览器
3. 携程登录（判断接码类型）
4. 动态获取并锁定劳保账号
5. 劳保登录 -> 任务循环
6. 释放劳保账号锁定
7. 关闭浏览器
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
from src.utils.async_utils import run_blocking
from src.utils.logger import logger
from src.utils.storage import (
    CtripAccountRepository,
    EnvironmentRepository,
    LaborAccountRepository,
)


class WorkflowResultType(Enum):
    """工作流执行结果类型。"""

    SUCCESS = auto()
    CTRIP_LOGIN_FAILED = auto()
    LABOR_LOGIN_FAILED = auto()
    NO_TASK = auto()
    TASK_FAILED = auto()
    BROWSER_ERROR = auto()
    NETWORK_ERROR = auto()  # 网络连接失败
    MANUAL_SMS_AUTO_MODE = auto()  # 手动接码账号在自动模式下
    ACCOUNT_ERROR = auto()  # 账号数据无效
    NO_LABOR_ACCOUNT = auto()  # 无可用劳保账号
    API_FIRST_LOGIN = auto()  # API账号首次登录，需要冷却期
    ERROR = auto()


@dataclass
class WorkflowResult:
    """工作流执行结果。"""

    result_type: WorkflowResultType
    tasks_completed: int = 0
    message: str = ""
    ctrip_blacklisted: bool = False
    labor_account_id: int | None = None  # 本次使用的劳保账号ID


async def execute_environment_workflow(
    environment: Environment,
    input_callback: Callable | None = None,
) -> WorkflowResult:
    """执行环境的完整工作流程。

    流程: 加载携程账号 → 打开浏览器 → 携程登录 → 获取劳保账号 → 劳保登录 → 任务循环

    Args:
        environment: 目标环境（仅需包含 ctrip_account_id，劳保账号动态分配）
        input_callback: 输入回调（用于手动模式的验证码等），None 表示自动模式

    Returns:
        WorkflowResult 包含执行结果
    """
    profile_id = environment.browser_profile_id
    env_id = environment.id
    env_repo = EnvironmentRepository()
    labor_repo = LaborAccountRepository()
    is_auto_mode = input_callback is None

    # 动态分配的劳保账号，用于 finally 释放
    locked_labor_id: int | None = None

    logger.info(
        f"[ENV-{env_id}] 开始执行工作流 (模式: {'自动' if is_auto_mode else '手动'})"
    )

    try:
        # === Step 0: 每日启动次数检查 ===
        if env_id:
            # BLOCKING DB -> Wrapped
            can_open = await run_blocking(env_repo.check_and_increment_daily_usage, env_id)
            if not can_open:
                logger.warning(f"[ENV-{env_id}] ❌ 今日启动次数已达上限")
                return WorkflowResult(
                    result_type=WorkflowResultType.ERROR, message="今日启动次数已达上限"
                )

        # === Step 1: 加载携程账号 ===
        # BLOCKING DB -> Wrapped
        ctrip_account = await run_blocking(_load_ctrip_account, environment.ctrip_account_id)

        if not ctrip_account:
            return WorkflowResult(
                result_type=WorkflowResultType.ACCOUNT_ERROR, message="携程账号数据无效"
            )

        logger.info(f"  携程账号: {ctrip_account.phone_number}")

        # === Step 2: 打开浏览器 ===
        logger.info(f"[ENV-{env_id}] 正在打开浏览器...")
        # BLOCKING NETWORK -> Async (aiohttp)
        conn_info = await BrowserAPI.open_browser_async(profile_id)
        
        ws_endpoint = conn_info.get("ws_endpoint")
        http_endpoint = conn_info.get("http_endpoint")

        if not ws_endpoint:
            return WorkflowResult(
                result_type=WorkflowResultType.BROWSER_ERROR,
                message="无法获取浏览器 WebSocket 端点",
            )

        # 更新环境连接信息
        if env_id:
            # BLOCKING DB -> Wrapped
            await run_blocking(
                env_repo.update_connection_info, env_id, ws_endpoint, http_endpoint, None
            )

        # === Step 3: 执行自动化（包括动态获取劳保账号）===
        result, locked_labor_id = await _run_automation(
            ws_endpoint=ws_endpoint,
            ctrip_account=ctrip_account,
            input_callback=input_callback,
            env_id=env_id,
            is_auto_mode=is_auto_mode,
        )

        # 更新统计
        if result.tasks_completed > 0 and locked_labor_id:
            # BLOCKING DB -> Wrapped
            await run_blocking(
                labor_repo.update_stats, locked_labor_id, completed=result.tasks_completed
            )

        return result

    except Exception as e:
        logger.error(f"[ENV-{env_id}] 工作流执行异常: {e}")
        return WorkflowResult(result_type=WorkflowResultType.ERROR, message=str(e))
    finally:
        # === Step 4: 释放劳保账号锁定 ===
        if locked_labor_id and env_id:
            # BLOCKING DB -> Wrapped
            await run_blocking(labor_repo.unlock_account, locked_labor_id, env_id)
            logger.info(f"🔓 已释放劳保账号: ID-{locked_labor_id}")

        # === Step 5: 关闭浏览器 ===
        try:
            logger.info(f"[ENV-{env_id}] 正在关闭浏览器...")
            # BLOCKING NETWORK -> Async (aiohttp)
            await BrowserAPI.close_browser_async(profile_id)
        except Exception as e:
            logger.warning(f"关闭浏览器失败: {e}")

        # === Step 6: 清理环境状态 ===
        if env_id:
            # 清理连接信息
            # BLOCKING DB -> Wrapped (Combined or separate calls)
            # Actually update_connection_info and update_status are fast, but let's be consistent
            await run_blocking(env_repo.update_connection_info, env_id, None, None, None)
            
            # 确保状态设为 idle（无论是正常完成还是异常退出）
            await run_blocking(env_repo.update_status, env_id, "idle")
            logger.debug(f"[ENV-{env_id}] 环境状态已设为 idle")


def _load_ctrip_account(account_id: int | None) -> CtripAccount | None:
    """从数据库加载携程账号。"""
    if not account_id:
        return None
    try:
        repo = CtripAccountRepository()
        acc_data = repo.get_by_id(account_id)
        if acc_data:
            return CtripAccount(**acc_data)
    except Exception as e:
        logger.error(f"加载携程账号失败: {e}")
    return None


def _acquire_labor_account(
    env_id: int | None,
) -> tuple[LaborAccount | None, int | None]:
    """获取并锁定一个可用的劳保账号。

    Returns:
        (劳保账号对象, 锁定的账号ID) 或 (None, None)
    """
    repo = LaborAccountRepository()

    # 获取未锁定的账号（按绑定次数排序）
    accounts = repo.get_all(limit=50)

    for acc_data in accounts:
        acc_id = acc_data.get("id")
        if not acc_id:
            continue

        # 尝试锁定
        if repo.lock_account(acc_id, env_id or 0):
            logger.info(f"🔒 已锁定劳保账号: {acc_data.get('phone')} (ID-{acc_id})")
            return LaborAccount.from_dict(acc_data), acc_id

    return None, None


async def _handle_ctrip_login_success(
    env_id: int | None,
    ctrip_account: CtripAccount,
) -> bool:
    """处理携程登录成功后的记录。

    Args:
        env_id: 环境 ID
        ctrip_account: 携程账号

    Returns:
        True 如果是首次登录，False 如果不是
    """
    env_repo = EnvironmentRepository()
    ctrip_repo = CtripAccountRepository()

    is_first_login = False

    # 记录环境的携程登录时间
    if env_id:
        is_first_login = env_repo.update_ctrip_login_at(env_id)

    # 如果是 API 账号且首次登录，记录注册时间
    if is_first_login and ctrip_account.account_type == "api" and ctrip_account.id:
        ctrip_repo.set_registered_at(ctrip_account.id)
        logger.info(f"📝 记录 API 账号注册时间: ID-{ctrip_account.id}")

    return is_first_login


async def _run_automation(
    ws_endpoint: str,
    ctrip_account: CtripAccount,
    input_callback: Callable | None,
    env_id: int | None,
    is_auto_mode: bool,
) -> tuple[WorkflowResult, int | None]:
    """执行自动化流程。

    Returns:
        (WorkflowResult, locked_labor_id)
    """
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(ws_endpoint)
        context = (
            browser.contexts[0] if browser.contexts else await browser.new_context()
        )
        page = context.pages[0] if context.pages else await context.new_page()

        page.set_default_timeout(30000)
        page.set_default_navigation_timeout(60000)
        
        # 检查黑号

        # 获取注册时间

        # === Step 0: 网络连通性检测 ===
        logger.info(f"[ENV-{env_id}] === 步骤0: 网络检测 ===")
        from src.utils.network_checker import NetworkChecker

        check_result = await NetworkChecker.check_connectivity(
            page, timeout_ms=20000, retries=2
        )

        if not check_result.success:
            logger.error(
                f"[ENV-{env_id}] ❌ 网络检测失败: {check_result.error_message}"
            )
            return WorkflowResult(
                result_type=WorkflowResultType.NETWORK_ERROR,
                message=check_result.error_message,
            ), None

        logger.info(f"[ENV-{env_id}] ✅ 网络正常 (延迟: {check_result.latency_ms}ms)")

        # === Step 1: 携程登录 ===
        logger.info(f"[ENV-{env_id}] === 步骤1: 携程登录 ===")
        ctrip_workflow = CtripLoginWorkflow(page)

        # 网络检测已导航到携程，检查是否需要重新加载
        current_url = page.url
        if "ctrip.com" not in current_url:
            try:
                await page.goto(
                    "https://www.ctrip.com/",
                    wait_until="domcontentloaded",
                    timeout=30000,
                )
            except Exception as e:
                logger.warning(f"导航到携程首页超时: {e}")

        await asyncio.sleep(1)

        if not await ctrip_workflow.is_logged_in():
            # 🔴 关键逻辑：检查接码类型
            sms_type = ctrip_account.sms_verify_type or "manual"

            if is_auto_mode and sms_type == "manual":
                # 自动模式 + 手动接码账号 = 无法登录，终止环境
                logger.warning(
                    f"[ENV-{env_id}] ❌ 手动接码账号不支持自动模式，终止环境"
                )
                return WorkflowResult(
                    result_type=WorkflowResultType.MANUAL_SMS_AUTO_MODE,
                    message="手动接码账号不支持自动模式，请使用手动启动",
                ), None

            # 执行登录
            login_result = await ctrip_workflow.login(
                ctrip_account, input_callback=input_callback
            )
            if not login_result:
                return WorkflowResult(
                    result_type=WorkflowResultType.CTRIP_LOGIN_FAILED,
                    message="携程登录失败",
                ), None
            logger.info(f"[ENV-{env_id}] ✅ 携程登录成功")

            # 🔴 关键逻辑：记录登录时间并检查是否需要冷却期
            # BLOCKING DB -> Wrapped
            is_first_login = await run_blocking(
                _handle_ctrip_login_success,
                env_id=env_id,
                ctrip_account=ctrip_account,
            )

            if is_first_login and ctrip_account.account_type == "api":
                # API 账号首次登录，需要冷却期，立即终止
                logger.warning(
                    f"[ENV-{env_id}] 🕐 API账号首次登录，需要2天冷却期，终止环境"
                )
                return WorkflowResult(
                    result_type=WorkflowResultType.API_FIRST_LOGIN,
                    message="API账号首次登录，需要2天冷却期",
                ), None
        else:
            logger.info(f"[ENV-{env_id}] ✅ 携程已登录，跳过")

        # === Step 2: 动态获取劳保账号 ===
        logger.info(f"[ENV-{env_id}] === 步骤2: 获取劳保账号 ===")
        # BLOCKING DB (Complex) -> Wrapped whole function
        labor_account, locked_labor_id = await run_blocking(_acquire_labor_account, env_id)

        if not labor_account:
            return WorkflowResult(
                result_type=WorkflowResultType.NO_LABOR_ACCOUNT,
                message="无可用的劳保账号",
            ), None

        logger.info(f"  劳保账号: {labor_account.phone}")

        # === Step 3: 劳保登录 ===
        logger.info(f"[ENV-{env_id}] === 步骤3: 劳保登录 ===")
        labor_workflow = LaborLoginWorkflow(page)

        try:
            if not await labor_workflow.ensure_logged_in(labor_account):
                return WorkflowResult(
                    result_type=WorkflowResultType.LABOR_LOGIN_FAILED,
                    message=f"劳保登录失败: {labor_account.phone}",
                    labor_account_id=locked_labor_id,
                ), locked_labor_id
            logger.info(f"[ENV-{env_id}] ✅ 劳保登录成功: {labor_account.phone}")

            # === Step 4: 执行任务循环 ===
            logger.info(f"[ENV-{env_id}] === 步骤4: 开始自动化做题 ===")
            runner = LaborWorkflowRunner(page)
            await runner.run_auto_tasks(labor_account, ctrip_account)

            completed = runner.stats.get("completed", 0)

            logger.info(f"[ENV-{env_id}] ✅ 工作流完成，共完成 {completed} 个任务")

            return WorkflowResult(
                result_type=WorkflowResultType.SUCCESS
                if completed > 0
                else WorkflowResultType.NO_TASK,
                tasks_completed=completed,
                message=f"完成 {completed} 个任务",
                labor_account_id=locked_labor_id,
            ), locked_labor_id
        except Exception as e:
            logger.error(f"[ENV-{env_id}] 自动化执行过程中出现异常: {e}")
            return WorkflowResult(
                result_type=WorkflowResultType.ERROR,
                message=f"自动化异常: {e}",
                labor_account_id=locked_labor_id,
            ), locked_labor_id

"""Labor workflow runner module.

Orchestrates the complete labor task workflow:
1. Login to Labor platform
2. Claim a task
3. Navigate to Ctrip and capture data
4. Submit results back to Labor platform
"""

import asyncio

from playwright.async_api import BrowserContext, Page

from src.automation.workflows.ctrip_search import CtripSearchWorkflow
from src.automation.workflows.labor_claim_task import LaborClaimTaskWorkflow
from src.automation.workflows.labor_login import LaborLoginWorkflow
from src.automation.workflows.labor_submit import LaborSubmitWorkflow
from src.core.models.ctrip_account import CtripAccount
from src.core.models.labor_account import LaborAccount
from src.core.models.labor_task import LaborTask, TaskState
from src.utils.logger import logger
from src.utils.storage import LaborAccountRepository


class LaborWorkflowRunner:
    """劳保平台完整工作流运行器。

    管理整个做题流程：登录 → 领题 → 采集 → 提交。
    支持单次执行和循环执行模式。
    """

    def __init__(self, page: Page):
        """初始化工作流运行器。

        Args:
            page: Playwright Page 对象
        """
        self.page = page
        self.context: BrowserContext = page.context

        # 初始化各工作流模块
        self.login_workflow = LaborLoginWorkflow(page)
        self.claim_workflow = LaborClaimTaskWorkflow(page)
        self.search_workflow = CtripSearchWorkflow(page)
        self.submit_workflow = LaborSubmitWorkflow(page)
        self.labor_repo = LaborAccountRepository()

        # 记录当前使用的劳保账号
        self.current_labor_account: LaborAccount | None = None

        # 运行状态
        self._running = False
        self._stop_requested = False

        # 统计数据
        self.stats = {
            "completed": 0,
            "failed": 0,
            "total_time": 0.0,
        }

    # ==================== 携程页面管理 ====================

    async def _open_ctrip_page(self, task: LaborTask) -> Page | None:
        """打开携程酒店页面（新标签页）。

        Args:
            task: 任务信息

        Returns:
            携程页面对象，失败返回 None
        """
        try:
            url = task.build_ctrip_url()
            if not url:
                logger.error("无法构建携程URL")
                return None

            logger.info(f"打开携程页面: {url}")
            ctrip_page = await self.context.new_page()

            # 为新页面创建搜索工作流
            search_workflow = CtripSearchWorkflow(ctrip_page)

            # 设置路由拦截（在导航前）
            await search_workflow._setup_route_handler()

            # 导航到酒店页面
            await ctrip_page.goto(url, wait_until="domcontentloaded")

            return ctrip_page

        except Exception as e:
            logger.error(f"打开携程页面失败: {e}")
            return None

    async def _close_ctrip_page(self, ctrip_page: Page):
        """关闭携程页面。"""
        try:
            if ctrip_page and not ctrip_page.is_closed():
                await ctrip_page.close()
                logger.debug("携程页面已关闭")
        except Exception as e:
            logger.debug(f"关闭携程页面失败: {e}")

    async def _switch_to_labor_page(self):
        """切换回劳保平台页面。"""
        try:
            # 将劳保页面置于前台
            await self.page.bring_to_front()
        except Exception as e:
            logger.debug(f"切换页面失败: {e}")

    async def _close_environment(self):
        """关闭当前的浏览器上下文和页面。"""
        try:
            logger.info("正在关闭浏览器环境...")
            if self.page and not self.page.is_closed():
                await self.page.close()

            if self.context:
                await self.context.close()

            logger.info("浏览器环境已关闭")
        except Exception as e:
            logger.error(f"关闭环境失败: {e}")

    # ==================== 核心工作流方法 ====================

    async def run_auto_tasks(
        self,
        labor_account: LaborAccount,
        ctrip_account: CtripAccount,
    ):
        """执行自动化做题任务。

        读取配置并循环执行：领题 -> 搜索 -> 提交。
        """
        max_tasks = ctrip_account.consecutive_task_count
        interval_max = ctrip_account.task_interval_max

        logger.info(
            f"🚀 开始自动化做题任务 (目标: {max_tasks}个, 最大间隔: {interval_max}分)"
        )

        self._running = True
        self._stop_requested = False
        self.current_labor_account = labor_account
        self.stats["completed"] = 0  # 重置单次运行统计
        task_count = 0

        try:
            while not self._stop_requested and task_count < max_tasks:
                # 0. 确保已登录（针对切号后的首个任务）
                if not await self.login_workflow.ensure_logged_in(
                    self.current_labor_account
                ):
                    logger.error(
                        f"劳保账号 {self.current_labor_account.phone} 登录失败"
                    )
                    break

                # 1. 领题 (使用带重试机制的方法)
                phone = self.current_labor_account.phone
                logger.info(f"--- 执行第 {task_count + 1}/{max_tasks} 个任务 (账号: {phone}) ---")
                task = await self.claim_workflow.claim_task(
                    max_attempts=6, wait_seconds=30
                )

                if not task.is_complete:
                    if task.state == TaskState.NO_TASK:
                        logger.warning("连续6次尝试均无法领取任务，关闭环境")
                        await self._close_environment()
                        break
                    else:
                        logger.warning(f"领题异常，状态: {task.state}，结束流程")
                        break

                # 2. 携程搜索与采集
                logger.info(f"采集目标: {task.hotel_name}")
                hotel_data = await self.search_workflow.search_and_capture(task)

                # 3. 提交结果
                # hotel_data 为 None 时 submit_result 会尝试提交“搜索不到”
                if await self.submit_workflow.submit_result(hotel_data):
                    # 同步到数据库
                    if self.current_labor_account and self.current_labor_account.id:
                        try:
                            self.labor_repo.update_stats(
                                id=self.current_labor_account.id, completed=1
                            )
                        except Exception as db_e:
                            logger.warning(f"更新数据库统计失败: {db_e}")

                    task_count += 1
                else:
                    logger.warning("任务提交失败，跳过本次计数")
                self.stats["completed"] = task_count

                if task_count < max_tasks:
                    import random

                    wait_mins = random.uniform(1, interval_max)
                    logger.info(f"☕️ 任务完成，随机等待 {wait_mins:.1f} 分钟后继续...")
                    for _ in range(int(wait_mins * 60)):
                        if self._stop_requested:
                            break
                        await asyncio.sleep(1)

            logger.info(f"✅ 自动化流程执行完毕，共完成 {task_count} 个任务")

        except Exception:
            logger.error("自动化执行异常")
        finally:
            self._running = False
            self._log_stats()

    def request_stop(self):
        """请求停止连续执行。"""
        self._stop_requested = True
        logger.info("已请求停止做题")

    @property
    def is_running(self) -> bool:
        """检查是否正在运行。"""
        return self._running

    def _log_stats(self):
        """输出统计信息。"""
        total = self.stats["completed"] + self.stats["failed"]
        avg_time = (
            (self.stats["total_time"] / self.stats["completed"])
            if self.stats["completed"] > 0
            else 0
        )

        logger.info("===== 做题统计 =====")
        logger.info(f"完成: {self.stats['completed']}")
        logger.info(f"失败: {self.stats['failed']}")
        logger.info(f"总计: {total}")
        logger.info(f"平均耗时: {avg_time:.1f}秒")

    def reset_stats(self):
        """重置统计数据。"""
        self.stats = {
            "completed": 0,
            "failed": 0,
            "total_time": 0.0,
        }

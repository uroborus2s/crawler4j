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
from src.utils.storage import (
    CtripAccountRepository,
    EnvironmentRepository,
    LaborAccountRepository,
)


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
        env_id: int | None = None,
    ):
        """执行自动化做题任务。

        读取配置并循环执行：领题 -> 搜索 -> 提交。
        支持搜索失败时废弃题目并重新领题，以及账号被封时的处理。
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

                # 2.5 检查账号被封
                if self.search_workflow.is_account_blacklisted():
                    logger.error("🚫 携程账号被封，停止任务并处理...")
                    await self._handle_account_blacklisted(ctrip_account, env_id)
                    break  # 退出主循环

                # 3. 根据搜索结果决定处理方式
                submit_success = False

                if hotel_data is None:
                    # 完全搜索失败 -> 废弃题目并重新领题
                    logger.warning("❌ 搜索完全失败，执行废弃流程...")
                    if await self.claim_workflow.discard_task(reason_text="携程搜索失败"):
                        logger.info("✅ 废弃成功，继续领取下一题")
                        # 更新废弃统计
                        if self.current_labor_account and self.current_labor_account.id:
                            try:
                                self.labor_repo.update_stats(
                                    id=self.current_labor_account.id, discarded=1
                                )
                            except Exception as db_e:
                                logger.warning(f"更新废弃统计失败: {db_e}")
                        continue  # 跳过本次提交，直接进入下一轮循环
                    else:
                        logger.error("废弃失败，尝试继续...")

                elif hotel_data == "搜索不到":
                    # URL 不匹配详情页 -> 提交"搜索不到"
                    logger.info("📝 提交搜索不到结果...")
                    submit_success = await self.submit_workflow.submit_not_found()
                else:
                    # 正常数据 -> 提交结果
                    submit_success = await self.submit_workflow.submit_result(hotel_data)

                if submit_success:
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

    async def _handle_account_blacklisted(
        self, ctrip_account: CtripAccount, env_id: int | None
    ):
        """处理携程账号被封。

        1. 不提交当前劳保答案
        2. 将携程账号状态设为 blacklisted
        3. 将环境状态设为 error（不删除环境）
        4. 关闭浏览器会话
        5. 记录日志
        """
        try:
            logger.warning(f"携程账号 {ctrip_account.phone_number} 被封，开始处理...")

            # 更新携程账号状态为 blacklisted
            ctrip_repo = CtripAccountRepository()
            if ctrip_account.id:
                ctrip_repo.update_status(ctrip_account.id, "blacklisted")
                logger.info(f"携程账号 ID-{ctrip_account.id} 已标记为 blacklisted")

            # 更新环境状态为 error（不删除环境）
            if env_id:
                env_repo = EnvironmentRepository()
                env_repo.update_status(env_id, "error")
                logger.info(f"环境 ENV-{env_id} 已标记为 error")

            logger.info("✅ 账号被封处理完成")

        except Exception as e:
            logger.error(f"处理账号被封失败: {e}")
        finally:
            # 关闭浏览器会话
            await self._close_environment()


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

"""Labor workflow runner module.

Orchestrates the complete labor task workflow:
1. Login to Labor platform
2. Claim a task
3. Navigate to Ctrip and capture data
4. Submit results back to Labor platform
"""

import asyncio
from typing import List, Optional

from playwright.async_api import BrowserContext, Page

from src.automation.workflows.ctrip_search import CtripSearchWorkflow
from src.automation.workflows.labor_claim_task import LaborClaimTaskWorkflow
from src.automation.workflows.labor_login import LaborLoginWorkflow
from src.automation.workflows.labor_submit import LaborSubmitWorkflow
from src.core.models.labor_account import LaborAccount
from src.core.models.labor_task import LaborTask, TaskState
from src.utils.logger import logger


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
    
    # ==================== 核心工作流方法 ====================
    
    async def run_single_cycle(
        self,
        labor_account: LaborAccount,
        preferred_cities: List[str] | None = None,
    ) -> bool:
        """执行一次完整的做题循环。
        
        流程：
        1. 确保劳保平台已登录
        2. 领取任务
        3. 打开携程页面采集数据
        4. 返回劳保平台提交结果
        
        Args:
            labor_account: 劳保账号信息
            preferred_cities: 优先选择的城市列表
            
        Returns:
            True if cycle completed successfully.
        """
        logger.info("===== 开始做题循环 =====")
        start_time = asyncio.get_event_loop().time()
        
        ctrip_page: Page | None = None
        
        try:
            # 1. 确保登录
            logger.info("[Step 1/4] 检查登录状态...")
            if not await self.login_workflow.ensure_logged_in(labor_account):
                logger.error("劳保平台登录失败")
                return False
            
            # 导航到做题页面
            await self.login_workflow.navigate_to_task_page()
            await asyncio.sleep(2)
            
            # 2. 领取任务
            logger.info("[Step 2/4] 领取任务...")
            task = await self.claim_workflow.claim_task(
                max_attempts=3,
                preferred_cities=preferred_cities
            )
            
            if not task.is_complete:
                logger.warning(f"任务领取失败，状态: {task.state.name}")
                self.stats["failed"] += 1
                return False
            
            logger.info(f"成功领取任务: {task}")
            
            # 3. 采集携程数据
            logger.info("[Step 3/4] 采集携程数据...")
            
            # 打开新页面进行采集
            ctrip_page = await self._open_ctrip_page(task)
            if not ctrip_page:
                logger.error("打开携程页面失败")
                self.stats["failed"] += 1
                return False
            
            # 使用新页面的搜索工作流
            ctrip_search = CtripSearchWorkflow(ctrip_page)
            hotel_data = await ctrip_search.search_hotel(task)
            
            if not hotel_data:
                logger.error("携程数据采集失败")
                # 关闭携程页面
                await self._close_ctrip_page(ctrip_page)
                self.stats["failed"] += 1
                return False
            
            logger.info(f"成功采集数据，键数量: {len(hotel_data)}")
            
            # 关闭携程页面
            await self._close_ctrip_page(ctrip_page)
            ctrip_page = None
            
            # 切换回劳保页面
            await self._switch_to_labor_page()
            await asyncio.sleep(1.5)
            
            # 4. 提交结果
            logger.info("[Step 4/4] 提交结果...")
            if await self.submit_workflow.submit_result(hotel_data):
                elapsed = asyncio.get_event_loop().time() - start_time
                logger.info(f"✅ 做题循环完成，用时: {elapsed:.1f}秒")
                
                self.stats["completed"] += 1
                self.stats["total_time"] += elapsed
                return True
            else:
                logger.error("结果提交失败")
                self.stats["failed"] += 1
                return False
            
        except Exception as e:
            logger.error(f"做题循环异常: {e}")
            self.stats["failed"] += 1
            return False
        
        finally:
            # 确保携程页面已关闭
            if ctrip_page:
                await self._close_ctrip_page(ctrip_page)
    
    async def run_continuous(
        self,
        labor_account: LaborAccount,
        max_tasks: int = 0,
        interval_seconds: float = 3.0,
        preferred_cities: List[str] | None = None,
    ):
        """连续执行做题循环。
        
        Args:
            labor_account: 劳保账号信息
            max_tasks: 最大任务数（0表示无限制）
            interval_seconds: 任务间隔时间（秒）
            preferred_cities: 优先城市列表
        """
        logger.info(f"开始连续做题模式（最大任务: {max_tasks or '无限'}）")
        
        self._running = True
        self._stop_requested = False
        task_count = 0
        
        try:
            while not self._stop_requested:
                # 检查任务数限制
                if max_tasks > 0 and task_count >= max_tasks:
                    logger.info(f"已达到最大任务数 {max_tasks}，停止")
                    break
                
                # 执行一次循环
                success = await self.run_single_cycle(labor_account, preferred_cities)
                task_count += 1
                
                if not success:
                    logger.warning(f"任务 {task_count} 执行失败")
                
                # 间隔等待
                if not self._stop_requested:
                    logger.info(f"等待 {interval_seconds} 秒后继续...")
                    await asyncio.sleep(interval_seconds)
                    
        except Exception as e:
            logger.error(f"连续执行异常: {e}")
        
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
        avg_time = (self.stats["total_time"] / self.stats["completed"]) if self.stats["completed"] > 0 else 0
        
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

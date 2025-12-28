"""Ctrip search workflow module.

Handles navigating to Ctrip hotel pages and capturing the getHotelRoomListInland API response.
Uses Playwright route interception for reliable data capture.
"""

import asyncio
import json
import random
from typing import Optional

from playwright.async_api import Page, Response, Route

from src.automation.workflows.base import BaseWorkflow
from src.core.models.labor_task import LaborTask
from src.utils.logger import logger


class CtripSearchWorkflow(BaseWorkflow):
    """Workflow for searching on Ctrip and capturing hotel room data.
    
    使用 Playwright 路由拦截功能捕获 getHotelRoomListInland API 响应，
    同时模拟人工浏览行为避免被识别为爬虫。
    """
    
    # 目标 API 关键词
    TARGET_API_KEYWORD = "getHotelRoomListInland"
    
    # 拦截 URL 模式
    INTERCEPT_PATTERN = "**/*getHotelRoomListInland*"
    
    def __init__(self, page: Page):
        super().__init__(page)
        self.captured_data: dict | None = None
        self._route_handler_set = False
        self._last_mouse_pos = (0, 0)
    
    async def _setup_route_handler(self):
        """设置路由拦截器，捕获酒店房型 API 响应。
        
        使用 Playwright 的 route() API 拦截特定请求，
        获取响应数据后继续原始请求流程。
        """
        if self._route_handler_set:
            return
        
        async def handle_route(route: Route):
            """拦截并记录目标 API 响应。"""
            try:
                # 获取原始响应
                response = await route.fetch()
                body = await response.body()
                
                # 检查是否是目标 API
                if self.TARGET_API_KEYWORD in route.request.url:
                    try:
                        self.captured_data = json.loads(body.decode('utf-8'))
                        logger.info(f"✅ 捕获到酒店房型数据，大小: {len(body)} bytes")
                    except json.JSONDecodeError as e:
                        logger.warning(f"API 响应 JSON 解析失败: {e}")
                
                # 继续返回原始响应（确保页面正常加载）
                await route.fulfill(response=response)
                
            except Exception as e:
                logger.error(f"路由处理异常: {e}")
                # 发生错误时继续原始请求
                await route.continue_()
        
        # 设置路由拦截
        await self.page.route(self.INTERCEPT_PATTERN, handle_route)
        self._route_handler_set = True
        logger.debug("已设置 API 响应拦截器")
    
    async def _remove_route_handler(self):
        """移除路由拦截器。"""
        if self._route_handler_set:
            try:
                await self.page.unroute(self.INTERCEPT_PATTERN)
                self._route_handler_set = False
            except Exception as e:
                logger.debug(f"移除路由处理器失败: {e}")
    
    # ==================== 人工行为模拟方法 ====================
    # 复用自 ctrip_login.py 中已验证的方法
    
    async def _human_move(self, end_x: float, end_y: float, steps: int = 15):
        """使用贝塞尔曲线模拟人类鼠标移动。"""
        start_x, start_y = self._last_mouse_pos
        
        # 贝塞尔曲线控制点（随机化）
        cp1_x = start_x + (end_x - start_x) * random.uniform(0.3, 0.7) + random.uniform(-30, 30)
        cp1_y = start_y + (end_y - start_y) * random.uniform(0.3, 0.7) + random.uniform(-30, 30)
        
        path = []
        for i in range(steps + 1):
            t = i / steps
            # 二次贝塞尔曲线
            x = (1 - t)**2 * start_x + 2 * (1 - t) * t * cp1_x + t**2 * end_x
            y = (1 - t)**2 * start_y + 2 * (1 - t) * t * cp1_y + t**2 * end_y
            path.append((x, y))
        
        for x, y in path:
            await self.page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.005, 0.015))
        
        self._last_mouse_pos = (end_x, end_y)
    
    async def _human_scroll(self, delta_y: int = 300, smooth: bool = True):
        """模拟人类滚动行为。
        
        Args:
            delta_y: 滚动距离（正数向下）
            smooth: 是否平滑滚动
        """
        if smooth:
            # 分多次滚动，模拟真实滚动
            steps = random.randint(3, 6)
            step_delta = delta_y // steps
            
            for _ in range(steps):
                await self.page.mouse.wheel(0, step_delta + random.randint(-20, 20))
                await asyncio.sleep(random.uniform(0.05, 0.15))
        else:
            await self.page.mouse.wheel(0, delta_y)
        
        await asyncio.sleep(random.uniform(0.3, 0.8))
    
    async def _random_mouse_movement(self):
        """随机鼠标移动，模拟用户浏览。"""
        viewport = self.page.viewport_size
        if viewport:
            target_x = random.uniform(100, viewport['width'] - 100)
            target_y = random.uniform(100, viewport['height'] - 100)
            await self._human_move(target_x, target_y)
    
    async def _simulate_human_browsing(self, duration: float = 5.0):
        """模拟人类浏览行为。
        
        包括：随机滚动、鼠标移动、短暂停顿等。
        
        Args:
            duration: 模拟浏览的总时长（秒）
        """
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < duration:
            action = random.choice(['scroll', 'move', 'wait'])
            
            if action == 'scroll':
                # 向下滚动
                await self._human_scroll(
                    delta_y=random.randint(150, 400),
                    smooth=True
                )
            elif action == 'move':
                # 随机移动鼠标
                await self._random_mouse_movement()
            else:
                # 短暂等待（模拟阅读）
                await asyncio.sleep(random.uniform(0.5, 1.5))
            
            await asyncio.sleep(random.uniform(0.3, 0.8))
        
        logger.debug(f"人工浏览模拟完成，持续 {duration:.1f} 秒")
    
    # ==================== 核心搜索方法 ====================
    
    def _build_hotel_url(self, task: LaborTask) -> str:
        """构建携程酒店详情页 URL。
        
        Args:
            task: 任务信息
            
        Returns:
            携程酒店详情页完整 URL
        """
        return task.build_ctrip_url()
    
    async def _wait_for_data_capture(self, timeout: float = 20.0) -> bool:
        """等待 API 数据捕获完成。
        
        Args:
            timeout: 最大等待时间（秒）
            
        Returns:
            True if data captured within timeout.
        """
        start_time = asyncio.get_event_loop().time()
        check_interval = 0.5
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            if self.captured_data is not None:
                return True
            await asyncio.sleep(check_interval)
        
        return False
    
    async def search_hotel(self, task: LaborTask) -> dict | None:
        """执行酒店搜索并获取房型数据。
        
        完整流程：
        1. 设置 API 响应拦截器
        2. 导航到酒店详情页
        3. 模拟人工浏览行为（触发 API 请求）
        4. 等待并返回捕获的数据
        
        Args:
            task: 包含酒店信息的任务对象
            
        Returns:
            捕获的 API 响应数据（JSON 对象），失败返回 None
        """
        if not task.hotel_id:
            logger.error("任务缺少酒店ID，无法执行搜索")
            return None
        
        # 重置捕获数据
        self.captured_data = None
        
        try:
            # 1. 设置路由拦截
            await self._setup_route_handler()
            
            # 2. 构建并导航到酒店页面
            url = self._build_hotel_url(task)
            logger.info(f"导航到携程酒店页面: {url}")
            
            await self.page.goto(url, wait_until="domcontentloaded")
            
            # 3. 等待页面基本加载
            await asyncio.sleep(random.uniform(1.5, 2.5))
            
            # 4. 检查是否是 404 页面
            if await self._is_404_page():
                logger.warning("酒店页面返回 404")
                return {"error": "404", "message": "Hotel not found"}
            
            # 5. 模拟人工浏览行为（这会触发 API 请求）
            logger.info("模拟人工浏览行为...")
            await self._simulate_human_browsing(duration=random.uniform(4, 7))
            
            # 6. 等待数据捕获
            if await self._wait_for_data_capture(timeout=15):
                logger.info("✅ 酒店数据采集成功")
                return self.captured_data
            else:
                logger.warning("等待 API 响应超时")
                
                # 尝试再次滚动触发
                logger.info("尝试再次滚动触发 API 请求...")
                await self._human_scroll(delta_y=500)
                await asyncio.sleep(3)
                
                if self.captured_data:
                    return self.captured_data
                
                return None
            
        except Exception as e:
            logger.error(f"酒店搜索异常: {e}")
            return None
        
        finally:
            # 清理路由处理器（可选，保留可以复用）
            pass
    
    async def _is_404_page(self) -> bool:
        """检查是否是 404 页面。
        
        基于 injected.js 第 119-133 行 checkPageStatus() 分析。
        """
        try:
            # 检查携程特定的 404 页面结构
            bg_div = await self.page.query_selector("div.bg")
            if bg_div:
                tower = await bg_div.query_selector("div.tower")
                beam = await bg_div.query_selector("div.beam")
                stars = await bg_div.query_selector_all("div[class^='star']")
                
                if tower and beam and len(stars) >= 4:
                    return True
            
            return False
            
        except Exception:
            return False
    
    async def search(self, keyword: str) -> bool:
        """兼容旧接口的搜索方法。
        
        注意：此方法保留用于向后兼容，建议使用 search_hotel() 方法。
        
        Args:
            keyword: 搜索关键词（此方法中未使用）
            
        Returns:
            True（始终返回，实际结果通过 captured_data 获取）
        """
        logger.info(f"携程搜索（兼容接口）: {keyword}")
        
        # 创建临时任务对象
        # 注意：这是一个简化的兼容实现，实际使用应该调用 search_hotel()
        await self._simulate_human_browsing(duration=3)
        return True
    
    def get_captured_data(self) -> dict | None:
        """获取捕获的 API 响应数据。
        
        Returns:
            最后一次捕获的数据，如未捕获返回 None
        """
        return self.captured_data
    
    def clear_captured_data(self):
        """清除捕获的数据。"""
        self.captured_data = None

"""Ctrip search workflow module.

Handles navigating to Ctrip hotel pages and capturing the getHotelRoomListInland API response.
Uses Playwright route interception for reliable data capture.
"""

import asyncio
import json
import random
from typing import TYPE_CHECKING

from playwright.async_api import Page, Route

from src.automation.workflows.base import BaseWorkflow
from src.core.models.labor_task import LaborTask
from src.utils.hotel_matcher import HotelMatcher, HotelMatch
from src.utils.logger import logger

if TYPE_CHECKING:
    from src.automation.workflows.labor_claim_task import LaborClaimTaskWorkflow


class CtripSearchWorkflow(BaseWorkflow):
    """Workflow for searching on Ctrip and capturing hotel room data.

    使用 Playwright 路由拦截功能捕获 getHotelRoomListInland API 响应，
    同时模拟人工浏览行为避免被识别为爬虫。
    """

    # 目标 API 关键词
    TARGET_API_KEYWORD = "getHotelRoomListInland"

    # 拦截 URL 模式
    INTERCEPT_PATTERN = "**/*getHotelRoomListInland*"

    # 搜索 API 拦截模式 (支持两种 API 端点)
    # POST 方法: https://m.ctrip.com/restapi/soa2/30668/search
    # GET 方法: https://m.ctrip.com/restapi/soa2/26872/search
    SEARCH_API_PATTERN = "**/*restapi/soa2/*/search*"
    SEARCH_API_POST_KEYWORD = "restapi/soa2/30668/search"  # POST 方法
    SEARCH_API_GET_KEYWORD = "restapi/soa2/26872/search"   # GET 方法

    def __init__(self, page: Page, claim_workflow: "LaborClaimTaskWorkflow | None" = None):
        super().__init__(page)
        self.captured_data: dict | None = None
        self.search_result_data: dict | None = None  # 搜索 API 响应数据
        self.search_api_method: str | None = None    # 记录使用的 API 方法 (GET/POST)
        self._route_handler_set = False
        self._search_route_handler_set = False
        self._last_mouse_pos = (0, 0)
        self.account_blacklisted = False  # 账号被封标志位
        self.claim_workflow = claim_workflow  # 用于废弃题目

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
                        data = json.loads(body.decode("utf-8"))
                        self.captured_data = data

                        # 检测账号被封 (htlSpiderActionErrorCode: 203)
                        if isinstance(data, dict):
                            error_code = data.get("data", {}).get("htlSpiderActionErrorCode")
                            if error_code == 203:
                                logger.error("🚫 检测到 htlSpiderActionErrorCode: 203，携程账号被封！")
                                self.account_blacklisted = True
                            else:
                                logger.info(f"✅ 捕获到酒店房型数据，大小: {len(body)} bytes")
                        else:
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

    async def _setup_search_route_handler(self):
        """设置搜索 API 路由拦截器，用于验证搜索结果。

        拦截两种 API 端点：
        - POST: https://m.ctrip.com/restapi/soa2/30668/search
        - GET: https://m.ctrip.com/restapi/soa2/26872/search
        获取酒店列表数据用于名称匹配验证。
        """
        if self._search_route_handler_set:
            return

        async def handle_search_route(route: Route):
            """拦截并记录搜索 API 响应。"""
            try:
                request_url = route.request.url

                # 检查是否是目标搜索 API
                is_post_api = self.SEARCH_API_POST_KEYWORD in request_url
                is_get_api = self.SEARCH_API_GET_KEYWORD in request_url

                if not (is_post_api or is_get_api):
                    # 不是目标 API，直接放行
                    await route.continue_()
                    return

                response = await route.fetch()
                body = await response.body()

                try:
                    data = json.loads(body.decode("utf-8"))
                    self.search_result_data = data

                    # 记录使用的 API 方法
                    if is_post_api:
                        self.search_api_method = "POST"
                        logger.info(f"✅ 捕获到搜索API响应 (POST 30668)，大小: {len(body)} bytes")
                    else:
                        self.search_api_method = "GET"
                        logger.info(f"✅ 捕获到搜索API响应 (GET 26872)，大小: {len(body)} bytes")

                except json.JSONDecodeError as e:
                    logger.warning(f"搜索 API 响应 JSON 解析失败: {e}")

                await route.fulfill(response=response)

            except Exception as e:
                logger.error(f"搜索路由处理异常: {e}")
                await route.continue_()

        await self.page.route(self.SEARCH_API_PATTERN, handle_search_route)
        self._search_route_handler_set = True
        logger.debug("已设置搜索 API 响应拦截器 (支持 30668/POST 和 26872/GET)")

    async def _remove_search_route_handler(self):
        """移除搜索 API 路由拦截器。"""
        if self._search_route_handler_set:
            try:
                await self.page.unroute(self.SEARCH_API_PATTERN)
                self._search_route_handler_set = False
            except Exception as e:
                logger.debug(f"移除搜索路由处理器失败: {e}")

    # ==================== 人工行为模拟方法 ====================
    # 复用自 ctrip_login.py 中已验证的方法

    async def _human_move(self, end_x: float, end_y: float, steps: int = 15):
        """使用贝塞尔曲线模拟人类鼠标移动。"""
        start_x, start_y = self._last_mouse_pos

        # 贝塞尔曲线控制点（随机化）
        cp1_x = (
            start_x
            + (end_x - start_x) * random.uniform(0.3, 0.7)
            + random.uniform(-30, 30)
        )
        cp1_y = (
            start_y
            + (end_y - start_y) * random.uniform(0.3, 0.7)
            + random.uniform(-30, 30)
        )

        path = []
        for i in range(steps + 1):
            t = i / steps
            # 二次贝塞尔曲线
            x = (1 - t) ** 2 * start_x + 2 * (1 - t) * t * cp1_x + t**2 * end_x
            y = (1 - t) ** 2 * start_y + 2 * (1 - t) * t * cp1_y + t**2 * end_y
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
            target_x = random.uniform(100, viewport["width"] - 100)
            target_y = random.uniform(100, viewport["height"] - 100)
            await self._human_move(target_x, target_y)

    async def _simulate_human_browsing(self, duration: float = 5.0):
        """模拟人类浏览行为。

        包括：随机滚动、鼠标移动、短暂停顿等。

        Args:
            duration: 模拟浏览的总时长（秒）
        """
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < duration:
            action = random.choice(["scroll", "move", "wait"])

            if action == "scroll":
                # 向下滚动
                await self._human_scroll(delta_y=random.randint(150, 400), smooth=True)
            elif action == "move":
                # 随机移动鼠标
                await self._random_mouse_movement()
            else:
                # 短暂等待（模拟阅读）
                await asyncio.sleep(random.uniform(0.5, 1.5))

            await asyncio.sleep(random.uniform(0.3, 0.8))

        logger.debug(f"人工浏览模拟完成，持续 {duration:.1f} 秒")

    async def _human_type(
        self, text: str, min_delay: float = 0.03, max_delay: float = 0.12
    ):
        """模拟人类打字行为。

        包括随机延迟、偶尔的快速连击和停顿。
        """
        for i, char in enumerate(text):
            await self.page.keyboard.type(char)

            # 基础延迟
            base_delay = random.uniform(min_delay, max_delay)

            # 模拟思考停顿（约10%概率）
            if random.random() < 0.10:
                base_delay += random.uniform(0.2, 0.5)

            # 模拟连击加速（约25%概率，尤其是连续英文字母）
            if random.random() < 0.25 and i > 0:
                base_delay *= 0.5

            await asyncio.sleep(base_delay)

    async def _move_to_element_and_click(self, locator):
        """使用贝塞尔曲线移动到元素并点击。"""
        try:
            # 1. 确保元素可见并滚动到视图中
            await locator.first.scroll_into_view_if_needed()
            await locator.first.wait_for(state="visible", timeout=5000)

            # 2. 获取元素相对于视口（Viewport）的位置
            box = await locator.first.bounding_box()
            if not box:
                logger.warning("无法获取元素边界框，使用原生点击")
                await locator.first.click()
                return

            # 目标点：元素中心 + 小随机偏移
            target_x = box["x"] + box["width"] / 2 + random.uniform(-5, 5)
            target_y = box["y"] + box["height"] / 2 + random.uniform(-3, 3)

            # 3. 贝塞尔曲线平滑移动
            await self._human_move(target_x, target_y, steps=random.randint(12, 18))

            # 4. 瞬准停顿，模拟点击前的精准对准
            await asyncio.sleep(random.uniform(0.1, 0.25))

            # 5. 执行点击（使用视口坐标）
            await self.page.mouse.click(target_x, target_y)

        except Exception as e:
            logger.warning(f"类人移动点击失败，尝试直接点击: {e}")
            try:
                await locator.first.click(timeout=3000)
            except Exception as final_e:
                logger.error(f"直接点击也失败: {final_e}")

    async def _select_calendar_date(self, date_str: str, max_retries: int = 5):
        """在日历组件中选择指定日期。

        基于携程日历 HTML 解析：
        - 容器: td[role="gridcell"]
        - 内容: div.tipWrapper (含有 aria-label="2025年12月30日...")
        - 禁用: td 的 class 包含 is-disable
        """
        import re

        # 解析目标日期
        match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", date_str)
        if not match:
            logger.warning(f"无法解析日期格式: {date_str}")
            return False

        year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
        target_label_prefix = f"{year}年{month}月{day}日"

        for attempt in range(max_retries):
            try:
                # 等待日历面板稳定加载
                await asyncio.sleep(0.5)

                # 确保日历面板可见
                calendar = self.page.locator(
                    "div.c-calendar[role='application']:not(.is-hide)"
                )
                if await calendar.count() == 0:
                    logger.debug("日历面板不可见，等待...")
                    try:
                        await calendar.first.wait_for(state="visible", timeout=3000)
                    except Exception:
                        pass

                # 1. 直接通过 aria-label 定位 tipWrapper
                target_tip = self.page.locator(
                    f"div.tipWrapper[aria-label^='{target_label_prefix}']:visible"
                ).first

                if await target_tip.count() > 0:
                    # 获取父级 td 检查是否禁用
                    parent_td = target_tip.locator("xpath=..")

                    cell_class = await parent_td.get_attribute("class") or ""
                    aria_disabled = await parent_td.get_attribute("aria-disabled")

                    if "is-disable" in cell_class or aria_disabled == "true":
                        logger.debug(f"日期 {date_str} 在 UI 上显示为禁用，跳过")
                        return False
                    else:
                        # 拟人移动并点击
                        logger.info(f"📍 命中日期: {target_label_prefix}")
                        await self._move_to_element_and_click(target_tip)
                        await asyncio.sleep(random.uniform(0.3, 0.6))
                        return True

                # 2. 如果当前面板没找到，先导航到目标月份
                logger.debug(
                    f"尝试 {attempt + 1}/{max_retries}: 当前面板未找到日期 {date_str}"
                )

                if attempt < max_retries - 1:
                    navigated = await self._navigate_to_month(year, month)
                    if not navigated:
                        # 导航失败，等待后重试
                        await asyncio.sleep(1.0)
                    else:
                        # 导航成功，等待日历刷新
                        await asyncio.sleep(0.8)

            except Exception as e:
                logger.debug(f"日期选择尝试 {attempt + 1} 失败: {e}")
                await asyncio.sleep(0.5)

        logger.warning(f"日期选择失败，超过最大重试次数: {date_str}")
        return False

    async def _navigate_to_month(self, target_year: int, target_month: int):
        """导航日历到目标月份。"""
        try:
            import re

            # 导航按钮
            next_btn = self.page.locator("span.c-calendar-icon-next-mon").first
            prev_btn = self.page.locator("span.c-calendar-icon-prev-mon").first

            # 安全阈值
            for _ in range(12):
                # 获取展示的所有月份标题
                month_headers = self.page.locator("header.c-calendar-month__title h2")
                titles = await month_headers.all_inner_texts()

                found_target = False
                current_max_total = 0

                for title in titles:
                    m = re.search(r"(\d{4})年(\d{1,2})月", title)
                    if m:
                        y, m_val = int(m.group(1)), int(m.group(2))
                        current_max_total = max(current_max_total, y * 12 + m_val)
                        if y == target_year and m_val == target_month:
                            found_target = True
                            break

                if found_target:
                    logger.debug(f"已定位到目标月份: {target_year}-{target_month}")
                    return True

                # 判断翻页方向
                target_total = target_year * 12 + target_month
                if target_total > current_max_total:
                    if (
                        await next_btn.is_visible()
                        and not await next_btn.get_attribute("class")
                        or "" == "is-disable"
                    ):
                        await self._move_to_element_and_click(next_btn)
                    else:
                        break
                else:
                    if (
                        await prev_btn.is_visible()
                        and not await prev_btn.get_attribute("class")
                        or "" == "is-disable"
                    ):
                        await self._move_to_element_and_click(prev_btn)
                    else:
                        break

                await asyncio.sleep(random.uniform(0.5, 1.0))

            return False
        except Exception as e:
            logger.debug(f"月份翻页失败: {e}")
            return False

    async def _inject_dates_via_js(self, checkin: str, checkout: str):
        """通过 JS 注入方式设置日期。

        当无法通过 UI 操作日历时的后备方案。
        """
        try:
            await self.page.evaluate(
                """(dates) => {
                const inInput = document.querySelector('#checkIn') || 
                                document.querySelector('[class*="checkIn"]') ||
                                document.querySelector('.checkin-date input');
                const outInput = document.querySelector('#checkOut') || 
                                 document.querySelector('[class*="checkOut"]') ||
                                 document.querySelector('.checkout-date input');
                if(inInput) { 
                    inInput.value = dates.checkin; 
                    inInput.dispatchEvent(new Event('input', { bubbles: true })); 
                    inInput.dispatchEvent(new Event('change', { bubbles: true }));
                }
                if(outInput) { 
                    outInput.value = dates.checkout; 
                    outInput.dispatchEvent(new Event('input', { bubbles: true }));
                    outInput.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }""",
                {"checkin": checkin, "checkout": checkout},
            )
            logger.debug(f"JS 注入日期完成: {checkin} ~ {checkout}")
        except Exception as e:
            logger.warning(f"JS 注入日期失败: {e}")

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

    async def _perform_homepage_search(self, hotel_name: str) -> bool:
        """在携程首页执行搜索。"""
        await self.page.goto(
            "https://www.ctrip.com/", wait_until="networkidle", timeout=60000
        )
        await asyncio.sleep(random.uniform(1.0, 2.0))

        logger.debug("模拟用户浏览首页...")
        await self._simulate_human_browsing(duration=random.uniform(1.5, 3.0))

        search_input = self.page.locator(
            "input#_allSearchKeyword, input[placeholder*='搜索任何旅游相关']"
        )
        if await search_input.count() == 0:
            logger.error("未找到搜索输入框")
            return False

        await self._move_to_element_and_click(search_input)
        await asyncio.sleep(random.uniform(0.5, 1.2))

        logger.info(f"🔍 正在输入搜索关键词: {hotel_name}")
        await self._human_type(hotel_name)
        await asyncio.sleep(random.uniform(0.4, 0.8))
        return True

    async def _navigate_to_detail_page(self) -> Page | None:
        """点击搜索按钮并等待详情页打开。"""
        search_button = self.page.locator("#search_button_global, .pc_home-search")
        try:
            async with self.page.expect_popup(timeout=60000) as popup_info:
                if await search_button.count() > 0:
                    await self._move_to_element_and_click(search_button)
                else:
                    logger.warning("未找到搜索按钮，尝试回车键")
                    await self.page.keyboard.press("Enter")

            detail_page = await popup_info.value
            await detail_page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(random.uniform(1.5, 2.5))
            
            # 这里只做基本的页面获取，URL 检查放在 search_and_capture 里的重试逻辑中统一处理
            return detail_page

        except Exception as e:
            logger.error(f"等待酒店详情页超时或失败: {e}")
            return None

    async def _select_dates_on_detail_page(self, checkin: str, checkout: str) -> bool:
        """在详情页选择日期。"""
        await self._simulate_human_browsing(duration=random.uniform(1.0, 2.0))

        try:
            await self.page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            logger.debug("等待页面加载超时，继续操作")

        date_selector = self.page.locator(
            "div.calendar_middle__tPMkN.calendarRelavtive__pWLcx"
        )

        if await date_selector.count() == 0:
            logger.warning("未找到日期选择器，尝试 JS 注入方式")
            await self._inject_dates_via_js(checkin, checkout)
            await asyncio.sleep(random.uniform(1.0, 2.0))
            return True

        await date_selector.first.scroll_into_view_if_needed()
        await asyncio.sleep(0.5)
        await self._move_to_element_and_click(date_selector)
        await asyncio.sleep(random.uniform(1.0, 1.8))

        # 等待日历弹窗
        calendar_popup = self.page.locator(
            "div.c-calendar[role='application']:not(.is-hide)"
        )
        try:
            await calendar_popup.first.wait_for(state="visible", timeout=8000)
            await asyncio.sleep(0.8)
        except Exception:
            exists = await self.page.locator("div.c-calendar[role='application']").count() > 0
            if exists:
                await asyncio.sleep(1.0)
            else:
                logger.warning("日历弹窗未找到或未弹出")

        checkin_ok = await self._select_calendar_date(checkin)
        if checkin_ok:
            await asyncio.sleep(random.uniform(0.5, 0.8))

        checkout_ok = await self._select_calendar_date(checkout)
        if checkout_ok:
            await asyncio.sleep(random.uniform(0.5, 1.0))

        if not checkin_ok or not checkout_ok:
            logger.warning("日历选择未完成，尝试 JS 注入方式")
            await self._inject_dates_via_js(checkin, checkout)

        return True

    async def _verify_search_result(
        self,
        task: LaborTask,
        similarity_threshold: float = 0.85
    ) -> HotelMatch | None:
        """验证搜索结果中是否有匹配的酒店。

        从捕获的搜索 API 响应中提取酒店列表，
        使用4级匹配策略验证酒店名称相似度。

        支持两种 API 返回格式：
        - GET 方法 (26872/search): result.Response.searchResults 数组，type='Hotel'
        - POST 方法 (30668/search): result.data 数组，type='hotel'

        Args:
            task: 任务信息，包含目标酒店名称和城市
            similarity_threshold: 相似度阈值，默认 0.85 (85%)

        Returns:
            匹配到的酒店信息，如无匹配返回 None
        """
        if not self.search_result_data:
            logger.warning("未捕获到搜索 API 响应数据")
            return None

        try:
            hotels = []
            is_get_method = self.search_api_method == "GET"

            if is_get_method:
                # GET 方法 (26872/search): Response.searchResults
                response = self.search_result_data.get('Response', {})
                search_results = response.get('searchResults', [])

                if not isinstance(search_results, list):
                    logger.warning("GET API 搜索结果格式非预期")
                    return None

                # 过滤酒店类型 (type='Hotel'，注意大写 H)
                hotels = [item for item in search_results if item.get('type') == 'Hotel']
                logger.debug(f"GET API: 从 {len(search_results)} 个结果中过滤出 {len(hotels)} 个酒店")

            else:
                # POST 方法 (30668/search): data 数组
                data = self.search_result_data.get('data', [])

                if not isinstance(data, list):
                    logger.warning("POST API 搜索结果格式非预期")
                    return None

                # 过滤酒店类型 (type='hotel'，注意小写 h)
                hotels = [item for item in data if item.get('type') == 'hotel']
                logger.debug(f"POST API: 从 {len(data)} 个结果中过滤出 {len(hotels)} 个酒店")

            if not hotels:
                logger.warning("搜索结果中无酒店数据")
                return None

            logger.info(f"搜索结果包含 {len(hotels)} 个酒店 (API: {self.search_api_method or 'Unknown'})")

            # 使用匹配器验证
            match = HotelMatcher.match_hotels(
                hotels=hotels,
                keyword=task.hotel_name,
                city_name=task.city_name,
                similarity_threshold=similarity_threshold
            )

            if match:
                logger.info(
                    f"✅ 酒店匹配成功: {match.hotel_name} "
                    f"(相似度: {match.similarity:.2%}, 类型: {match.match_type})"
                )
            else:
                logger.warning(
                    f"❌ 未找到匹配酒店 (阈值: {similarity_threshold:.0%})"
                )

            return match

        except Exception as e:
            logger.error(f"验证搜索结果异常: {e}")
            return None

    async def _wait_for_search_result(self, timeout: float = 10.0) -> bool:
        """等待搜索 API 响应捕获完成。

        Args:
            timeout: 最大等待时间（秒）

        Returns:
            True if search result captured within timeout.
        """
        start_time = asyncio.get_event_loop().time()
        check_interval = 0.3

        while asyncio.get_event_loop().time() - start_time < timeout:
            if self.search_result_data is not None:
                return True
            await asyncio.sleep(check_interval)

        return False

    async def search_and_capture(self, task: LaborTask) -> dict | str | None:
        """从首页搜索酒店并采集数据。

        包含酒店名称匹配验证和重试机制：
        1. 首页搜索 -> 拦截搜索 API 响应
        2. 验证酒店名称相似度 (>=90%)
        3. 如不匹配 -> 废弃题目并返回 None
        4. 如匹配 -> 进入详情页采集数据
        5. URL 不匹配详情页格式 -> 视为搜索不到（直接提交）
        """
        import re
        max_retries = 3
        capture_timeout = 45.0
        similarity_threshold = 0.85  # 90% 相似度阈值

        original_page = self.page
        detail_url_pattern = re.compile(r"https://hotels\.ctrip\.com/hotels/\d+\.html\?cityid=\d+")

        for attempt in range(max_retries):
            new_pages = []
            try:
                logger.info(f"🔄 开始第 {attempt + 1}/{max_retries} 次搜索尝试: {task.hotel_name}")

                # 1. 开启新标签页
                new_page = await self.page.context.new_page()
                new_pages.append(new_page)
                self.page = new_page

                # 2. 设置路由拦截（同时拦截搜索 API 和房型 API）
                await self._setup_route_handler()
                await self._setup_search_route_handler()
                self.search_result_data = None  # 重置搜索结果
                self.search_api_method = None   # 重置 API 方法

                # 3. 执行首页搜索
                if not await self._perform_homepage_search(task.hotel_name):
                    logger.warning("首页搜索失败，准备重试...")
                    await self._cleanup_pages(new_pages)
                    self.page = original_page
                    continue

                # 4. 点击搜索并等待详情页打开（同时搜索 API 会被触发）
                logger.info("点击搜索，等待搜索结果...")
                detail_page = await self._navigate_to_detail_page()

                # 注意：点击搜索后详情页会自动打开（popup），需要将其加入待清理列表
                if detail_page:
                    new_pages.append(detail_page)

                # 等待搜索 API 响应（最多等待10秒）
                await self._wait_for_search_result(timeout=10.0)

                # 5. 验证酒店名称匹配度
                match_result = await self._verify_search_result(
                    task, similarity_threshold=similarity_threshold
                )

                if not match_result:
                    # 未匹配到符合条件的酒店 -> 直接关闭所有页面，废弃题目
                    logger.warning(f"搜索结果中未找到匹配酒店 (相似度 >= {similarity_threshold:.0%})")
                    logger.info("🗑️ 不匹配，关闭携程页面并执行废弃题目流程...")

                    # 先关闭携程页面（包括详情页和首页）
                    await self._simulate_human_browsing(duration=random.uniform(0.5, 1.5))
                    await self._cleanup_pages(new_pages)
                    self.page = original_page

                    if self.claim_workflow:
                        # 调用废弃题目逻辑
                        discard_success = await self.claim_workflow.discard_task()
                        if discard_success:
                            logger.info("✅ 废弃题目成功，将重新领取新题目")
                        else:
                            logger.warning("废弃题目失败")

                        # 返回特殊标记，让调用方知道需要重新领题
                        return "废弃重领"
                    else:
                        # 无 claim_workflow，按原逻辑返回 None
                        return None

                # 匹配成功，继续后续流程
                logger.info(f"酒店匹配验证通过，继续采集流程...")

                if not detail_page:
                    logger.warning("进入详情页失败，准备重试...")
                    await self._cleanup_pages(new_pages)
                    self.page = original_page
                    continue

                # 设置当前页面为详情页，继续后续采集
                self.page = detail_page
                self._route_handler_set = False
                self._search_route_handler_set = False
                await self._setup_route_handler()

                # URL 格式检查
                current_url = detail_page.url
                if not detail_url_pattern.match(current_url):
                    logger.warning(f"页面URL不匹配详情页格式 ({current_url[:100]})，视为搜索不到")
                    await self._simulate_human_browsing(duration=random.uniform(1.0, 3.5))
                    await self._cleanup_pages(new_pages)
                    self.page = original_page
                    return "搜索不到"

                # 6. 选择日期
                logger.info(f"正在详情页修改日期: {task.checkin} ~ {task.checkout}")
                await self._select_dates_on_detail_page(task.checkin, task.checkout)

                # 7. 等待数据捕获
                logger.info(f"📡 等待 getHotelRoomListInland 接口响应 (超时: {capture_timeout}s)...")
                captured = await self._wait_for_data_capture(timeout=capture_timeout)

                if captured and self.captured_data:
                    if isinstance(self.captured_data, dict):
                        logger.info(f"✅ 成功捕获房型数据，尝试: {attempt+1}")
                        await self._simulate_human_browsing(duration=random.uniform(2.5, 4.5))
                        await self._cleanup_pages(new_pages)
                        self.page = original_page
                        return self.captured_data
                    logger.warning("捕获的数据格式非预期")
                else:
                    # API 拦截失败，尝试页面兜底方案
                    logger.warning("API 拦截超时，尝试页面兜底提取...")
                    fallback_data = await self._extract_hotel_info_from_page()
                    if fallback_data:
                        logger.info(f"✅ 页面兜底成功，尝试: {attempt+1}")
                        await self._simulate_human_browsing(duration=random.uniform(2.5, 4.5))
                        await self._cleanup_pages(new_pages)
                        self.page = original_page
                        return fallback_data
                    logger.warning("页面兜底也失败，准备重试...")

            except Exception as e:
                logger.error(f"搜索尝试 {attempt+1} 异常: {e}")

            # 本次尝试失败，清理并重试
            await self._cleanup_pages(new_pages)
            self.page = original_page
            self._route_handler_set = False
            self._search_route_handler_set = False
            self.captured_data = None
            self.search_result_data = None
            self.search_api_method = None

            if attempt < max_retries - 1:
                wait_time = random.uniform(2, 4)
                logger.info(f"等待 {wait_time:.1f} 秒后进行下一次尝试...")
                await asyncio.sleep(wait_time)

        logger.error("❌ 所有重试均失败")
        return None

    async def _extract_hotel_info_from_page(self) -> dict | None:
        """从详情页 HTML 提取酒店信息（API 拦截失败时的兜底方案）。

        当 getHotelRoomListInland API 拦截失败时，尝试从页面 DOM 提取基本信息。

        Returns:
            包含酒店基本信息的字典，如提取失败返回 None
        """
        try:
            # 等待页面加载完成
            await self.page.wait_for_load_state("domcontentloaded", timeout=5000)

            # 尝试从页面提取酒店名称
            hotel_name = None
            hotel_id = None

            # 方法1: 从 URL 提取酒店 ID
            current_url = self.page.url
            import re
            id_match = re.search(r'/hotels/(\d+)\.html', current_url)
            if id_match:
                hotel_id = int(id_match.group(1))
                logger.debug(f"从 URL 提取酒店 ID: {hotel_id}")

            # 方法2: 从页面标题提取酒店名称
            title_element = await self.page.query_selector("h1.hotel-name, .hotel-title, [class*='hotelName']")
            if title_element:
                hotel_name = await title_element.inner_text()
                hotel_name = hotel_name.strip() if hotel_name else None
                logger.debug(f"从页面提取酒店名称: {hotel_name}")

            # 方法3: 从 meta 标签提取
            if not hotel_name:
                meta_title = await self.page.query_selector("meta[property='og:title']")
                if meta_title:
                    content = await meta_title.get_attribute("content")
                    if content:
                        hotel_name = content.split("-")[0].strip()

            # 方法4: 从 document.title 提取
            if not hotel_name:
                page_title = await self.page.title()
                if page_title:
                    # 携程标题格式通常是 "酒店名称-携程酒店"
                    hotel_name = page_title.split("-")[0].strip()

            if hotel_name and hotel_id:
                logger.info(f"🔄 页面兜底提取成功: {hotel_name} (ID: {hotel_id})")
                return {
                    "data": {
                        "hotelId": hotel_id,
                        "hotelName": hotel_name,
                        "source": "page_fallback"
                    }
                }

            logger.warning("页面兜底提取失败: 无法获取酒店名称或 ID")
            return None

        except Exception as e:
            logger.error(f"页面兜底提取异常: {e}")
            return None

    async def _cleanup_pages(self, pages: list[Page]):
        """清理临时页面列表。"""
        for p in pages:
            try:
                if not p.is_closed():
                    await p.close()
            except Exception:
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
        self.account_blacklisted = False

    def is_account_blacklisted(self) -> bool:
        """检查是否检测到账号被封。

        Returns:
            True if htlSpiderActionErrorCode: 203 was detected
        """
        return self.account_blacklisted

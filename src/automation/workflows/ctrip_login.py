import asyncio
import base64
import random
import re
from typing import Callable, Optional

from playwright.async_api import Page

from src.automation.workflows.base import BaseWorkflow
from src.automation.workflows.sms_receiver import SMSReceiver
from src.core.models.ctrip_account import CtripAccount
from src.utils.captcha_solver import CaptchaSolver
from src.utils.logger import logger


class CtripLoginWorkflow(BaseWorkflow):
    def __init__(self, page: Page):
        super().__init__(page)
        self.sms_receiver = SMSReceiver("", "")
        self._last_mouse_pos = (0, 0)  # Track last mouse position for realism

    def _decode_image_src(self, src: str) -> bytes | None:
        """
        解码图片 src 属性，支持 base64 data URL 和普通 URL。

        Args:
            src: 图片的 src 属性值

        Returns:
            图片字节数据，失败返回 None
        """
        try:
            if src.startswith("data:"):
                # base64 data URL 格式: data:image/png;base64,xxxxx
                if ";base64," in src:
                    base64_data = src.split(";base64,")[1]
                    return base64.b64decode(base64_data)
                else:
                    logger.warning(f"不支持的 data URL 格式: {src[:50]}...")
                    return None
            elif src.startswith("http"):
                # HTTP URL - 使用 urllib 下载
                import urllib.request

                with urllib.request.urlopen(src, timeout=10) as response:
                    return response.read()
            else:
                logger.warning(f"不支持的 src 格式: {src[:50]}...")
                return None
        except Exception as e:
            logger.error(f"解码图片 src 失败: {e}")
            return None

    async def human_move(self, end_x: float, end_y: float, steps: int = 15):
        """
        Simulate human-like mouse movement using Bezier curves.
        """
        start_x, start_y = self._last_mouse_pos

        # Control points for Bezier curve (randomized)
        cp1_x = (
            start_x
            + (end_x - start_x) * random.uniform(0.3, 0.7)
            + random.uniform(-50, 50)
        )
        cp1_y = (
            start_y
            + (end_y - start_y) * random.uniform(0.3, 0.7)
            + random.uniform(-50, 50)
        )

        path = []
        for i in range(steps + 1):
            t = i / steps
            # Quadratic Bezier
            x = (1 - t) ** 2 * start_x + 2 * (1 - t) * t * cp1_x + t**2 * end_x
            y = (1 - t) ** 2 * start_y + 2 * (1 - t) * t * cp1_y + t**2 * end_y
            path.append((x, y))

        for x, y in path:
            await self.page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.005, 0.015))

        self._last_mouse_pos = (end_x, end_y)

    async def human_click(self, selector: str):
        """
        Move to element and click with random delays.
        """
        try:
            locator = self.page.locator(selector).first
            # Ensure visible and scrolled into view
            await locator.scroll_into_view_if_needed()

            box = await locator.bounding_box()
            if box:
                target_x = box["x"] + box["width"] * random.uniform(0.2, 0.8)
                target_y = box["y"] + box["height"] * random.uniform(0.2, 0.8)
                await self.human_move(target_x, target_y)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await self.page.mouse.down()
                await asyncio.sleep(random.uniform(0.05, 0.15))
                await self.page.mouse.up()
            else:
                logger.warning(f"选择器 {selector} 未能获取 bounding_box，尝试直接点击")
                await locator.click(timeout=5000)
        except Exception as e:
            logger.warning(
                f"human_click 第一阶段失败 ({selector}): {e}, 尝试强制点击..."
            )
            try:
                await self.page.locator(selector).first.click(force=True, timeout=5000)
            except Exception as e2:
                logger.error(f"强制点击也失败了 ({selector}): {e2}")
                raise e2

    async def human_type(self, selector: str, text: str):
        """
        Type text with random delays between keystrokes.
        """
        await self.human_click(selector)
        await asyncio.sleep(random.uniform(0.2, 0.5))
        for char in text:
            await self.page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.05, 0.2))

    async def human_drag(
        self, start_x, start_y, end_x, end_y, with_overshoot: bool = True
    ):
        """
        高度仿真的人类拖拽行为。

        特征模拟：
        1. 按下前短暂停顿（瞄准时间）
        2. 慢启动 → 快速移动 → 减速接近 → 微调
        3. 轻微过冲后回调
        4. 随机 Y 轴抖动（手不稳）
        5. 非匀速移动间隔
        """
        await self.human_move(start_x, start_y)

        # 1. 按下前瞄准停顿
        await asyncio.sleep(random.uniform(0.15, 0.35))
        await self.page.mouse.down()

        # 2. 按下后启动延迟
        await asyncio.sleep(random.uniform(0.08, 0.2))

        distance = end_x - start_x

        # 3. 过冲距离（真人常见行为）
        overshoot = 0
        if with_overshoot and distance > 30:
            overshoot = random.uniform(3, 12)

        # 4. 分阶段移动
        # 阶段1：慢启动 (0-15%)
        # 阶段2：快速移动 (15-75%)
        # 阶段3：减速接近 (75-95%)
        # 阶段4：微调到位 (95-100%)

        total_steps = random.randint(40, 60)

        for i in range(total_steps):
            progress = (i + 1) / total_steps

            # 多阶段速度曲线
            if progress < 0.15:
                # 慢启动：二次缓入
                phase_progress = progress / 0.15
                t = 0.15 * (phase_progress**2)
            elif progress < 0.75:
                # 快速移动：近似线性
                phase_progress = (progress - 0.15) / 0.6
                t = 0.15 + 0.6 * phase_progress
            elif progress < 0.95:
                # 减速接近：缓出
                phase_progress = (progress - 0.75) / 0.2
                t = 0.75 + 0.2 * (1 - (1 - phase_progress) ** 2)
            else:
                # 微调
                phase_progress = (progress - 0.95) / 0.05
                t = 0.95 + 0.05 * phase_progress

            # 计算目标位置（包含过冲）
            if progress < 0.9:
                target_x = start_x + (distance + overshoot) * t
            else:
                # 最后 10% 回调到正确位置
                overshoot_x = start_x + distance + overshoot
                correction_progress = (progress - 0.9) / 0.1
                target_x = overshoot_x - overshoot * correction_progress

            # Y 轴抖动（模拟手抖）
            # 中间阶段抖动更大，开始和结束时更稳
            if 0.2 < progress < 0.8:
                y_noise = random.gauss(0, 2.5)  # 高斯分布更自然
            else:
                y_noise = random.gauss(0, 1.0)

            target_y = start_y + y_noise

            # 添加微小 X 轴随机波动
            x_noise = random.gauss(0, 0.5) if 0.3 < progress < 0.7 else 0

            await self.page.mouse.move(target_x + x_noise, target_y)

            # 非匀速延迟
            if progress < 0.15:
                delay = random.uniform(0.025, 0.05)  # 启动慢
            elif progress < 0.75:
                delay = random.uniform(0.008, 0.02)  # 中间快
            elif progress < 0.95:
                delay = random.uniform(0.015, 0.035)  # 减速
            else:
                delay = random.uniform(0.03, 0.06)  # 微调慢

            await asyncio.sleep(delay)

        # 5. 到达后短暂停顿（确认位置）
        await asyncio.sleep(random.uniform(0.1, 0.25))

        # 6. 释放
        await self.page.mouse.up()

        self._last_mouse_pos = (end_x, end_y)

    async def select_country_code(self, country_code: str):
        """
        Selects the country code from the dropdown.
        """
        try:
            # Click the country code dropdown starter
            # Selector derived from inspection: .intel-tel-code or similar
            # Fallback to finding by text if class name varies
            dropdown_trigger = self.page.locator(
                ".intel-tel-code, .country-code-selector"
            ).first
            if not await dropdown_trigger.is_visible():
                # Try finding by text "+86" or similar current code
                dropdown_trigger = self.page.locator("text=+86").first

            if await dropdown_trigger.is_visible():
                await self.human_click(
                    ".intel-tel-code"
                )  # Simplified selector assumption

                # Wait for list
                await self.page.wait_for_selector(
                    ".country-list, .popover-content", timeout=3000
                )

                # Find the specific code.
                # Usually text="+1" or text="美国"
                # Need to be robust.
                target_option = self.page.locator(
                    f"li:has-text('{country_code}')"
                ).first
                if await target_option.is_visible():
                    await target_option.scroll_into_view_if_needed()
                    await self.human_click(f"li:has-text('{country_code}')")
                    logger.info(f"Selected country code: {country_code}")
                else:
                    logger.warning(f"Country code {country_code} not found in list")
            else:
                logger.warning("Country code dropdown trigger not found")

        except Exception as e:
            logger.warning(f"Failed to select country code: {e}")

            logger.warning(f"Failed to select country code: {e}")

    async def _handle_click_captcha(self) -> bool:
        """
        处理点选验证码。
        """
        try:
            logger.info("开始处理点选验证码...")

            # 1. 获取图片
            # 背景大图
            bg_loc = self.page.locator(".big-icon-image").first
            # 提示小图 (显示要点击的顺序)
            prompt_loc = self.page.locator(".small-icon-img").first

            if not await bg_loc.is_visible() or not await prompt_loc.is_visible():
                logger.error("点选验证码图片元素不可见")
                return False

            bg_src = await bg_loc.get_attribute("src")
            prompt_src = await prompt_loc.get_attribute("src")

            if not bg_src:
                return False

            bg_bytes = self._decode_image_src(bg_src)
            prompt_bytes = self._decode_image_src(prompt_src) if prompt_src else None

            if not bg_bytes:
                logger.error("无法解码点选背景图")
                return False

            # 2. 识别坐标
            points = CaptchaSolver.solve_click(bg_bytes, prompt_bytes, debug=False)
            if not points:
                logger.warning("未能识别出点选图标位置")
                # 兜底：如果没有识别出，可以尝试随机点击或者请求人工介入(这里暂且返回失败)
                return False

            logger.info(f"识别到 {len(points)} 个点击目标: {points}")

            # 3. 执行点击
            # 获取图片在页面上的实际位置和尺寸
            box = await bg_loc.bounding_box()
            if not box:
                return False

            # ddddocr 返回的是基于图片原始尺寸的坐标，还是缩放后的？
            # ddddocr 是基于传入字节流图片的原始尺寸。
            # 我们需要计算缩放比例。
            # 通常需要获取图片的自然尺寸。

            # 通过 JS 获取图片原始尺寸
            natural_size = await bg_loc.evaluate(
                "el => ({w: el.naturalWidth, h: el.naturalHeight})"
            )
            scale_x = box["width"] / natural_size["w"]
            scale_y = box["height"] / natural_size["h"]

            for i, (px, py) in enumerate(points):
                # 转换坐标
                target_x = box["x"] + px * scale_x
                target_y = box["y"] + py * scale_y

                logger.info(f"点击第 {i + 1} 个图标: ({target_x}, {target_y})")

                # 模拟在此处点击
                await self.human_move(target_x, target_y)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                await self.page.mouse.down()
                await asyncio.sleep(random.uniform(0.05, 0.1))
                await self.page.mouse.up()
                await asyncio.sleep(random.uniform(0.5, 1.0))

            # 某些验证码点击完自动提交，有些需要点确认
            # 检查是否有确认按钮
            confirm_btn = self.page.locator(".cpt-ok-btn, .pop-ok-btn").first
            if await confirm_btn.is_visible():
                await self.human_click(".cpt-ok-btn, .pop-ok-btn")

            await asyncio.sleep(2)
            return True

        except Exception as e:
            logger.error(f"处理点选验证码异常: {e}")
            return False

    async def _wait_for_captcha(
        self, slider_selector: str, click_selector: str, timeout: float = 15.0
    ) -> str | None:
        """等待验证码组件出现，返回类型 'slider'/'click' 或 None。"""
        start_time = asyncio.get_event_loop().time()
        logger.info(f"等待验证码组件出现 (最多等待 {timeout} 秒)...")

        while asyncio.get_event_loop().time() - start_time < timeout:
            if await self.page.locator(slider_selector).is_visible():
                return "slider"
            if await self.page.locator(click_selector).first.is_visible():
                return "click"
            await asyncio.sleep(2)
        return None

    async def _is_captcha_success(self, api_success: bool, success_msg: str) -> bool:
        """检查验证码是否已成功。"""
        if api_success:
            return True
        return await self.page.locator(f"text='{success_msg}'").is_visible()

    async def _try_refresh_captcha(self) -> None:
        """尝试刷新验证码。"""
        refresh_btn = self.page.locator(".cpt-refresh, [class*='refresh']").first
        if await refresh_btn.is_visible():
            logger.info("尝试刷新验证码")
            await refresh_btn.click()
            await asyncio.sleep(2)

    async def handle_captcha(self) -> bool:
        """处理携程验证码（滑块或点选）。"""
        slider_selector = ".cpt-drop-btn"
        click_selector = (
            ".cpt-icon-box, .icon-image-container, "
            "[data-testid='captcha'] .big-icon-image"
        )

        try:
            # 1. 等待验证码出现
            captcha_type = await self._wait_for_captcha(slider_selector, click_selector)
            if not captcha_type:
                logger.error("等待 15 秒后未检测到已知验证码，流程中断")
                return False

            logger.info(f"检测到 {captcha_type} 验证码，开始破解...")

            # 2. 设置成功检测
            captcha_api_success = False
            success_msg = "验证码已发送至您的手机，请注意查收!"

            async def handle_response(response):
                nonlocal captcha_api_success
                if "sendVerifyCodeByMobilePhone" in response.url and response.status == 200:
                    try:
                        resp_data = await response.json()
                        if resp_data.get("resultCode") == 0 or resp_data.get("status") == 0:
                            captcha_api_success = True
                            logger.info("🌐 接口返回验证码发送成功")
                    except Exception:
                        pass

            self.page.on("response", handle_response)

            try:
                # 3. 尝试破解
                for attempt in range(4):
                    logger.info(f"开始第 {attempt + 1}/4 次尝试破解 ({captcha_type})...")

                    if await self._is_captcha_success(captcha_api_success, success_msg):
                        logger.info("✅ 判定为验证码已发送成功 (提前检测)")
                        return True

                    # 执行破解
                    if captcha_type == "click":
                        result = await self._handle_click_captcha()
                    else:
                        result = await self._handle_slider_logic(slider_selector)

                    if not result:
                        logger.warning("本次尝试失败, 检查验证码类型或刷新")
                        await asyncio.sleep(2)

                        # 检测类型切换
                        if await self.page.locator(click_selector).first.is_visible():
                            captcha_type = "click"
                        elif await self.page.locator(slider_selector).is_visible():
                            captcha_type = "slider"

                        if not captcha_api_success:
                            await self._try_refresh_captcha()
                        continue

                    await asyncio.sleep(3)

                    if await self._is_captcha_success(captcha_api_success, success_msg):
                        logger.info("✅ 破解后判定成功")
                        return True

                return False

            finally:
                self.page.remove_listener("response", handle_response)

        except Exception as e:
            logger.error(f"处理验证码异常: {e}")
            return False

    async def _handle_slider_logic(self, slider_selector: str) -> bool:
        """
        原有的滑块处理逻辑提取
        """
        try:
            # 1. 获取背景图
            bg_selectors = [
                "img.advise",
                ".cpt-img-cal-box img",
                ".cpt-bg-img img",
                "[class*='captcha'] img",
                ".cpt-drop-box img",
            ]
            bg_img_loc = None
            for sel in bg_selectors:
                try:
                    loc = self.page.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        box = await loc.bounding_box()
                        if box and box["width"] > 100:
                            bg_img_loc = loc
                            break
                except Exception:
                    continue

            if bg_img_loc is None:
                return False

            # 2 & 3. 获取图片数据
            bg_src = await bg_img_loc.get_attribute("src")
            bg_bytes = self._decode_image_src(bg_src) if bg_src else None

            slider_piece_selectors = [
                "img.image-left",
                ".image-left img",
                ".cpt-img-double img",
                ".cpt-small-img img",
            ]
            slider_bytes = None
            for sel in slider_piece_selectors:
                loc = self.page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    src = await loc.get_attribute("src")
                    if src:
                        slider_bytes = self._decode_image_src(src)
                        if slider_bytes:
                            break

            if not bg_bytes:
                return False

            # 4. 识别缺口并拖拽
            offset, img_w = CaptchaSolver.solve_slider(
                bg_bytes, slider_bytes, debug=False
            )
            if offset == 0:
                return False

            slider_box = await self.page.locator(slider_selector).bounding_box()
            bg_box = await bg_img_loc.bounding_box()
            if not slider_box or not bg_box:
                return False

            scale_ratio = bg_box["width"] / img_w
            drag_distance = (
                (offset * scale_ratio)
                - (slider_box["width"] / 2)
                + random.uniform(-5, 5)
            )

            start_x = slider_box["x"] + slider_box["width"] / 2
            start_y = slider_box["y"] + slider_box["height"] / 2
            await self.human_drag(
                start_x, start_y, start_x + drag_distance, start_y, with_overshoot=True
            )
            return True
        except Exception as e:
            logger.warning(f"滑块逻辑执行异常: {e}")
            return False

    async def _get_code_from_sms_platform(
        self, account: CtripAccount, phone: str
    ) -> str | None:
        """通过接码平台取码（3分钟超时）。

        Args:
            account: 携程账号（包含平台配置）
            phone: 手机号

        Returns:
            验证码字符串，失败返回 None
        """
        from src.config import config
        from src.utils.sms_platform import SMSPlatformClient, SMSPlatformConfig

        # 从配置或账号获取平台信息
        host = config.sms_platform_host
        username = config.sms_platform_username
        password = config.sms_platform_password
        product_id = config.sms_platform_product_id

        if not all([host, username, password, product_id]):
            logger.error("接码平台配置不完整")
            return None

        client = SMSPlatformClient(
            SMSPlatformConfig(
                host=host,
                username=username,
                password=password,
                product_id=product_id,
            )
        )

        logger.info(f"📱 正在从接码平台获取验证码 (手机号: {phone})...")
        code = await client.get_code(phone, timeout=180)  # 3分钟超时

        if code:
            logger.info(f"✅ 接码平台取码成功: {code}")
        else:
            logger.error("❌ 接码平台取码失败或超时")

        return code

    async def _switch_to_sms_login(self) -> bool:
        """切换到短信验证码登录面板。"""
        sms_tab = self.page.locator(
            "a.login-entry-dynamic, a:has-text('验证码登录')"
        ).first
        if await sms_tab.is_visible():
            await self.human_click("a.login-entry-dynamic, a:has-text('验证码登录')")
            await asyncio.sleep(0.5)
            try:
                await self.page.wait_for_selector(
                    "[data-testid='dynamicPanel']", state="visible", timeout=5000
                )
                logger.info("✅ 已切换到验证码登录面板")
                return True
            except Exception as e:
                logger.warning(f"等待验证码面板超时: {e}")
        return False

    def _parse_phone_input(
        self, user_phone: str, default_cc: str
    ) -> tuple[str, str]:
        """解析用户输入的手机号，返回 (country_code, phone)。"""
        if user_phone.startswith("+"):
            match = re.match(r"(\+\d+)(.*)", user_phone)
            if match:
                return match.group(1), match.group(2)
        return default_cc, user_phone

    async def _get_verification_code(
        self,
        account: CtripAccount | None,
        phone: str,
        country_code: str,
        input_callback: Optional[Callable],
    ) -> str | None:
        """获取验证码（自动或手动）。"""
        sms_type = getattr(account, "sms_verify_type", "manual") if account else "manual"

        if sms_type == "api" and account:
            return await self._get_code_from_sms_platform(account, phone)
        elif input_callback:
            return input_callback(
                "输入验证码",
                f"已发送短信至 {country_code}{phone}，请输入验证码:",
                default="",
            )
        return None

    async def _check_agreement(self) -> None:
        """勾选用户协议复选框。"""
        agreement_selectors = [
            "input[type='checkbox']",
            ".agreement-checkbox",
            "[class*='agree'] input",
            ".custom_checkbox",
            ".login_agreement_checkbox",
        ]
        for sel in agreement_selectors:
            try:
                locator = self.page.locator(sel).first
                if await locator.is_visible() and not await locator.is_checked():
                    await self.human_click(sel)
                    break
            except Exception:
                pass

    async def _click_login_button(self) -> bool:
        """点击登录按钮。"""
        login_btn_selectors = [
            "input[data-testid='loginButton']",
            "input[value='登录']",
            "button:has-text('登录')",
            ".login_btn",
            "#loginBtn",
        ]
        for btn_sel in login_btn_selectors:
            try:
                btn = self.page.locator(btn_sel).first
                if await btn.is_visible() and await btn.is_enabled():
                    logger.info(f"正在尝试点击登录按钮: {btn_sel}")
                    await self.human_click(btn_sel)
                    logger.info(f"✅ 已触发点击: {btn_sel}")
                    return True
            except Exception as e:
                logger.warning(f"点击登录按钮 {btn_sel} 时抛出异常: {e}")
        return False

    async def _verify_login_success(self) -> bool:
        """验证登录是否成功（轮询检测）。"""
        try:
            await self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        for check_idx in range(5):
            if await self.is_logged_in():
                logger.info(f"✅ 登录成功 (检测点 {check_idx + 1})")
                return True
            await asyncio.sleep(2)
        return False

    async def login(
        self,
        account: CtripAccount | None = None,
        input_callback: Optional[Callable] = None,
    ) -> str | None:
        """执行携程登录流程。

        支持最多 2 轮尝试，每轮包含完整的登录流程。
        """
        pure_phone = account.phone_number if account and account.phone_number else ""
        country_code = account.country_code if account else "+86"

        for attempt in range(2):
            logger.info(f"🚀 执行登录流程: 第 {attempt + 1} 轮")

            try:
                # 1. 导航到登录页
                await self.page.goto(
                    "https://passport.ctrip.com/user/login",
                    wait_until="domcontentloaded",
                )

                if await self.is_logged_in():
                    logger.info("✅ 已登录")
                    return "ALREADY_LOGGED_IN"

                # 2. 切换到短信登录
                await self._switch_to_sms_login()

                # 3. 获取手机号
                current_phone, current_cc = pure_phone, country_code
                if not current_phone and input_callback:
                    user_phone = input_callback(
                        "输入手机号", "请输入携程登录手机号:", default=""
                    )
                    if user_phone:
                        current_cc, current_phone = self._parse_phone_input(
                            user_phone, country_code
                        )

                if not current_phone:
                    logger.error("无手机号，无法登录")
                    return None

                # 4. 输入手机号
                if current_cc != "+86":
                    await self.select_country_code(current_cc)

                phone_input_selector = (
                    "[data-testid='dynamicPanel'] input[type='tel'], "
                    "input[data-testid='telInput']:visible"
                )
                await self.human_type(phone_input_selector, current_phone)

                # 5. 发送验证码
                await self.human_click("text='发送验证码'")

                if not await self.handle_captcha():
                    logger.warning(f"第 {attempt + 1} 次尝试失败")
                    await asyncio.sleep(1)
                    continue

                # 6. 获取并填入验证码
                logger.info("等待获取验证码...")
                code = await self._get_verification_code(
                    account, current_phone, current_cc, input_callback
                )

                if not code:
                    logger.error("未获得验证码，终止本次尝试")
                    continue

                await self.human_type("input[placeholder*='验证码']", code)
                await asyncio.sleep(random.uniform(0.5, 1.0))

                # 7. 勾选协议
                await self._check_agreement()
                await asyncio.sleep(0.5)

                # 8. 点击登录
                if not await self._click_login_button():
                    logger.info("未找到匹配的登录按钮，尝试回车键登录")
                    await self.page.keyboard.press("Enter")
                    await asyncio.sleep(2)

                # 9. 验证登录成功
                if await self._verify_login_success():
                    return current_phone

                logger.warning(f"第 {attempt + 1} 次尝试未检测到登录成功")

            except Exception as e:
                logger.error(f"登录尝试第 {attempt + 1} 次出错: {e}")
                await asyncio.sleep(2)

        return None

    async def is_logged_in(self) -> bool:
        """
        Check if user is already logged in via Cookies or UI element.
        """
        cookies = await self.page.context.cookies()
        # Ctrip auth cookie is usually 'cticket' or 'Union' or 'UID'
        # Heuristic check
        has_auth = any(c.get("name") == "cticket" for c in cookies)
        if has_auth:
            return True

        # UI Check
        try:
            if await self.page.is_visible("text=退出"):
                return True
        except Exception:
            pass

        return False

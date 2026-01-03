"""Labor task claim workflow module.

Handles claiming (taking) a new task from the Labor platform (劳保保).
Based on content.js executePageTask() analysis.
"""

import asyncio
import re

from src.automation.workflows.base import BaseWorkflow
from src.core.models.labor_task import LaborTask, TaskState
from src.utils.logger import logger


class LaborClaimTaskWorkflow(BaseWorkflow):
    """Workflow for claiming tasks on the Labor platform (劳保保)."""

    # 做题页面URL
    TASK_URL = "https://frontend.lobaobao97.com/mark"

    # DOM 选择器 (基于 content.js 分析)
    SELECT_CITY_BUTTON = "button:has-text('选择城市')"
    CLAIM_BUTTON = "button:has-text('领题')"
    ABANDON_BUTTON = "button:has-text('废弃')"
    SUBMIT_BUTTON = "button:has-text('提交')"

    # 任务信息选择器
    FORM_ITEM = ".adm-form-item"
    FORM_LABEL = ".adm-form-item-label"
    FORM_VALUE = ".adm-form-item-child-inner span"

    # 城市选择弹窗
    CITY_LIST_ITEM = ".adm-check-list-item"
    CITY_CONTENT = ".adm-list-item-content-main"
    POPUP_MASK = ".adm-mask"

    # 复制按钮选择器
    COPY_BUTTON = "button:has-text('复制')"

    async def _get_task_detail_text(self, label_text: str) -> str | None:
        """从页面 DOM 中提取任务详情文本。"""
        try:
            items = await self.page.query_selector_all(self.FORM_ITEM)

            for item in items:
                label = await item.query_selector(self.FORM_LABEL)
                if not label:
                    continue

                label_content = await label.inner_text()
                if (
                    label_text
                    in label_content.replace(" ", "").replace("\u00a0", "").strip()
                ):
                    value_span = await item.query_selector(self.FORM_VALUE)
                    if value_span:
                        text = await value_span.inner_text()
                        return text.strip()
            return None
        except Exception as e:
            logger.debug(f"提取任务详情失败 ({label_text}): {e}")
            return None

    async def _get_hotel_name_via_copy(self) -> str | None:
        """通过点击'复制'按钮获取酒店名称。"""
        try:
            # 找到酒店名称项目
            items = await self.page.query_selector_all(self.FORM_ITEM)
            for item in items:
                label = await item.query_selector(self.FORM_LABEL)
                if label and "酒店名称" in await label.inner_text():
                    copy_btn = await item.query_selector(self.COPY_BUTTON)
                    if copy_btn:
                        # 触发复制
                        await copy_btn.click()
                        await asyncio.sleep(0.5)
                        # 从剪切板获取 (Playwright 无法直接获取外部剪切板，但我们可以尝试从 DOM 元素获取兜底)
                        return await self._get_task_detail_text("酒店名称")
            return None
        except Exception:
            return None

    async def _get_current_city(self) -> str:
        """获取当前选择的城市名称。"""
        try:
            city_button = await self.page.query_selector(self.SELECT_CITY_BUTTON)
            if city_button:
                parent = await city_button.evaluate_handle(
                    "el => el.closest('.adm-space-item')"
                )
                if parent:
                    # 遍历相邻元素寻找文本
                    container = await parent.evaluate_handle("el => el.parentElement")
                    if container:
                        text = await container.evaluate("el => el.innerText")
                        # 文本通常包含 "选择城市" 和 城市名
                        parts = [
                            p.strip()
                            for p in text.split("\n")
                            if p.strip() and p.strip() != "选择城市"
                        ]
                        if parts:
                            return parts[0]
            return "未选择"
        except Exception:
            return "未选择"

    async def get_existing_task(self) -> LaborTask:
        """检查页面是否存在待处理的任务。"""
        try:
            # 提取任务详情
            checkin = await self._get_task_detail_text("入住时间")
            checkout = await self._get_task_detail_text("离店时间")
            hotel_name = await self._get_task_detail_text("酒店名称")

            # 日期清理：提取 YYYY-MM-DD
            date_pattern = r"\d{4}-\d{2}-\d{2}"
            if checkin:
                m = re.search(date_pattern, checkin)
                checkin = m.group(0) if m else checkin
            if checkout:
                m = re.search(date_pattern, checkout)
                checkout = m.group(0) if m else checkout

            if checkin and checkout and hotel_name:
                logger.info(
                    f"📍 发现待处理任务: {hotel_name} ({checkin} 至 {checkout})"
                )
                return LaborTask(
                    hotel_name=hotel_name,
                    checkin=checkin,
                    checkout=checkout,
                    state=TaskState.COMPLETE,
                )

            return LaborTask(state=TaskState.NO_TASK)
        except Exception as e:
            logger.error(f"获取任务详情异常: {e}")
            return LaborTask(state=TaskState.NO_TASK)

    async def select_any_city_with_tasks(self) -> bool:
        """轮询所有城市，选择第一个有题目的城市。如果点击失败则尝试下一个城市。"""
        try:
            if not await self.is_visible(self.SELECT_CITY_BUTTON):
                return False

            await self.page.click(self.SELECT_CITY_BUTTON)
            await asyncio.sleep(1.0)

            # 等待城市列表弹窗出现
            popup = self.page.locator(".adm-popup-body")
            try:
                await popup.wait_for(state="visible", timeout=5000)
            except Exception:
                logger.warning("城市选择弹窗未出现")
                return False

            # 使用 Locator 而不是 ElementHandle，更稳定
            city_items = self.page.locator("a.adm-check-list-item")
            count = await city_items.count()
            logger.debug(f"找到 {count} 个城市选项")

            # 收集所有有题目的城市
            valid_cities = []
            for i in range(count):
                item = city_items.nth(i)
                content = item.locator(".adm-list-item-content-main")

                if await content.count() > 0:
                    text = await content.inner_text()
                    # 跳过"暂无题目"的城市
                    if "暂无题目" not in text:
                        valid_cities.append((i, text.strip()))

            if not valid_cities:
                logger.warning("所有城市均暂无题目")
                await self._close_popup()
                return False

            logger.info(f"找到 {len(valid_cities)} 个有题目的城市: {[c[1] for c in valid_cities]}")

            # 依次尝试每个有题目的城市
            for city_index, city_name in valid_cities:
                logger.info(f"🔄 尝试选择城市: {city_name}")

                # 尝试点击该城市
                click_success = await self._try_click_city(city_items.nth(city_index), city_name, popup)

                if click_success:
                    logger.info(f"✅ 成功选择城市: {city_name}")
                    return True
                else:
                    logger.warning(f"❌ 点击城市 {city_name} 失败，尝试下一个城市...")
                    # 确保弹窗仍然打开，以便选择下一个城市
                    await self._ensure_popup_open(popup)

            # 所有城市都点击失败
            logger.warning("所有有题目的城市都点击失败")
            await self._close_popup()
            return False

        except Exception as e:
            logger.error(f"轮询城市失败: {e}")
            await self._close_popup()
            return False

    async def _try_click_city(self, item, city_name: str, popup) -> bool:
        """尝试点击指定城市项，返回是否成功。"""
        # 尝试点击城市项，最多重试3次
        for click_attempt in range(3):
            try:
                # 确保元素可见并滚动到视图
                await item.scroll_into_view_if_needed()
                await asyncio.sleep(0.3)

                # 使用 force=True 强制点击，绕过可能的遮挡
                await item.click(force=True, timeout=3000)
                await asyncio.sleep(1.0)

                # 检查弹窗是否已关闭
                if await self._is_popup_closed(popup):
                    return True

                logger.debug(f"点击城市尝试 {click_attempt + 1} 失败，弹窗仍可见，重试...")

            except Exception as e:
                logger.debug(f"点击城市尝试 {click_attempt + 1} 异常: {e}")

        # 3次都失败，尝试用 JavaScript 直接触发点击
        logger.debug("常规点击失败，尝试 JavaScript 点击...")
        try:
            # 使用 JS 点击当前城市项
            city_keyword = city_name.split()[0] if city_name else ""
            await self.page.evaluate(f"""
                () => {{
                    const items = document.querySelectorAll('a.adm-check-list-item');
                    for (const item of items) {{
                        const content = item.querySelector('.adm-list-item-content-main');
                        if (content && content.innerText.includes('{city_keyword}')) {{
                            item.click();
                            break;
                        }}
                    }}
                }}
            """)
            await asyncio.sleep(1.5)

            if await self._is_popup_closed(popup):
                return True

        except Exception as e:
            logger.debug(f"JavaScript 点击失败: {e}")

        return False

    async def _is_popup_closed(self, popup) -> bool:
        """检查弹窗是否已关闭（多种判断方式）。"""
        # 方式1：检查 popup-body 是否隐藏
        try:
            await popup.wait_for(state="hidden", timeout=2000)
            return True
        except Exception:
            pass

        # 方式2：检查 mask 是否消失
        mask = self.page.locator(".adm-mask")
        if await mask.count() == 0 or not await mask.first.is_visible():
            return True

        # 方式3：检查 popup 的 display 样式
        try:
            is_hidden = await self.page.evaluate("""
                () => {
                    const popup = document.querySelector('.adm-popup-body');
                    if (!popup) return true;
                    const style = window.getComputedStyle(popup);
                    return style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0';
                }
            """)
            if is_hidden:
                return True
        except Exception:
            pass

        return False

    async def _ensure_popup_open(self, popup):
        """确保弹窗仍然打开，如果关闭则重新打开。"""
        try:
            # 检查弹窗是否仍然可见
            if await popup.count() > 0 and await popup.first.is_visible():
                return  # 弹窗仍然打开

            # 弹窗已关闭，需要重新打开
            logger.debug("弹窗已关闭，重新打开城市选择...")
            await asyncio.sleep(0.5)

            if await self.is_visible(self.SELECT_CITY_BUTTON):
                await self.page.click(self.SELECT_CITY_BUTTON)
                await asyncio.sleep(1.0)

                try:
                    await popup.wait_for(state="visible", timeout=3000)
                except Exception:
                    logger.warning("重新打开城市选择弹窗失败")

        except Exception as e:
            logger.debug(f"确保弹窗打开时发生异常: {e}")

    async def _close_popup(self):
        """关闭弹窗遮罩，确保完全关闭。"""
        max_attempts = 5

        for attempt in range(max_attempts):
            try:
                # 检查遮罩是否存在
                mask = self.page.locator(".adm-mask")
                popup = self.page.locator(".adm-popup")

                mask_visible = await mask.count() > 0 and await mask.first.is_visible()
                popup_visible = (
                    await popup.count() > 0 and await popup.first.is_visible()
                )

                if not mask_visible and not popup_visible:
                    logger.debug("弹窗已关闭")
                    return

                # 方法1：点击关闭按钮（如果有）
                close_btns = [
                    ".adm-popup-close-icon",
                    "button:has-text('关闭')",
                    "button:has-text('取消')",
                    ".adm-popup .adm-center-popup-close",
                ]
                for btn_selector in close_btns:
                    try:
                        btn = self.page.locator(btn_selector)
                        if await btn.count() > 0 and await btn.first.is_visible():
                            await btn.first.click(force=True)
                            await asyncio.sleep(0.3)
                            break
                    except Exception:
                        pass

                # 方法2：点击遮罩层
                if mask_visible:
                    try:
                        await mask.first.click(force=True)
                        await asyncio.sleep(0.5)
                        continue
                    except Exception:
                        pass

                # 方法3：按 ESC 键
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.3)

                # 方法4：点击页面空白区域
                try:
                    await self.page.mouse.click(10, 10)
                    await asyncio.sleep(0.3)
                except Exception:
                    pass

                # 方法5：JavaScript 强制隐藏弹窗
                try:
                    await self.page.evaluate("""
                        document.querySelectorAll('.adm-mask, .adm-popup').forEach(el => {
                            el.style.display = 'none';
                            el.remove();
                        });
                    """)
                    await asyncio.sleep(0.2)
                except Exception:
                    pass

            except Exception as e:
                logger.debug(f"关闭弹窗尝试 {attempt + 1} 失败: {e}")

        # 最后检查并警告
        try:
            mask = self.page.locator(".adm-mask")
            if await mask.count() > 0 and await mask.first.is_visible():
                logger.warning("弹窗遮罩仍然存在，尝试强制移除...")
                # 最后手段：强制移除 DOM
                await self.page.evaluate("""
                    document.querySelectorAll('.adm-mask, .adm-popup, .adm-popup-body').forEach(el => el.remove());
                """)
        except Exception:
            pass

    async def claim_task(
        self, max_attempts: int = 6, wait_seconds: int = 30
    ) -> LaborTask:
        """领取新任务（带重试机制）。

        当检测到当前城市无可领取的题目时：
        1. 等待指定秒数
        2. 刷新页面
        3. 重新选择有题目的城市
        4. 尝试领题

        重复上述循环最多指定次数。

        Args:
            max_attempts: 最大尝试次数，默认6次 (6次无题后停止)
            wait_seconds: 每次重试前的等待时间，默认30秒

        Returns:
            LaborTask 包含任务信息或 NO_TASK 状态
        """
        logger.info(
            f"🎯 开始领题流程 (最多 {max_attempts} 轮，每轮等待 {wait_seconds}s)"
        )

        for attempt in range(max_attempts):
            logger.info(f"📋 领题尝试 (第 {attempt + 1}/{max_attempts} 轮)")

            # 1. 检查是否已有挂起任务
            task = await self.get_existing_task()
            if task.is_complete:
                logger.info(f"✅ 发现已有任务: {task.hotel_name}")
                return task

            # 2. 如果领题按钮不可点击或不可见，说明可能需要废弃旧任务
            claim_btn = self.page.locator(self.CLAIM_BUTTON)
            try:
                if not await claim_btn.is_visible() or not await claim_btn.is_enabled():
                    logger.info("领题按钮不可用，尝试废弃当前任务状态")
                    await self.click_abandon_button()
                    await asyncio.sleep(2)
            except Exception:
                pass

            # 3. 轮流选择城市
            city_found = await self.select_any_city_with_tasks()

            if city_found:
                # 4. 点击领题
                await asyncio.sleep(0.3)
                if await self.click_claim_button():
                    await asyncio.sleep(0.5)
                    task = await self.get_existing_task()
                    if task.is_complete:
                        logger.info(f"✅ 成功领取任务: {task.hotel_name}")
                        return task

            # 5. 无题或领题失败，检查是否需要重试
            if attempt < max_attempts - 1:
                logger.info(f"⏳ 暂无可领题目，等待 {wait_seconds} 秒后刷新页面...")
                await asyncio.sleep(wait_seconds)

                # 6. 刷新页面
                try:
                    logger.info("🔄 刷新页面...")
                    await self.page.reload(wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.warning(f"页面刷新失败: {e}")
                    # 重试导航到做题页面
                    try:
                        await self.page.goto(
                            self.TASK_URL, wait_until="domcontentloaded", timeout=30000
                        )
                        await asyncio.sleep(2)
                    except Exception:
                        pass

        logger.warning(f"❌ 连续 {max_attempts} 次尝试均未领取到任务，停止重试")
        return LaborTask(state=TaskState.NO_TASK)

    async def click_claim_button(self) -> bool:
        """点击领题按钮。"""
        try:
            btn = self.page.locator(self.CLAIM_BUTTON)
            if await btn.is_visible():
                await btn.click()
                return True
            return False
        except Exception:
            return False

    async def click_abandon_button(self) -> bool:
        """点击废弃按钮。"""
        try:
            btn = self.page.locator(self.ABANDON_BUTTON)
            if await btn.is_visible():
                await btn.click()
                # 处理可能出现的确认弹窗
                await asyncio.sleep(1)
                confirm_btn = self.page.locator("button:has-text('确定')")
                if await confirm_btn.is_visible():
                    await confirm_btn.click()
                return True
            return False
        except Exception:
            return False

    async def discard_task(self, reason_text: str = "") -> bool:
        """废弃当前题目。

        流程：
        1. 点击"废弃"按钮
        2. 在废弃弹窗中点击"废弃原因"选择器
        3. 在底部选择器中选择第一个可用原因并点击"确定"
        4. 可选填写补充说明
        5. 点击"提交"按钮完成废弃

        Args:
            reason_text: 可选的额外补充说明

        Returns:
            True if discard successful
        """
        try:
            logger.info("🗑️ 开始废弃当前题目...")

            # Step 1: 点击废弃按钮
            abandon_btn = self.page.locator(self.ABANDON_BUTTON)
            if not await abandon_btn.is_visible():
                logger.warning("废弃按钮不可见")
                return False

            await abandon_btn.click()
            await asyncio.sleep(1.0)
            logger.debug("已点击废弃按钮")

            # Step 2: 等待废弃弹窗出现
            discard_dialog = self.page.locator(".adm-center-popup-body.adm-dialog-body")
            try:
                await discard_dialog.wait_for(state="visible", timeout=5000)
            except Exception:
                logger.warning("废弃弹窗未出现")
                return False

            # Step 3: 点击"废弃原因"选择器打开底部选择器
            reason_selector = self.page.locator(
                ".adm-form-item-label:has-text('废弃原因')"
            ).locator("xpath=ancestor::a[contains(@class, 'adm-list-item')]")

            if await reason_selector.count() == 0:
                # 备选选择器
                reason_selector = self.page.locator(
                    "a.adm-list-item:has(.adm-form-item-label:has-text('废弃原因'))"
                )

            if await reason_selector.count() > 0:
                await reason_selector.first.click()
                await asyncio.sleep(0.8)
                logger.debug("已点击废弃原因选择器")
            else:
                logger.warning("未找到废弃原因选择器")
                return False

            # Step 4: 等待底部 Picker 弹出并选择原因
            picker = self.page.locator(".adm-picker")
            try:
                await picker.wait_for(state="visible", timeout=3000)
            except Exception:
                logger.warning("废弃原因选择器未弹出")
                # 尝试继续，可能已经有默认选项

            # 选择器中滚动选择第一个原因（通常已经默认选中）
            # 直接点击"确定"按钮
            picker_confirm = self.page.locator(
                ".adm-picker-header-button:has-text('确定')"
            )
            if await picker_confirm.count() > 0:
                await picker_confirm.first.click()
                await asyncio.sleep(0.5)
                logger.debug("已选择废弃原因并确定")
            else:
                # 尝试其他确定按钮
                confirm_btn = self.page.locator("a.adm-picker-header-button").last
                if await confirm_btn.count() > 0:
                    await confirm_btn.click()
                    await asyncio.sleep(0.5)

            # Step 5: 填写补充说明（可选）
            if reason_text:
                extra_input = self.page.locator("input#extra")
                if await extra_input.count() > 0:
                    await extra_input.fill(reason_text)
                    await asyncio.sleep(0.3)
                    logger.debug(f"已填写补充说明: {reason_text}")

            # Step 6: 点击"提交"按钮完成废弃
            submit_btn = self.page.locator(
                ".adm-dialog-button:has-text('提交')"
            )
            if await submit_btn.count() == 0:
                submit_btn = self.page.locator(
                    ".adm-dialog-footer button:has-text('提交')"
                )

            if await submit_btn.count() > 0:
                await submit_btn.first.click()
                await asyncio.sleep(1.5)
                logger.info("✅ 废弃题目提交成功")
            else:
                logger.warning("未找到提交按钮")
                return False

            # Step 7: 处理可能的成功提示弹窗
            await asyncio.sleep(0.5)
            success_popup = self.page.locator(".adm-toast, .adm-dialog")
            if await success_popup.count() > 0:
                # 点击确定关闭弹窗
                ok_btn = self.page.locator("button:has-text('确定'), button:has-text('知道了')")
                if await ok_btn.count() > 0 and await ok_btn.first.is_visible():
                    await ok_btn.first.click()
                    await asyncio.sleep(0.5)

            logger.info("🗑️ 题目废弃流程完成")
            return True

        except Exception as e:
            logger.error(f"废弃题目失败: {e}")
            # 尝试关闭可能残留的弹窗
            await self._close_popup()
            return False

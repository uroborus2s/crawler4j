"""Labor task submit workflow module.

Handles submitting captured hotel data back to the Labor platform (劳保保).
Directly fills the captured JSON data into the submission form.
"""

import asyncio
import json
import random

from src.automation.workflows.base import BaseWorkflow
from src.utils.logger import logger


class LaborSubmitWorkflow(BaseWorkflow):
    """Workflow for submitting task results to the Labor platform (劳保保).

    直接将从携程采集的原始 JSON 数据填入劳保平台的文本框并提交。
    """

    # DOM 选择器 (基于 content.js 分析)
    TEXT_AREA = "textarea.adm-text-area-element"
    TEXT_AREA_CONTAINER = ".adm-text-area"
    SUBMIT_BUTTON = "button:has-text('提交')"
    CONFIRM_BUTTON = "button:has-text('确定')"
    CANCEL_BUTTON = "button:has-text('取消')"
    POPUP_CONTAINER = ".adm-center-popup-wrap"
    SUCCESS_INDICATOR = "text='完成', text='成功', text='提交成功'"

    async def _find_visible_textarea(self):
        """查找可见的文本框。

        Returns:
            文本框元素，未找到返回 None
        """
        try:
            # 优先使用精确选择器
            textarea = self.page.locator(self.TEXT_AREA)
            if await textarea.count() > 0 and await textarea.first.is_visible():
                return await textarea.first.element_handle()

            # 备用：通过容器查找
            container = self.page.locator(self.TEXT_AREA_CONTAINER)
            if await container.count() > 0 and await container.first.is_visible():
                return await container.first.locator("textarea").element_handle()

            return None
        except Exception:
            return None

    async def _fill_data(self, data: dict) -> bool:
        """将数据填入文本框。

        Args:
            data: 要填入的数据（必须是字典类型）

        Returns:
            True if filled successfully.
        """
        try:
            # 验证数据类型：只接受 dict 类型
            if not isinstance(data, dict):
                logger.error(f"❌ 数据类型错误: 期望 dict，实际为 {type(data).__name__}")
                return False

            # 转换为 JSON 字符串（使用紧凑格式减少大小）
            json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
            original_length = len(json_str)

            logger.info(f"准备填入数据，大小: {original_length} bytes")

            # 查找文本框
            textarea = await self._find_visible_textarea()
            if not textarea:
                logger.error("未找到可见的文本框")
                return False

            # 点击聚焦
            await textarea.click()
            await asyncio.sleep(0.1)

            # 优化策略：优先使用 JS 注入（最快），兼容 React
            success = await self._fill_smart(textarea, json_str)

            if not success:
                # 如果都失败了，最后尝试一次清空 + 原生 fill
                logger.warning("智能填入失败，尝试兜底 fill 方法")
                await textarea.fill("")
                await textarea.fill(json_str)
                success = True

            if not success:
                return False

            # 触发 input 和 change 事件（确保表单识别到变化）
            await textarea.dispatch_event("input")
            await textarea.dispatch_event("change")
            await asyncio.sleep(0.2)

            # 验证填入数据的完整性
            filled_value = await textarea.evaluate("el => el.value")
            if not await self._validate_filled_json(filled_value, original_length):
                logger.error("❌ 填入数据验证失败，数据不完整或格式错误")
                return False

            logger.info("✅ 数据已填入文本框并验证通过")
            return True

        except Exception as e:
            logger.error(f"填入数据失败: {e}")
            return False

    async def _validate_filled_json(self, filled_value: str, original_length: int) -> bool:
        """验证填入的 JSON 数据是否完整有效。

        Args:
            filled_value: 从 textarea 读取的值
            original_length: 原始 JSON 字符串长度

        Returns:
            True if JSON is valid and complete.
        """
        try:
            # 1. 长度检查：必须达到原始长度的 99%（几乎完全匹配）
            if len(filled_value) < original_length * 0.99:
                logger.warning(
                    f"数据长度不足: 填入 {len(filled_value)}, 原始 {original_length}, "
                    f"完成率 {len(filled_value) / original_length * 100:.1f}%"
                )
                return False

            # 2. JSON 格式验证：尝试解析
            json.loads(filled_value)
            logger.debug("JSON 格式验证通过")
            return True

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON 格式验证失败: {e}")
            return False
        except Exception as e:
            logger.error(f"数据验证异常: {e}")
            return False

    async def _fill_smart(
        self, textarea, json_str: str, chunk_size: int = 5000
    ) -> bool:
        """智能填入数据，优先使用 JS 注入，兼容 React 组件。

        注意：此方法仅负责填入数据，完整性验证由 _fill_data 方法的
        _validate_filled_json 统一处理。
        """
        try:
            expected_length = len(json_str)
            logger.info(f"使用 JavaScript 设置值，总长度: {expected_length}")

            # 方法1: React 兼容的 native setter 方式
            fill_result = await textarea.evaluate(
                """
                (el, value) => {
                    // 使用原生 setter 设置值
                    const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLTextAreaElement.prototype, 'value'
                    ).set;
                    nativeInputValueSetter.call(el, value);

                    // 触发 React 合成事件
                    const inputEvent = new Event('input', { bubbles: true, cancelable: true });
                    el.dispatchEvent(inputEvent);

                    const changeEvent = new Event('change', { bubbles: true, cancelable: true });
                    el.dispatchEvent(changeEvent);

                    return el.value.length;
                }
            """,
                json_str,
            )

            await asyncio.sleep(0.3)

            # 严格验证：必须完全匹配长度
            if fill_result and fill_result == expected_length:
                logger.info(f"通过 React 兼容方式设置值成功，长度: {fill_result}")
                return True
            elif fill_result:
                logger.warning(
                    f"JS 方式长度不匹配: 期望 {expected_length}, 实际 {fill_result}"
                )

            # 方法2: Playwright 原生 fill
            logger.debug("JavaScript 方式失败，尝试 Playwright fill")
            await textarea.fill(json_str)
            await asyncio.sleep(0.2)

            value = await textarea.evaluate("el => el.value")
            if len(value) == expected_length:
                logger.info(f"通过 Playwright fill 成功，长度: {len(value)}")
                return True
            elif len(value) > 0:
                logger.warning(
                    f"Playwright fill 长度不匹配: 期望 {expected_length}, 实际 {len(value)}"
                )

            # 方法3: 分块 type 输入（最后手段）
            logger.debug("fill 方式失败，尝试分块 type 输入")
            await textarea.click()
            await self.page.keyboard.press("Meta+a")  # 全选清空
            await asyncio.sleep(0.1)

            for i in range(0, len(json_str), chunk_size):
                chunk = json_str[i : i + chunk_size]
                await textarea.type(chunk, delay=0)
                if i + chunk_size < len(json_str):
                    await asyncio.sleep(0.02)  # 每块之间短暂等待

            await asyncio.sleep(0.2)
            value = await textarea.evaluate("el => el.value")
            logger.info(f"分块输入完成，长度: {len(value)} (期望: {expected_length})")

            # 分块输入允许略微误差（可能有编码问题），但仍需达到 99%
            return len(value) >= expected_length * 0.99

        except Exception as e:
            logger.error(f"填入数据失败: {e}")
            return False

    async def _click_submit(self) -> bool:
        """点击提交按钮。

        Returns:
            True if clicked successfully.
        """
        try:
            if await self.is_visible(self.SUBMIT_BUTTON, timeout=3000):
                # 检查按钮是否可用（未禁用）
                submit_btn = await self.page.query_selector(self.SUBMIT_BUTTON)
                if submit_btn:
                    is_disabled = await submit_btn.is_disabled()
                    if is_disabled:
                        logger.warning("提交按钮处于禁用状态")
                        return False

                    await asyncio.sleep(random.uniform(0.2, 0.5))
                    await submit_btn.click()
                    logger.info("点击提交按钮")
                    return True

            logger.warning("未找到提交按钮")
            return False

        except Exception as e:
            logger.error(f"点击提交按钮失败: {e}")
            return False

    async def _handle_confirm_popup(self) -> bool:
        """处理提交后的确认弹窗。

        Returns:
            True if confirmation handled successfully.
        """
        try:
            await asyncio.sleep(1.2)

            # 查找弹窗中的确定按钮
            popups = await self.page.query_selector_all(self.POPUP_CONTAINER)

            for popup in popups:
                if not await popup.is_visible():
                    continue

                # 在弹窗内查找确定按钮
                buttons = await popup.query_selector_all("button")
                for button in buttons:
                    text = await button.inner_text()
                    if "确定" in text.strip():
                        await button.click()
                        logger.info('点击确认弹窗"确定"按钮')
                        return True

            # 备用方案：直接查找页面上的确定按钮
            if await self.is_visible(self.CONFIRM_BUTTON, timeout=2000):
                await self.page.click(self.CONFIRM_BUTTON)
                logger.info("点击确认按钮")
                return True

            logger.warning("未找到确认弹窗")
            return False

        except Exception as e:
            logger.error(f"处理确认弹窗失败: {e}")
            return False

    async def _close_all_popups(self, button_text: str = "确定") -> int:
        """关闭所有弹窗。

        基于 content.js findPageCloseAllPopups() 分析。

        Args:
            button_text: 优先点击的按钮文本

        Returns:
            关闭的弹窗数量
        """
        closed_count = 0

        try:
            popups = await self.page.query_selector_all(self.POPUP_CONTAINER)

            for popup in popups:
                if not await popup.is_visible():
                    continue

                buttons = await popup.query_selector_all("button")
                target_button = None

                # 查找目标按钮
                for button in buttons:
                    span = await button.query_selector("span")
                    if span:
                        text = await span.inner_text()
                        text = text.replace(" ", "").strip()

                        if text == button_text:
                            target_button = button
                            break
                        elif text in ["确定", "取消"] and not target_button:
                            target_button = button

                if target_button:
                    await target_button.click()
                    closed_count += 1
                    await asyncio.sleep(0.3)

            return closed_count

        except Exception as e:
            logger.debug(f"关闭弹窗异常: {e}")
            return closed_count

    async def submit_not_found(self) -> bool:
        """提交“搜索不到”结果。"""
        logger.info("正在提交：搜索不到")
        try:
            # 1. 查找原因下拉框或按钮
            # (假设页面有特定按钮或下拉选项，根据实际 UI 调整选择器)
            # 这里先点击提交，看是否弹出原因选择
            if not await self._click_submit():
                return False

            await asyncio.sleep(1)
            # 处理可能的选项弹窗
            reason_opt = self.page.locator(
                "text='搜索不到', .adm-picker-view-item:has-text('搜索不到')"
            )
            if await reason_opt.count() > 0:
                await reason_opt.first.click()
                await asyncio.sleep(0.5)
                # 点击确定
                await self._close_all_popups("确定")
                return True
            return False
        except Exception as e:
            logger.error(f"提交搜索不到失败: {e}")
            return False

    async def submit_result(self, data: dict) -> bool:
        """提交任务结果。

        Args:
            data: 必须是有效的 dict 类型数据（从携程 API 捕获的原始数据）

        Returns:
            True if submission successful.
        """
        # 0. 确保页面处于前台
        try:
            await self.page.bring_to_front()
        except Exception:
            pass

        # 严格验证：只接受 dict 类型
        if not isinstance(data, dict):
            logger.error(f"❌ submit_result 只接受 dict 类型数据，收到: {type(data).__name__}")
            return False

        logger.info("开始提交任务结果...")

        try:
            # 1. 检查是否有未处理的弹窗
            await self._close_all_popups("确定")
            await asyncio.sleep(0.5)

            # 2. 填入数据（内部会验证 JSON 完整性）
            if not await self._fill_data(data):
                logger.error("❌ 数据填入失败，取消提交")
                return False

            # 3. 等待一下再提交（模拟人类行为）
            await asyncio.sleep(random.uniform(0.2, 0.5))

            # 4. 点击提交
            if not await self._click_submit():
                # 提交按钮可能禁用，尝试再次填入数据
                logger.info("提交按钮可能未激活，尝试重新触发表单")
                textarea = await self._find_visible_textarea()
                if textarea:
                    await textarea.dispatch_event("input")
                    await asyncio.sleep(0.5)

                    if not await self._click_submit():
                        return False

            # 5. 处理确认弹窗
            await asyncio.sleep(1.2)
            confirm_count = await self._close_all_popups("确定")

            # 6. 验证提交结果 (通过检测页面上的成功提示)
            try:
                # 等待一会儿看是否有成功提示
                success_msg = self.page.locator(self.SUCCESS_INDICATOR)
                await success_msg.first.wait_for(state="visible", timeout=5000)
                logger.info("✅ 检测到成功提示，任务提交确认")
                await self.screenshot("labor_submit_success")
                return True
            except Exception:
                if confirm_count > 0:
                    logger.info("未检测到具体成功提示，但已处理确认弹窗，假设成功")
                    return True
                else:
                    # 可能没有弹窗，检查是否有提交按钮已经消失或变为不可用
                    logger.warning("未检测到确认弹窗或成功提示，检查表单状态...")
                    submit_btn = await self.page.query_selector(self.SUBMIT_BUTTON)
                    if not submit_btn or await submit_btn.is_disabled():
                        return True
                    return False

        except Exception as e:
            logger.error(f"提交任务异常: {e}")
            await self.screenshot("labor_submit_error")
            return False

    async def check_and_submit_pending(self) -> bool:
        """检查是否有待提交的数据，如有则尝试补充提交。

        基于 content.js executeSupplementSubmit() 分析。
        用于处理页面刷新后残留的未提交数据。

        Returns:
            True if pending data was submitted.
        """
        try:
            textarea = await self._find_visible_textarea()
            if not textarea:
                return False

            content = await textarea.input_value()
            if not content:
                return False

            # 检查是否是有效的 JSON
            try:
                json.loads(content)
            except json.JSONDecodeError:
                return False

            # 检查提交按钮状态
            submit_btn = await self.page.query_selector(self.SUBMIT_BUTTON)
            if submit_btn and not await submit_btn.is_disabled():
                logger.info("检测到待提交数据，执行补充提交")
                return await self.submit_result(content)

            return False

        except Exception as e:
            logger.debug(f"检查待提交数据失败: {e}")
            return False

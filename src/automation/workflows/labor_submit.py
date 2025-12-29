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
    TEXT_AREA = ".adm-text-area-element"
    SUBMIT_BUTTON = "button:has-text('提交')"
    CONFIRM_BUTTON = "button:has-text('确定')"
    CANCEL_BUTTON = "button:has-text('取消')"
    POPUP_CONTAINER = ".adm-center-popup-wrap"
    
    async def _find_visible_textarea(self):
        """查找可见的文本框。
        
        Returns:
            文本框元素，未找到返回 None
        """
        try:
            textareas = await self.page.query_selector_all(self.TEXT_AREA)
            for textarea in textareas:
                if await textarea.is_visible():
                    return textarea
            return None
        except Exception:
            return None
    
    async def _fill_data(self, data: dict | str) -> bool:
        """将数据填入文本框。
        
        Args:
            data: 要填入的数据（字典或 JSON 字符串）
            
        Returns:
            True if filled successfully.
        """
        try:
            # 转换为 JSON 字符串
            if isinstance(data, dict):
                json_str = json.dumps(data, ensure_ascii=False, indent=2)
            else:
                json_str = str(data)
            
            # 查找文本框
            textarea = await self._find_visible_textarea()
            if not textarea:
                logger.error("未找到可见的文本框")
                return False
            
            # 清空并填入数据
            await textarea.fill("")
            await asyncio.sleep(0.2)
            await textarea.fill(json_str)
            
            # 触发 input 事件（确保表单识别到变化）
            await textarea.dispatch_event("input")
            await asyncio.sleep(0.3)
            
            logger.info("数据已填入文本框")
            return True
            
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
                        logger.info("点击确认弹窗\"确定\"按钮")
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
            reason_opt = self.page.locator("text='搜索不到', .adm-picker-view-item:has-text('搜索不到')")
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

    async def submit_result(self, data: dict | str | None) -> bool:
        """提交任务结果。"""
        if data is None:
            return await self.submit_not_found()
            
        logger.info("开始提交任务结果...")
        
        try:
            # 1. 检查是否有未处理的弹窗
            await self._close_all_popups("确定")
            await asyncio.sleep(0.5)
            
            # 2. 填入数据
            if not await self._fill_data(data):
                return False
            
            # 3. 等待一下再提交（模拟人类行为）
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
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
            
            if confirm_count > 0:
                logger.info("✅ 任务提交成功")
                return True
            else:
                # 可能没有弹窗，检查页面状态
                logger.warning("未检测到确认弹窗，检查提交状态...")
                await asyncio.sleep(2)
                
                # 检查是否有成功提示或任务信息已清空
                # 这里可以添加更多验证逻辑
                return True
                
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

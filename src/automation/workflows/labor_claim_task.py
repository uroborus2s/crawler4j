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
                if label_text in label_content.replace(" ", "").replace("\u00a0", "").strip():
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
                parent = await city_button.evaluate_handle("el => el.closest('.adm-space-item')")
                if parent:
                    # 遍历相邻元素寻找文本
                    container = await parent.evaluate_handle("el => el.parentElement")
                    if container:
                        text = await container.evaluate("el => el.innerText")
                        # 文本通常包含 "选择城市" 和 城市名
                        parts = [p.strip() for p in text.split("\n") if p.strip() and p.strip() != "选择城市"]
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
                logger.info(f"📍 发现待处理任务: {hotel_name} ({checkin} 至 {checkout})")
                await self.screenshot("labor_task_detected")
                return LaborTask(
                    hotel_name=hotel_name,
                    checkin=checkin,
                    checkout=checkout,
                    state=TaskState.COMPLETE
                )
            
            return LaborTask(state=TaskState.NO_TASK)
        except Exception as e:
            logger.error(f"获取任务详情异常: {e}")
            return LaborTask(state=TaskState.NO_TASK)

    async def select_any_city_with_tasks(self) -> bool:
        """轮询所有城市，选择第一个有题目的城市。"""
        try:
            if not await self.is_visible(self.SELECT_CITY_BUTTON):
                return False
            
            await self.page.click(self.SELECT_CITY_BUTTON)
            await asyncio.sleep(0.8)
            
            # 等待城市列表弹窗出现
            popup = self.page.locator(".adm-popup-body")
            try:
                await popup.wait_for(state="visible", timeout=3000)
            except Exception:
                logger.warning("城市选择弹窗未出现")
                return False
            
            # 查找所有城市列表项
            city_items = await self.page.query_selector_all("a.adm-check-list-item")
            for item in city_items:
                content = await item.query_selector(".adm-list-item-content-main")
                if content:
                    text = await content.inner_text()
                    # 跳过"暂无题目"的城市
                    if "暂无题目" in text:
                        continue
                    
                    city_name = text.strip()
                    logger.info(f"✅ 选择有题城市: {city_name}")
                    
                    # 尝试点击城市项，最多重试3次
                    for click_attempt in range(3):
                        await item.click()
                        await asyncio.sleep(0.8)
                        
                        # 检查弹窗是否已关闭
                        try:
                            # 等待弹窗消失
                            await popup.wait_for(state="hidden", timeout=2000)
                            logger.debug("城市选择成功，弹窗已关闭")
                            return True
                        except Exception:
                            # 弹窗还在，可能点击没成功，重试
                            logger.debug(f"点击城市尝试 {click_attempt + 1} 失败，重试...")
                            continue
                    
                    # 3次都失败，尝试强制关闭弹窗
                    await self._close_popup()
                    await asyncio.sleep(0.5)
                    
                    # 检查是否终于关闭了
                    mask = self.page.locator(".adm-mask")
                    if not (await mask.count() > 0 and await mask.first.is_visible()):
                        return True
                    
                    logger.warning("城市选择后弹窗未正常关闭")
                    return False
            
            logger.warning("所有城市均暂无题目")
            await self._close_popup()
            return False
        except Exception as e:
            logger.error(f"轮询城市失败: {e}")
            await self._close_popup()
            return False


    async def _close_popup(self):
        """关闭弹窗遮罩，确保完全关闭。"""
        max_attempts = 5
        
        for attempt in range(max_attempts):
            try:
                # 检查遮罩是否存在
                mask = self.page.locator(".adm-mask")
                popup = self.page.locator(".adm-popup")
                
                mask_visible = await mask.count() > 0 and await mask.first.is_visible()
                popup_visible = await popup.count() > 0 and await popup.first.is_visible()
                
                if not mask_visible and not popup_visible:
                    logger.debug("弹窗已关闭")
                    return
                
                # 方法1：点击遮罩层
                if mask_visible:
                    try:
                        await mask.first.click(force=True)  # force=True 强制点击
                        await asyncio.sleep(0.5)
                        continue
                    except Exception:
                        pass
                
                # 方法2：按 ESC 键
                await self.page.keyboard.press("Escape")
                await asyncio.sleep(0.3)
                
                # 方法3：点击页面空白区域
                try:
                    await self.page.mouse.click(10, 10)
                    await asyncio.sleep(0.3)
                except Exception:
                    pass
                
            except Exception as e:
                logger.debug(f"关闭弹窗尝试 {attempt + 1} 失败: {e}")
        
        # 最后检查并警告
        try:
            mask = self.page.locator(".adm-mask")
            if await mask.count() > 0 and await mask.first.is_visible():
                logger.warning("弹窗遮罩仍然存在，可能影响后续操作")
        except Exception:
            pass

    async def claim_task(self, max_attempts: int = 5) -> LaborTask:
        """领取新任务。"""
        logger.info("开始领题流程...")
        
        for attempt in range(max_attempts):
            # 1. 检查是否已有挂起任务
            task = await self.get_existing_task()
            if task.is_complete:
                return task
                
            # 2. 如果领题按钮不可点击或不可见，说明可能需要废弃旧任务
            claim_btn = self.page.locator(self.CLAIM_BUTTON)
            if not await claim_btn.is_visible() or not await claim_btn.is_enabled():
                logger.info("领题按钮不可用，尝试废弃当前任务状态")
                await self.click_abandon_button()
                await asyncio.sleep(2)
            
            # 3. 轮流选择城市
            if not await self.select_any_city_with_tasks():
                logger.warning("没有可领题目的城市，等待 3 秒重试...")
                await asyncio.sleep(3)
                continue
                
            # 4. 点击领题
            await asyncio.sleep(0.2)
            if await self.click_claim_button():
                await asyncio.sleep(0.2)
                task = await self.get_existing_task()
                if task.is_complete:
                    await self.screenshot("labor_task_claimed_success")
                    return task
            
            await asyncio.sleep(2)
            
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

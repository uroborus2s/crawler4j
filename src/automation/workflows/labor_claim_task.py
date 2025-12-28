"""Labor task claim workflow module.

Handles claiming (taking) a new task from the Labor platform (劳保保).
Based on content.js executePageTask() analysis.
"""

import asyncio
import random
from typing import List

from playwright.async_api import Page

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
    
    async def _get_task_detail_text(self, label_text: str) -> str | None:
        """从页面 DOM 中提取任务详情文本。
        
        基于 content.js 第 2436-2455 行 findPageTaskDetailText() 分析。
        
        Args:
            label_text: 标签文本（如 '入住时间', '酒店名称'）
            
        Returns:
            对应的值文本，未找到返回 None
        """
        try:
            items = await self.page.query_selector_all(self.FORM_ITEM)
            
            for item in items:
                label = await item.query_selector(self.FORM_LABEL)
                if not label:
                    continue
                    
                label_content = await label.inner_text()
                # 移除空格进行匹配
                if label_content.replace(" ", "").replace("\u00a0", "").strip() == label_text:
                    value_span = await item.query_selector(self.FORM_VALUE)
                    if value_span:
                        text = await value_span.inner_text()
                        return text.replace(" ", "").replace("\u00a0", "").strip()
            
            return None
            
        except Exception as e:
            logger.debug(f"提取任务详情失败 ({label_text}): {e}")
            return None
    
    async def _get_current_city(self) -> str:
        """获取当前选择的城市名称。
        
        Returns:
            当前城市名称，未选择返回 "未选择"
        """
        try:
            # 查找"选择城市"按钮所在的容器
            city_button = await self.page.query_selector(self.SELECT_CITY_BUTTON)
            if city_button:
                # 向上查找容器，获取相邻的城市名称元素
                parent = await city_button.evaluate_handle("el => el.closest('.adm-space-item')")
                if parent:
                    next_sibling = await parent.evaluate_handle("el => el.nextElementSibling")
                    if next_sibling:
                        city_text = await next_sibling.inner_text()
                        return city_text.strip() if city_text else "未选择"
            
            return "未选择"
            
        except Exception as e:
            logger.debug(f"获取当前城市失败: {e}")
            return "未选择"
    
    async def _get_daily_output(self) -> int:
        """获取当日产量数字。
        
        Returns:
            当日产量，解析失败返回 -1
        """
        try:
            spans = await self.page.query_selector_all("span")
            for span in spans:
                text = await span.inner_text()
                if "当日产量" in text:
                    # 格式: "当日产量：5"
                    num_str = text.replace("当日产量：", "").replace("当日产量:", "").strip()
                    return int(num_str)
            return -1
        except Exception:
            return -1
    
    async def get_existing_task(self) -> LaborTask:
        """检查页面是否存在待处理的任务。
        
        基于 content.js 第 2463-2581 行 findPageExistingTaskDetails() 分析。
        
        Returns:
            LaborTask 对象，包含任务状态和详情
        """
        try:
            # 获取城市
            city_name = await self._get_current_city()
            
            # 提取任务详情
            checkin = await self._get_task_detail_text("入住时间")
            checkout = await self._get_task_detail_text("离店时间")
            hotel_name = await self._get_task_detail_text("酒店名称")
            hotel_id = await self._get_task_detail_text("酒店id")
            
            # 判断任务状态
            if checkin and checkout and hotel_name and hotel_id:
                # 所有信息完整
                logger.info(f"题目信息: {hotel_name}，{checkin}~{checkout}")
                return LaborTask(
                    hotel_name=hotel_name,
                    hotel_id=hotel_id,
                    checkin=checkin,
                    checkout=checkout,
                    city_name=city_name,
                    state=TaskState.COMPLETE
                )
            
            if not checkin and not checkout and not hotel_name and not hotel_id:
                # 无任务
                return LaborTask(city_name=city_name, state=TaskState.NO_TASK)
            
            if checkin and checkout and hotel_name and not hotel_id:
                # 有任务但缺少酒店ID
                logger.warning(f"任务信息不完整，缺少酒店ID: {hotel_name}")
                return LaborTask(
                    hotel_name=hotel_name,
                    hotel_id=None,
                    checkin=checkin,
                    checkout=checkout,
                    city_name=city_name,
                    state=TaskState.MISSING_ID
                )
            
            # 其他情况视为无任务
            return LaborTask(city_name=city_name, state=TaskState.NO_TASK)
            
        except Exception as e:
            logger.error(f"获取任务详情异常: {e}")
            return LaborTask(state=TaskState.NO_TASK)
    
    async def click_claim_button(self) -> bool:
        """点击领题按钮。
        
        Returns:
            True if clicked successfully.
        """
        try:
            if await self.is_visible(self.CLAIM_BUTTON, timeout=3000):
                await asyncio.sleep(random.uniform(0.2, 0.5))
                await self.page.click(self.CLAIM_BUTTON)
                logger.info("点击\"领题\"按钮")
                return True
            else:
                logger.warning("未找到领题按钮")
                return False
        except Exception as e:
            logger.error(f"点击领题按钮失败: {e}")
            return False
    
    async def click_abandon_button(self) -> bool:
        """点击废弃按钮（用于无法处理的任务）。
        
        Returns:
            True if clicked successfully.
        """
        try:
            if await self.is_visible(self.ABANDON_BUTTON, timeout=3000):
                await self.page.click(self.ABANDON_BUTTON)
                logger.info("点击\"废弃\"按钮")
                await asyncio.sleep(1)
                return True
            return False
        except Exception as e:
            logger.error(f"点击废弃按钮失败: {e}")
            return False
    
    async def select_city(self, preferred_cities: List[str] | None = None) -> bool:
        """选择城市。
        
        Args:
            preferred_cities: 优先选择的城市列表
            
        Returns:
            True if city selected successfully.
        """
        try:
            # 点击"选择城市"按钮
            if not await self.is_visible(self.SELECT_CITY_BUTTON, timeout=3000):
                logger.warning("未找到选择城市按钮")
                return False
            
            await self.page.click(self.SELECT_CITY_BUTTON)
            logger.info("打开城市选择列表")
            await asyncio.sleep(1.5)
            
            # 获取可用城市列表（排除"暂无题目"的城市）
            city_items = await self.page.query_selector_all(self.CITY_LIST_ITEM)
            available_cities = []
            
            for item in city_items:
                content = await item.query_selector(self.CITY_CONTENT)
                if content:
                    text = await content.inner_text()
                    if "暂无题目" not in text:
                        city_name = text.replace("暂无题目", "").strip()
                        available_cities.append((city_name, item))
            
            if not available_cities:
                logger.warning("没有可用的城市（所有城市暂无题目）")
                # 关闭弹窗
                await self._close_popup()
                return False
            
            # 选择城市：优先匹配 preferred_cities，否则选第一个
            selected_item = None
            selected_name = ""
            
            if preferred_cities:
                for pref_city in preferred_cities:
                    for city_name, item in available_cities:
                        if pref_city in city_name or city_name in pref_city:
                            selected_item = item
                            selected_name = city_name
                            break
                    if selected_item:
                        break
            
            if not selected_item:
                selected_name, selected_item = available_cities[0]
            
            # 点击选择
            await selected_item.click()
            logger.info(f"选择城市: {selected_name}")
            
            await asyncio.sleep(1.5)
            await self._close_popup()
            
            return True
            
        except Exception as e:
            logger.error(f"选择城市失败: {e}")
            await self._close_popup()
            return False
    
    async def _close_popup(self):
        """关闭弹窗遮罩。"""
        try:
            if await self.is_visible(self.POPUP_MASK, timeout=1000):
                await self.page.click(self.POPUP_MASK)
                await asyncio.sleep(0.5)
        except Exception:
            pass
    
    async def claim_task(self, max_attempts: int = 3, preferred_cities: List[str] | None = None) -> LaborTask:
        """领取新任务的完整流程。
        
        流程：
        1. 检查是否已有任务
        2. 如无任务，检查城市是否已选择
        3. 点击领题按钮
        4. 等待并获取任务信息
        
        Args:
            max_attempts: 最大尝试次数
            preferred_cities: 优先城市列表
            
        Returns:
            LaborTask 对象
        """
        logger.info("开始领取任务...")
        
        for attempt in range(max_attempts):
            try:
                # 等待页面稳定
                await asyncio.sleep(2)
                
                # 获取当前城市
                city_name = await self._get_current_city()
                logger.info(f"当前城市: {city_name}")
                
                # 获取当日产量
                daily_output = await self._get_daily_output()
                if daily_output >= 0:
                    logger.info(f"当日产量: {daily_output}")
                
                # 检查是否已有任务
                task = await self.get_existing_task()
                
                if task.is_complete:
                    logger.info(f"已有完整任务: {task}")
                    return task
                
                if task.state == TaskState.MISSING_ID:
                    logger.warning("任务缺少酒店ID，尝试废弃并重新领取")
                    await self.click_abandon_button()
                    await asyncio.sleep(2)
                    continue
                
                # 无任务，检查城市
                if city_name == "未选择":
                    logger.info("需要先选择城市")
                    if not await self.select_city(preferred_cities):
                        logger.warning("选择城市失败")
                        await asyncio.sleep(2)
                        continue
                
                # 点击领题
                if await self.click_claim_button():
                    await asyncio.sleep(3)
                    
                    # 检查是否成功领取
                    task = await self.get_existing_task()
                    if task.is_complete:
                        return task
                    
                    # 领取后仍无任务，可能需要切换城市
                    if task.is_empty and attempt < max_attempts - 1:
                        logger.info("当前城市无任务，尝试切换城市")
                        await self.select_city(preferred_cities)
                        continue
                
            except Exception as e:
                logger.error(f"领取任务尝试 {attempt + 1} 失败: {e}")
                await asyncio.sleep(2)
        
        logger.warning(f"领取任务失败，已尝试 {max_attempts} 次")
        return LaborTask(state=TaskState.NO_TASK)

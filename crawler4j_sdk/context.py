"""TaskContext - 任务执行上下文。

提供脚本可访问的所有能力。
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page

    from crawler4j_sdk.db import DataService


@dataclass
class HttpClient:
    """HTTP客户端封装
    
    提供简化的HTTP请求方法。
    """
    
    async def get(self, url: str, **kwargs: Any) -> dict:
        """发送GET请求

        Args:
            url (str): 请求URL
            **kwargs (Any): 传递给 session.get 的额外参数
        """
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, **kwargs) as resp:
                return await resp.json()
    
    async def post(self, url: str, data: dict | None = None, **kwargs: Any) -> dict:
        """发送POST请求

        Args:
            url (str): 请求URL
            data (dict | None): JSON数据
            **kwargs (Any): 传递给 session.post 的额外参数
        """
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, **kwargs) as resp:
                return await resp.json()

@dataclass
class CtripAccountInfo:
    """携程账号信息（只读）"""
    id: int
    phone_number: str
    country_code: str = "+86"


@dataclass
class LaborAccountInfo:
    """劳保账号信息（只读）"""
    id: int
    phone_number: str
    password: str


@dataclass
class TaskContext:
    """任务执行上下文
    
    脚本通过此对象访问框架提供的所有能力。
    
    Attributes:
        env_id: 环境ID
        task_name: 当前任务名称
        config: 任务配置（JSON解析后的字典）
        page: Playwright Page对象
        context: Playwright BrowserContext对象
        logger: 日志记录器
        http: HTTP客户端
        db: 数据库服务
        ctrip_account: 携程账号信息
        labor_account: 劳保账号信息
        captured_data: 捕获的数据列表
        state: 任务状态字典（跨方法/子任务共享）
        input_callback: 输入回调（用于手动模式）
    """
    
    # 基础信息
    env_id: int
    task_name: str
    config: dict = field(default_factory=dict)
    
    # 浏览器
    page: "Page | None" = None
    context: "BrowserContext | None" = None
    
    # 日志
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("task"))
    
    # HTTP
    http: HttpClient = field(default_factory=HttpClient)
    
    # 数据服务
    db: "DataService | None" = None
    
    # 账号信息
    ctrip_account: CtripAccountInfo | None = None
    labor_account: LaborAccountInfo | None = None
    
    # 数据
    captured_data: list = field(default_factory=list)
    state: dict = field(default_factory=dict)
    
    # 输入回调（手动模式）
    input_callback: Callable | None = None
    
    # 停止标志
    _stop_requested: bool = field(default=False, repr=False)
    
    # 子任务执行器（由框架注入）
    _subtask_executor: Callable | None = field(default=None, repr=False)
    
    # === 工具方法 ===
    
    async def wait(self, seconds: float) -> None:
        """等待指定秒数"""
        await asyncio.sleep(seconds)
    
    async def screenshot(self, name: str) -> str:
        """截图并保存
        
        Args:
            name: 截图名称（不含扩展名）
            
        Returns:
            截图保存路径
        """
        if not self.page:
            raise RuntimeError("Page未初始化")
        
        from datetime import datetime
        from pathlib import Path
        
        screenshots_dir = Path("screenshots")
        screenshots_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = screenshots_dir / f"{name}_{timestamp}.png"
        
        await self.page.screenshot(path=str(path))
        self.logger.info(f"📸 截图已保存: {path}")
        
        return str(path)
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项
        
        Args:
            key: 配置键
            default: 默认值
            
        Returns:
            配置值
        """
        return self.config.get(key, default)
    
    # === 工作流编排方法 ===
    
    def should_stop(self) -> bool:
        """检查是否应该停止执行
        
        用于工作流循环中的停止检查。
        
        Returns:
            True 如果已请求停止
        """
        return self._stop_requested
    
    def request_stop(self) -> None:
        """请求停止当前工作流"""
        self._stop_requested = True
        self.logger.info("已请求停止工作流")
    
    async def run_subtask(self, task_name: str, **kwargs: Any) -> Any:
        """执行子任务
        
        在复合任务中调用其他原子任务。
        子任务共享同一个 ctx.state。
        
        Args:
            task_name (str): 子任务名称
            **kwargs (Any): 传递给子任务的额外参数（会合并到 ctx.state）
            
        Returns:
            子任务的返回值（TaskResult.data）
        """
        if not self._subtask_executor:
            raise RuntimeError("子任务执行器未注入，请确保通过框架运行")
        
        # 合并额外参数到 state
        if kwargs:
            self.state.update(kwargs)
        
        self.logger.info(f"▶ 执行子任务: {task_name}")
        result = await self._subtask_executor(task_name, self)
        
        if result and hasattr(result, 'data'):
            return result.data
        return result


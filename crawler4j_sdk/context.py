"""TaskContext 任务执行上下文。

本模块定义了 Crawler4j SDK 的核心契约之一：TaskContext（执行上下文与能力注入）。
TaskContext 是 SDK 的"能力总线"：脚本不直接依赖运行时内部对象，而是只依赖 TaskContext 提供的稳定能力。

稳定契约 (Stable API - 同 MAJOR 版本内冻结):
    - 字段: env_id, task_name, config, page, context, logger, http, db, captured_data, state
    - 方法: wait, screenshot, get_config, request_stop, should_stop, run_subtask

参考规格: docs/srs/06-sdk/06-3-taskcontext.md
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page

    from crawler4j_sdk.db import DataService


# === HTTP 客户端协议 ===

@runtime_checkable
class HttpClient(Protocol):
    """HTTP 客户端协议。
    
    定义了 TaskContext.http 的能力接口。
    运行时可注入任何符合此协议的实现（aiohttp、httpx 等）。
    """
    
    async def get(self, url: str, **kwargs: Any) -> dict[str, Any]:
        """发送 GET 请求。
        
        Args:
            url: 请求 URL。
            **kwargs: 额外参数（headers、timeout 等）。
        
        Returns:
            JSON 解析后的响应字典。
        """
        ...
    
    async def post(
        self, 
        url: str, 
        data: dict[str, Any] | None = None, 
        **kwargs: Any
    ) -> dict[str, Any]:
        """发送 POST 请求。
        
        Args:
            url: 请求 URL。
            data: JSON 数据体。
            **kwargs: 额外参数（headers、timeout 等）。
        
        Returns:
            JSON 解析后的响应字典。
        """
        ...


# === 默认 HTTP 客户端实现 ===

@dataclass
class DefaultHttpClient:
    """默认 HTTP 客户端实现，基于 aiohttp。
    
    Note:
        每次请求创建新 session，适合简单场景。
        高并发场景建议运行时注入复用 session 的实现。
    """
    
    async def get(self, url: str, **kwargs: Any) -> dict[str, Any]:
        """发送 GET 请求。"""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url, **kwargs) as resp:
                return await resp.json()
    
    async def post(
        self, 
        url: str, 
        data: dict[str, Any] | None = None, 
        **kwargs: Any
    ) -> dict[str, Any]:
        """发送 POST 请求。"""
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data, **kwargs) as resp:
                return await resp.json()


# === 任务执行上下文 ===

@dataclass
class TaskContext:
    """任务执行上下文。
    
    脚本通过此对象访问框架提供的所有能力。
    TaskContext 是 SDK 的"能力总线"，脚本不直接依赖运行时内部对象。
    
    基础字段 (Stable):
        env_id: 环境 ID，用于日志前缀、数据隔离等。
        task_name: 当前任务名（TaskScript.name）。
        config: 任务配置（JSON 解析后的字典）。
    
    浏览器能力 (Stable):
        page: Playwright Page 对象，可为 None。
        context: Playwright BrowserContext 对象，可为 None。
    
    日志能力 (Stable):
        logger: 日志记录器，脚本用此输出业务日志。
    
    HTTP 能力 (Stable):
        http: HTTP 客户端，提供 get/post 等方法。
    
    数据能力 (Stable):
        db: 数据服务聚合入口，允许为 None，使用前需判空。
    
    共享状态 (Stable):
        state: 跨方法/子任务共享的"工作内存"，仅存 JSON 可序列化值。
        captured_data: 抓取/提取的原始数据集合。
    
    安全与最小权限:
        - TaskContext 只注入脚本"需要的最小能力集合"
        - 日志中不得输出密码、Cookie、Token 等机密
        - 对手机号、身份证等 PII 应脱敏
    
    示例:
        >>> async def execute(self, ctx: TaskContext) -> TaskResult:
        ...     # 使用浏览器
        ...     await ctx.page.goto("https://example.com")
        ...     
        ...     # 使用配置
        ...     timeout = ctx.get_config("timeout", 30)
        ...     
        ...     # 使用日志
        ...     ctx.logger.info("开始处理")
        ...     
        ...     # 使用 HTTP
        ...     data = await ctx.http.get("https://api.example.com/data")
        ...     
        ...     # 共享状态
        ...     ctx.state["phase"] = "search"
        ...     
        ...     # 调用子任务
        ...     result = await ctx.run_subtask("sub_task", param=123)
    """
    
    # === 基础信息 (Stable) ===
    
    env_id: int
    """环境 ID，用于日志前缀、数据隔离等。"""
    
    task_name: str
    """当前任务名（TaskScript.name / TaskFlow.name）。"""
    
    config: dict[str, Any] = field(default_factory=dict)
    """任务配置（JSON 解析后的字典），由运行时注入。"""
    
    # === 浏览器能力 (Stable) ===
    
    page: "Page | None" = None
    """Playwright Page 对象。
    
    Note:
        - 可为 None，取决于运行模式（非浏览器任务可能没有）
        - 访问前应判空或在契约中声明必须运行在 Browser 模式
    """
    
    context: "BrowserContext | None" = None
    """Playwright BrowserContext 对象。
    
    Note:
        可为 None，取决于运行模式。
    """
    
    # === 日志能力 (Stable) ===
    
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("task"))
    """日志记录器。
    
    Note:
        - 脚本用此输出业务日志，不得假设全局 logger 名称
        - 日志信息包含敏感内容时必须脱敏
    """
    
    # === HTTP 能力 (Stable) ===
    
    http: HttpClient = field(default_factory=DefaultHttpClient)
    """HTTP 客户端，提供 get/post 等方法。
    
    Note:
        调用方应显式传入 timeout、headers 等，不得无限等待。
    """
    
    # === 数据能力 (Stable) ===
    
    db: "DataService | None" = None
    """数据服务聚合入口。
    
    Note:
        - 允许为 None，使用前需判空或调用 db.is_available()
        - 聚合 accounts/storage/tasks 等子服务
    """
    
    # === 共享状态与数据 (Stable) ===
    
    captured_data: list[Any] = field(default_factory=list)
    """抓取/提取的原始数据集合，用于结果汇总或持久化。
    
    Note:
        包含敏感信息时必须脱敏或仅存引用。
    """
    
    state: dict[str, Any] = field(default_factory=dict)
    """跨方法/子任务共享的"工作内存"。
    
    约定保留键（建议）:
        - state["phase"]: 当前阶段
        - state["cursor"]: 游标/分页信息
        - state["artifacts"]: 输出物引用
        - state["inputs"]: 关键输入快照（脱敏后）
    
    Note:
        - 仅存放 JSON 可序列化值
        - 不要把 Page/Context/Logger/DB 等对象塞入
        - 可恢复信息建议同步写入 db/storage
    """
    
    # === 内部字段 (Non-stable) ===
    
    _stop_requested: bool = field(default=False, repr=False)
    """停止标志，内部使用。"""
    
    _subtask_executor: Callable[..., Any] | None = field(default=None, repr=False)
    """子任务执行器，由运行时注入。"""
    
    # === 工具方法 (Stable) ===
    
    async def wait(self, seconds: float) -> None:
        """等待指定秒数。
        
        Args:
            seconds: 等待时间（秒）。
        
        Example:
            >>> await ctx.wait(2.5)  # 等待 2.5 秒
        """
        await asyncio.sleep(seconds)
    
    async def screenshot(self, name: str) -> str:
        """截图并保存。
        
        Args:
            name: 截图名称（不含扩展名），不得包含敏感信息。
        
        Returns:
            截图保存路径字符串。
        
        Raises:
            RuntimeError: 当 Page 未初始化时。
        
        Example:
            >>> path = await ctx.screenshot("login_success")
            >>> ctx.logger.info(f"截图已保存: {path}")
        """
        if not self.page:
            raise RuntimeError("Page 未初始化，无法截图")
        
        screenshots_dir = Path("screenshots")
        screenshots_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = screenshots_dir / f"{name}_{timestamp}.png"
        
        await self.page.screenshot(path=str(path))
        self.logger.info(f"📸 截图已保存: {path}")
        
        return str(path)
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """获取配置项（便捷方法）。
        
        Args:
            key: 配置键名。
            default: 键不存在时的默认值。
        
        Returns:
            配置值或默认值。
        
        Example:
            >>> timeout = ctx.get_config("timeout", 30)
            >>> retry_count = ctx.get_config("retry", 3)
        """
        return self.config.get(key, default)
    
    # === 停止/取消 (Stable) ===
    
    def should_stop(self) -> bool:
        """检查是否应该停止执行。
        
        用于工作流循环中的停止检查，长循环必须周期性调用。
        
        Returns:
            True 如果已请求停止。
        
        Example:
            >>> while not ctx.should_stop():
            ...     # 处理任务
            ...     pass
        """
        return self._stop_requested
    
    def request_stop(self) -> None:
        """请求停止当前工作流。
        
        设置停止标志，工作流在下次 should_stop() 检查时会退出。
        
        Example:
            >>> if error_count > 3:
            ...     ctx.request_stop()
        """
        self._stop_requested = True
        self.logger.info("已请求停止工作流")
    
    # === 子任务调用 (Stable) ===
    
    async def run_subtask(self, task_name: str, **kwargs: Any) -> Any:
        """执行子任务。
        
        在工作流中调用其他原子任务。子任务共享同一个 ctx.state。
        
        Args:
            task_name: 子任务名称（TaskScript.name）。
            **kwargs: 传递给子任务的额外参数，会合并到 ctx.state。
        
        Returns:
            子任务的返回值（TaskResult.data）。
        
        Raises:
            RuntimeError: 当子任务执行器未注入时（未通过框架运行）。
        
        Example:
            >>> # 调用登录子任务
            >>> await ctx.run_subtask("login")
            >>> 
            >>> # 传递参数给子任务
            >>> task_data = await ctx.run_subtask("claim_task")
            >>> result = await ctx.run_subtask("search", task=task_data)
        """
        if not self._subtask_executor:
            raise RuntimeError("子任务执行器未注入，请确保通过框架运行")
        
        # 合并额外参数到 state（共享给子任务）
        if kwargs:
            self.state.update(kwargs)
        
        self.logger.info(f"▶ 执行子任务: {task_name}")
        result = await self._subtask_executor(task_name, self)
        
        # 返回 TaskResult.data
        if result and hasattr(result, 'data'):
            return result.data
        return result

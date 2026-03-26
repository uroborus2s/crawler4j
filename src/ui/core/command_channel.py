"""Core-UI 命令通道。

规格参考: docs/02-requirements/reference-srs/05-framework-core/05-5-ui-host-microfrontend.md (5.5.3.2)

UI → Core 的交互通过"命令通道"完成：
    - 幂等与可重试
    - 统一错误结构
"""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Awaitable, Callable

from PyQt6.QtCore import QObject, pyqtSignal


class CommandResult(StrEnum):
    """命令执行结果。"""
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class CommandResponse:
    """命令响应。
    
    规格 5.5.3.2: 统一错误结构
        - code: 状态码
        - message: 消息
        - hint: 修复建议
        - correlation_id: 关联ID
    """
    result: CommandResult = CommandResult.SUCCESS
    code: str = "OK"
    message: str = ""
    hint: str = ""
    data: Any = None
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    
    @classmethod
    def success(cls, data: Any = None, message: str = "") -> "CommandResponse":
        return cls(
            result=CommandResult.SUCCESS,
            data=data,
            message=message,
        )
    
    @classmethod
    def error(cls, code: str, message: str, hint: str = "") -> "CommandResponse":
        return cls(
            result=CommandResult.ERROR,
            code=code,
            message=message,
            hint=hint,
        )


class CommandChannel(QObject):
    """命令通道。
    
    规格 5.5.3.2: UI → Core 命令通道
    
    提供 UI 调用 Core 功能的统一接口。
    
    Usage:
        channel = CommandChannel()
        
        # 同步调用
        response = channel.execute("module.list")
        
        # 异步调用
        channel.execute_async("task.submit", {"module": "ctrip"})
    """
    
    # 信号：命令完成
    command_completed = pyqtSignal(str, object)  # (correlation_id, response)
    
    def __init__(self):
        super().__init__()
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._async_handlers: dict[str, Callable[..., Awaitable[Any]]] = {}
    
    def register(self, command: str, handler: Callable[..., Any]) -> None:
        """注册命令处理器。
        
        Args:
            command: 命令名（如 "module.list", "task.submit"）
            handler: 处理函数
        """
        self._handlers[command] = handler
    
    def register_async(self, command: str, handler: Callable[..., Awaitable[Any]]) -> None:
        """注册异步命令处理器。"""
        self._async_handlers[command] = handler
    
    def execute(self, command: str, params: dict[str, Any] | None = None) -> CommandResponse:
        """执行命令（同步）。
        
        Args:
            command: 命令名
            params: 命令参数
        
        Returns:
            命令响应
        """
        params = params or {}
        handler = self._handlers.get(command)
        if not handler:
            return CommandResponse.error(
                "COMMAND_NOT_FOUND",
                f"未知命令: {command}",
                "请检查命令名称是否正确"
            )
        
        try:
            result = handler(**params)
            return CommandResponse.success(data=result)
        except Exception as e:
            return CommandResponse.error(
                "EXECUTION_ERROR",
                str(e),
            )
    
    async def execute_async(
        self,
        command: str,
        params: dict[str, Any] | None = None,
    ) -> CommandResponse:
        """执行命令（异步）。"""
        params = params or {}
        
        handler = self._async_handlers.get(command)
        if not handler:
            # 尝试同步处理器
            return self.execute(command, params)
        
        try:
            result = await handler(**params)
            return CommandResponse.success(data=result)
        except Exception as e:
            return CommandResponse.error(
                "EXECUTION_ERROR",
                str(e),
            )


# === 预定义命令 ===

class CoreCommands:
    """Core 命令常量。"""
    # 模块管理
    MODULE_LIST = "module.list"
    MODULE_GET = "module.get"
    MODULE_ENABLE = "module.enable"
    MODULE_DISABLE = "module.disable"
    MODULE_REFRESH = "module.refresh"
    
    # 任务管理
    TASK_SUBMIT = "task.submit"
    TASK_STOP = "task.stop"
    TASK_GET = "task.get"
    TASK_LIST = "task.list"
    TASK_LIST_RECENT = "task.list_recent"
    
    # 环境管理
    ENV_LIST = "env.list"
    ENV_STATS = "env.stats"
    
    # 配置
    CONFIG_GET = "config.get"
    CONFIG_SET = "config.set"


# 全局单例
_channel: CommandChannel | None = None


def get_command_channel() -> CommandChannel:
    """获取全局 CommandChannel 实例。"""
    global _channel
    if _channel is None:
        _channel = CommandChannel()
    return _channel

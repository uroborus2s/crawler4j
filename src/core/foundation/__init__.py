"""Foundation Layer - 基础能力层。

提供与业务无关的通用底层能力：
- EventBus: 进程内事件总线
- Logging: 统一日志门面
- Network: 基础 HTTP 客户端封装
- Config: 配置管理 (由 persistence 提供)
"""

from src.core.foundation.event_bus import (
    Event,
    EventBus,
    EventType,
    get_event_bus,
)
from src.core.foundation.logging import (
    AppLogger,
    LogEntry,
    LogLevel,
    logger,
)
from src.core.foundation.network import (
    AsyncHttpClient,
)

__all__ = [
    # Event Bus
    "EventBus",
    "Event",
    "EventType",
    "get_event_bus",
    # Logging
    "AppLogger",
    "LogEntry",
    "LogLevel",
    "logger",
    # Network
    "AsyncHttpClient",
]

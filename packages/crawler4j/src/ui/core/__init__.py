"""UI Host 集成模块。

提供 UI Host 层与 Core 层的集成能力：
- CoreAdapter: UI ↔ Core 信号桥梁
- CommandChannel: UI → Core 命令通道

注意：EventBus 现在位于 Foundation 层 (src.core.foundation)
"""

from src.core.foundation import (
    Event,
    EventBus,
    EventType,
    get_event_bus,
)
from src.ui.core.adapter import (
    CoreAdapter,
    get_core_adapter,
)
from src.ui.core.command_channel import (
    CommandChannel,
    CommandResponse,
    CoreCommands,
    get_command_channel,
)

__all__ = [
    # 命令通道
    "CommandChannel",
    "CommandResponse",
    "CoreCommands",
    "get_command_channel",
    # 事件总线 (从 Foundation 重导出)
    "EventBus",
    "Event",
    "EventType",
    "get_event_bus",
    # Signal Bridge (适配器)
    "CoreAdapter",
    "get_core_adapter",
]

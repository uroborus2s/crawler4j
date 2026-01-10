"""UI Core 集成模块。

提供 UI 与 Core 的集成能力：
    - CommandChannel: UI → Core 命令通道
    - EventBus: Core → UI 事件总线
    - CoreAdapter: Core 适配器
"""

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
from src.ui.core.event_bus import (
    Event,
    EventBus,
    EventType,
    get_event_bus,
)

__all__ = [
    # 命令通道
    "CommandChannel",
    "CommandResponse",
    "CoreCommands",
    "get_command_channel",
    # 事件总线
    "EventBus",
    "Event",
    "EventType",
    "get_event_bus",
    # 适配器
    "CoreAdapter",
    "get_core_adapter",
]

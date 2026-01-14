"""事件总线 (Event Bus)。

规格参考: docs/srs/05-framework-core/05-5-ui-host-microfrontend.md (5.5.3.3)

进程内事件总线，实现模块间及层级间的解耦通信：
- Core → UI 事件传递
- 支持按 EventType / module_name / task_run_id 过滤订阅
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable

from PyQt6.QtCore import QObject, pyqtSignal


class EventType(StrEnum):
    """事件类型。"""
    # 任务事件
    TASK_STARTED = "task.started"
    TASK_PROGRESS = "task.progress"
    TASK_LOG = "task.log"
    TASK_FINISHED = "task.finished"
    TASK_FAILED = "task.failed"
    TASK_CANCELLED = "task.cancelled"
    
    # 任务配置事件
    TASK_CONFIG_CREATED = "task.config.created"
    TASK_CONFIG_UPDATED = "task.config.updated"
    TASK_CONFIG_DELETED = "task.config.deleted"
    
    # 模块事件
    MODULE_INSTALLED = "module.installed"
    MODULE_UNINSTALLED = "module.uninstalled"
    MODULE_UPGRADED = "module.upgraded"
    MODULE_REFRESHED = "module.refreshed"
    MODULE_ENABLED = "module.enabled"
    MODULE_DISABLED = "module.disabled"
    
    # 环境事件
    ENV_POOL_SATURATED = "env.pool_saturated"
    ENV_UNHEALTHY = "env.unhealthy"
    ENV_CREATED = "env.created"
    ENV_DESTROYED = "env.destroyed"


@dataclass
class Event:
    """事件数据。
    
    规格 5.5.3.3: 事件应支持按 module_name / task_run_id 过滤订阅。
    """
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)
    module_name: str | None = None
    task_run_id: str | None = None
    timestamp: int = field(default_factory=lambda: int(time.time()))
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])


class EventBus(QObject):
    """事件总线。
    
    规格 5.5.3.3: Core → UI 事件总线
    
    Usage:
        bus = EventBus()
        
        # 订阅事件
        bus.subscribe(EventType.TASK_FINISHED, on_task_finished)
        bus.subscribe_by_module("ctrip", on_ctrip_event)
        
        # 发布事件（由 Core 调用）
        bus.publish(Event(type=EventType.TASK_STARTED, task_run_id="xxx"))
    """
    
    # Qt 信号：用于跨线程安全传递
    event_emitted = pyqtSignal(object)  # Event
    
    def __init__(self):
        super().__init__()
        self._subscribers: dict[EventType, list[Callable[[Event], None]]] = {}
        self._module_subscribers: dict[str, list[Callable[[Event], None]]] = {}
        self._task_subscribers: dict[str, list[Callable[[Event], None]]] = {}
        
        # 连接信号到分发器
        self.event_emitted.connect(self._dispatch)
    
    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """订阅特定类型的事件。"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)
    
    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """取消订阅。"""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass
    
    def subscribe_by_module(self, module_name: str, handler: Callable[[Event], None]) -> None:
        """按模块订阅事件。"""
        if module_name not in self._module_subscribers:
            self._module_subscribers[module_name] = []
        self._module_subscribers[module_name].append(handler)
    
    def subscribe_by_task(self, task_run_id: str, handler: Callable[[Event], None]) -> None:
        """按任务订阅事件。"""
        if task_run_id not in self._task_subscribers:
            self._task_subscribers[task_run_id] = []
        self._task_subscribers[task_run_id].append(handler)
    
    def unsubscribe_by_task(self, task_run_id: str) -> None:
        """取消任务相关的所有订阅。"""
        self._task_subscribers.pop(task_run_id, None)
    
    def publish(self, event: Event) -> None:
        """发布事件。
        
        线程安全：通过 Qt 信号跨线程传递。
        """
        self.event_emitted.emit(event)
    
    def _dispatch(self, event: Event) -> None:
        """分发事件到订阅者。"""
        # 按类型分发
        for handler in self._subscribers.get(event.type, []):
            try:
                handler(event)
            except Exception:
                pass  # 不影响其他订阅者
        
        # 按模块分发
        if event.module_name:
            for handler in self._module_subscribers.get(event.module_name, []):
                try:
                    handler(event)
                except Exception:
                    pass
        
        # 按任务分发
        if event.task_run_id:
            for handler in self._task_subscribers.get(event.task_run_id, []):
                try:
                    handler(event)
                except Exception:
                    pass


# 全局单例
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """获取全局 EventBus 实例。"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus

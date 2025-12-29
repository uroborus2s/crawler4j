"""Event bus module.

Provides Qt signal/slot based event system for UI updates.
"""

from enum import Enum, auto
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal


class EventType(Enum):
    """Application event types."""
    
    # Scheduler events
    SCHEDULER_STARTED = auto()
    SCHEDULER_STOPPED = auto()
    SCHEDULER_PAUSED = auto()
    
    # Environment events
    ENVIRONMENT_CREATED = auto()
    ENVIRONMENT_STARTED = auto()
    ENVIRONMENT_STOPPED = auto()
    ENVIRONMENT_ERROR = auto()
    ENVIRONMENT_STATUS_CHANGED = auto()
    
    # Task events
    TASK_STARTED = auto()
    TASK_COMPLETED = auto()
    TASK_FAILED = auto()
    TASK_PROGRESS = auto()
    
    # Account events
    CTRIP_ACCOUNT_ADDED = auto()
    CTRIP_ACCOUNT_UPDATED = auto()
    CTRIP_ACCOUNT_BLACKLISTED = auto()
    LABOR_ACCOUNT_ADDED = auto()
    LABOR_ACCOUNT_UPDATED = auto()
    LABOR_STATS_UPDATED = auto()
    
    # Settings events
    SETTINGS_CHANGED = auto()
    BROWSER_TYPE_CHANGED = auto()
    CONCURRENCY_CHANGED = auto()
    
    # Connection events
    BROWSER_CONNECTED = auto()
    BROWSER_DISCONNECTED = auto()


class Event:
    """Application event container."""
    
    def __init__(
        self,
        event_type: EventType,
        data: Any = None,
        source: str | None = None,
    ):
        self.type = event_type
        self.data = data
        self.source = source
    
    def __repr__(self) -> str:
        return f"Event({self.type.name}, data={self.data}, source={self.source})"


class EventBus(QObject):
    """Central event bus for application-wide communication.
    
    Usage:
        bus = EventBus()
        
        # Subscribe to events
        bus.event_emitted.connect(my_handler)
        
        # Emit events
        bus.emit(EventType.TASK_COMPLETED, {"task_id": 123})
    """
    
    # Generic event signal
    event_emitted = pyqtSignal(object)  # Event
    
    # Specific typed signals for common events
    log_added = pyqtSignal(str, str, int)  # message, level, env_id
    environment_status_changed = pyqtSignal(int, str)  # env_id, status
    environment_created = pyqtSignal(dict)  # env_data
    scheduler_status_changed = pyqtSignal(bool)  # is_running
    stats_updated = pyqtSignal(dict)  # stats dict
    labor_stats_updated = pyqtSignal(dict)  # data dict
    
    
    def __init__(self):
        super().__init__()
    
    def emit(self, event_type: EventType, data: Any = None, source: str | None = None):
        """Emit an event.
        
        Args:
            event_type: Type of event.
            data: Event payload.
            source: Source identifier (e.g., module name).
        """
        event = Event(event_type, data, source)
        self.event_emitted.emit(event)
        
        # Also emit typed signals for common events
        self._emit_typed_signal(event)
    
    def _emit_typed_signal(self, event: Event):
        """Emit typed signal based on event type."""
        if event.type == EventType.ENVIRONMENT_STATUS_CHANGED:
            data = event.data or {}
            self.environment_status_changed.emit(
                data.get("env_id", 0),
                data.get("status", "unknown"),
            )
        elif event.type == EventType.ENVIRONMENT_CREATED:
            data = event.data or {}
            self.environment_created.emit(data)
        elif event.type in (EventType.SCHEDULER_STARTED, EventType.SCHEDULER_STOPPED):
            is_running = event.type == EventType.SCHEDULER_STARTED
            self.scheduler_status_changed.emit(is_running)
        elif event.type == EventType.LABOR_STATS_UPDATED:
            data = event.data or {}
            self.stats_updated.emit(data)
            self.labor_stats_updated.emit(data)



# Global event bus instance (Lazy initialized)
_event_bus_instance: EventBus | None = None

def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = EventBus()
    return _event_bus_instance

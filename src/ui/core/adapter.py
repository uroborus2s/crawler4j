"""Core 适配器 - 连接 UI 层和 Core 层。

负责：
    - 初始化 Core 服务
    - 注册命令处理器到 CommandChannel
    - 发布 Core 事件到 EventBus
"""

from typing import Any

from src.core.atm import TaskRequest, TaskStatus, get_task_service

# Core 模块导入
from src.core.mms import get_module_registry
from src.core.persistence import get_config_store, init_database
from src.ui.core.command_channel import CommandChannel, CoreCommands, get_command_channel
from src.ui.core.event_bus import Event, EventBus, EventType, get_event_bus


class CoreAdapter:
    """Core 适配器。
    
    作为 UI 层访问 Core 的唯一入口点。
    """
    
    def __init__(self):
        self._channel = get_command_channel()
        self._event_bus = get_event_bus()
        self._initialized = False
    
    def initialize(self) -> None:
        """初始化 Core 并注册命令处理器。"""
        if self._initialized:
            return
        
        init_database()
        self._register_module_commands()
        self._register_task_commands()
        self._register_config_commands()
        self._initialized = True
    
    # === 模块命令 ===
    
    def _register_module_commands(self) -> None:
        self._channel.register(CoreCommands.MODULE_LIST, self._cmd_module_list)
        self._channel.register(CoreCommands.MODULE_GET, self._cmd_module_get)
        self._channel.register(CoreCommands.MODULE_ENABLE, self._cmd_module_enable)
        self._channel.register(CoreCommands.MODULE_DISABLE, self._cmd_module_disable)
        self._channel.register(CoreCommands.MODULE_REFRESH, self._cmd_module_refresh)
    
    def _cmd_module_list(self) -> list[dict[str, Any]]:
        registry = get_module_registry()
        return [m.to_dict() for m in registry.list_modules()]
    
    def _cmd_module_get(self, module_name: str) -> dict[str, Any] | None:
        registry = get_module_registry()
        module = registry.get_module(module_name)
        return module.to_dict() if module else None
    
    def _cmd_module_enable(self, module_name: str) -> bool:
        registry = get_module_registry()
        success = registry.enable_module(module_name)
        if success:
            self._event_bus.publish(Event(type=EventType.MODULE_ENABLED, module_name=module_name))
        return success
    
    def _cmd_module_disable(self, module_name: str) -> bool:
        registry = get_module_registry()
        success = registry.disable_module(module_name)
        if success:
            self._event_bus.publish(Event(type=EventType.MODULE_DISABLED, module_name=module_name))
        return success
    
    def _cmd_module_refresh(self) -> dict[str, Any]:
        registry = get_module_registry()
        summary = registry.refresh()
        self._event_bus.publish(Event(type=EventType.MODULE_REFRESHED, data=summary))
        return summary
    
    # === 任务命令 ===
    
    def _register_task_commands(self) -> None:
        self._channel.register(CoreCommands.TASK_LIST_RECENT, self._cmd_task_list_recent)
        self._channel.register(CoreCommands.TASK_GET, self._cmd_task_get)
        self._channel.register_async(CoreCommands.TASK_SUBMIT, self._cmd_task_submit)
        self._channel.register_async(CoreCommands.TASK_STOP, self._cmd_task_stop)
    
    def _cmd_task_list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        service = get_task_service()
        return [t.to_dict() for t in service.list_recent(limit)]
    
    def _cmd_task_get(self, task_id: str) -> dict[str, Any] | None:
        service = get_task_service()
        task = service.get(task_id)
        return task.to_dict() if task else None
    
    async def _cmd_task_submit(
        self,
        module_name: str,
        task_name: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        service = get_task_service()
        request = TaskRequest(module_name=module_name, task_name=task_name, params=params or {})
        task = await service.submit(request)
        self._event_bus.publish(Event(type=EventType.TASK_STARTED, task_run_id=task.id, module_name=module_name))
        return task.to_dict()
    
    async def _cmd_task_stop(self, task_id: str, force: bool = False) -> bool:
        service = get_task_service()
        success = await service.stop(task_id, force)
        if success:
            self._event_bus.publish(Event(type=EventType.TASK_CANCELLED, task_run_id=task_id))
        return success
    
    # === 配置命令 ===
    
    def _register_config_commands(self) -> None:
        self._channel.register(CoreCommands.CONFIG_GET, self._cmd_config_get)
        self._channel.register(CoreCommands.CONFIG_SET, self._cmd_config_set)
    
    def _cmd_config_get(self, module_name: str, key: str) -> Any:
        store = get_config_store()
        return store.get_module_config(module_name).get(key)
    
    def _cmd_config_set(self, module_name: str, key: str, value: Any) -> bool:
        store = get_config_store()
        config = store.get_module_config(module_name)
        config[key] = value
        store.set_module_config(module_name, config)
        return True


# 全局单例
_adapter: CoreAdapter | None = None


def get_core_adapter() -> CoreAdapter:
    global _adapter
    if _adapter is None:
        _adapter = CoreAdapter()
    return _adapter

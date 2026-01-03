"""环境生命周期Hooks管理器。

负责Hooks的加载、注册和执行。
"""

import asyncio
from typing import Any

from src.plugins.models import EnvironmentHook, HandlerType, HookType
from src.plugins.repositories import EnvironmentHooksRepository
from src.utils.logger import logger

# 预定义动作注册表
PREDEFINED_ACTIONS: dict[str, callable] = {}


def register_action(name: str):
    """装饰器：注册预定义动作"""
    def decorator(func):
        PREDEFINED_ACTIONS[name] = func
        return func
    return decorator


@register_action("log_start")
async def action_log_start(ctx: dict) -> None:
    """记录环境启动日志"""
    env_id = ctx.get("env_id")
    logger.info(f"🚀 [Hook] 环境 ENV-{env_id} 开始执行")


@register_action("log_stop")
async def action_log_stop(ctx: dict) -> None:
    """记录环境停止日志"""
    env_id = ctx.get("env_id")
    logger.info(f"🛑 [Hook] 环境 ENV-{env_id} 停止执行")


@register_action("log_create")
async def action_log_create(ctx: dict) -> None:
    """记录环境创建日志"""
    env_id = ctx.get("env_id")
    logger.info(f"✨ [Hook] 环境 ENV-{env_id} 已创建")


@register_action("log_destroy")
async def action_log_destroy(ctx: dict) -> None:
    """记录环境销毁日志"""
    env_id = ctx.get("env_id")
    logger.info(f"🗑️ [Hook] 环境 ENV-{env_id} 已销毁")


@register_action("emit_event")
async def action_emit_event(ctx: dict) -> None:
    """发送事件到EventBus"""
    from src.core.events import EventType, get_event_bus
    
    bus = get_event_bus()
    event_type = ctx.get("event_type")
    if event_type:
        bus.emit(EventType[event_type], ctx)


@register_action("delay")
async def action_delay(ctx: dict) -> None:
    """延迟执行"""
    seconds = ctx.get("seconds", 1)
    await asyncio.sleep(seconds)


class HooksManager:
    """环境生命周期Hooks管理器
    
    功能：
    1. 从数据库加载Hooks配置
    2. 按优先级执行Hooks
    3. 支持预定义动作和自定义代码
    """

    _instance: "HooksManager | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        self._repo = EnvironmentHooksRepository()
        self._hooks_cache: dict[int | None, dict[HookType, list[EnvironmentHook]]] = {}
        self._initialized = True

    def load_hooks(self, env_id: int | None = None) -> None:
        """从数据库加载Hooks到缓存"""
        hooks_data = self._repo.get_by_environment(env_id)
        
        self._hooks_cache[env_id] = {}
        for hook_data in hooks_data:
            hook = EnvironmentHook.from_dict(hook_data)
            if hook.hook_type not in self._hooks_cache[env_id]:
                self._hooks_cache[env_id][hook.hook_type] = []
            self._hooks_cache[env_id][hook.hook_type].append(hook)
        
        logger.debug(f"已加载 {len(hooks_data)} 个Hooks (env_id={env_id})")

    def clear_cache(self, env_id: int | None = None) -> None:
        """清除Hooks缓存"""
        if env_id is None:
            self._hooks_cache.clear()
        elif env_id in self._hooks_cache:
            del self._hooks_cache[env_id]

    async def execute(
        self,
        hook_type: HookType,
        env_id: int | None,
        context: dict[str, Any],
    ) -> bool:
        """执行指定类型的Hooks
        
        Args:
            hook_type: Hook类型
            env_id: 环境ID
            context: 执行上下文
            
        Returns:
            True如果所有Hooks执行成功
        """
        # 确保缓存已加载
        if env_id not in self._hooks_cache:
            self.load_hooks(env_id)
        if None not in self._hooks_cache:
            self.load_hooks(None)  # 加载全局Hooks

        # 合并全局Hooks和环境特定Hooks
        hooks: list[EnvironmentHook] = []
        if None in self._hooks_cache:
            hooks.extend(self._hooks_cache[None].get(hook_type, []))
        if env_id in self._hooks_cache:
            hooks.extend(self._hooks_cache[env_id].get(hook_type, []))

        if not hooks:
            return True

        # 按优先级排序（高优先级先执行）
        hooks.sort(key=lambda h: h.priority, reverse=True)

        # 添加env_id到context
        context["env_id"] = env_id
        context["hook_type"] = hook_type.value

        logger.debug(f"执行 {len(hooks)} 个 {hook_type.value} Hooks (env_id={env_id})")

        for hook in hooks:
            if not hook.enabled:
                continue
            
            try:
                await self._execute_handler(hook, context)
            except Exception as e:
                logger.error(f"Hook执行失败 [{hook_type.value}]: {e}")
                # 根据配置决定是否中止后续Hooks
                # 当前策略：记录错误但继续执行
                continue

        return True

    async def _execute_handler(self, hook: EnvironmentHook, context: dict) -> None:
        """执行Hook处理器"""
        if hook.handler_type == HandlerType.PREDEFINED:
            await self._run_predefined_action(hook.handler_code, context)
        else:
            await self._run_custom_code(hook.handler_code, context)

    async def _run_predefined_action(self, action_code: str, context: dict) -> None:
        """运行预定义动作
        
        格式：action_name 或 action_name:param1=value1,param2=value2
        """
        # 解析动作名称和参数
        if ":" in action_code:
            action_name, params_str = action_code.split(":", 1)
            # 解析参数
            for param in params_str.split(","):
                if "=" in param:
                    key, value = param.split("=", 1)
                    context[key.strip()] = value.strip()
        else:
            action_name = action_code.strip()

        if action_name not in PREDEFINED_ACTIONS:
            logger.warning(f"未知的预定义动作: {action_name}")
            return

        action_func = PREDEFINED_ACTIONS[action_name]
        
        if asyncio.iscoroutinefunction(action_func):
            await action_func(context)
        else:
            action_func(context)

    async def _run_custom_code(self, code: str, context: dict) -> None:
        """运行自定义代码（简单沙箱）
        
        警告：这是一个简化实现，生产环境需要更严格的沙箱
        """
        # 准备安全的执行环境
        safe_globals = {
            "__builtins__": {
                "print": print,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "len": len,
                "range": range,
            },
            "ctx": context,
            "logger": logger,
            "asyncio": asyncio,
        }

        try:
            # 编译并执行代码
            compiled = compile(code, "<hook>", "exec")
            exec(compiled, safe_globals)
        except Exception as e:
            logger.error(f"自定义Hook代码执行失败: {e}")
            raise

    def get_available_actions(self) -> list[dict]:
        """获取所有可用的预定义动作"""
        return [
            {
                "name": name,
                "description": func.__doc__ or "",
            }
            for name, func in PREDEFINED_ACTIONS.items()
        ]


# 全局单例访问
_hooks_manager: HooksManager | None = None


def get_hooks_manager() -> HooksManager:
    """获取全局HooksManager实例"""
    global _hooks_manager
    if _hooks_manager is None:
        _hooks_manager = HooksManager()
    return _hooks_manager

"""SDK helper wrappers for host-managed resource-pool cards."""

from __future__ import annotations

import inspect
from typing import Any

from crawler4j_contracts import TaskContext


def _ensure_resource_pool_tool(context: TaskContext, tool_name: str) -> None:
    if context.tools is None:
        raise RuntimeError("TaskContext.tools 未注入，无法调用宿主资源池工具")
    if not context.tools.has_tool(tool_name):
        raise RuntimeError(
            f"宿主未提供 {tool_name} capability，无法调用资源池 helper；"
            "请先使用 ctx.tools.has_tool(...) 判断或升级宿主版本"
        )


async def _call_context_tool(context: TaskContext, tool_name: str, /, **kwargs: Any) -> Any:
    _ensure_resource_pool_tool(context, tool_name)
    result = context.tools.call(tool_name, **kwargs)
    if inspect.isawaitable(result):
        return await result
    return result


def _resolve_env_id(context: TaskContext, env_id: int | None) -> int:
    target_env_id = int(env_id) if env_id is not None else int(context.env_id)
    if target_env_id <= 0:
        raise ValueError("env_id is required")
    return target_env_id


async def bind_resource_pool(
    context: TaskContext,
    *,
    pool_name: str,
    env_id: int | None = None,
    eligible: bool = True,
    reason: str = "",
    exclusive: bool = True,
) -> bool:
    return bool(
        await _call_context_tool(
            context,
            "env.bind_resource_pool",
            env_id=_resolve_env_id(context, env_id),
            pool_name=pool_name,
            eligible=eligible,
            reason=reason,
            exclusive=exclusive,
        )
    )


async def mark_resource_pool_eligible(
    context: TaskContext,
    *,
    pool_name: str,
    env_id: int | None = None,
    reason: str = "",
) -> bool:
    return bool(
        await _call_context_tool(
            context,
            "env.mark_resource_pool_eligible",
            env_id=_resolve_env_id(context, env_id),
            pool_name=pool_name,
            reason=reason,
        )
    )


async def mark_resource_pool_ineligible(
    context: TaskContext,
    *,
    pool_name: str,
    env_id: int | None = None,
    reason: str,
) -> bool:
    return bool(
        await _call_context_tool(
            context,
            "env.mark_resource_pool_ineligible",
            env_id=_resolve_env_id(context, env_id),
            pool_name=pool_name,
            reason=reason,
        )
    )


async def remove_resource_pool(
    context: TaskContext,
    *,
    pool_name: str,
    env_id: int | None = None,
) -> bool:
    return bool(
        await _call_context_tool(
            context,
            "env.remove_resource_pool",
            env_id=_resolve_env_id(context, env_id),
            pool_name=pool_name,
        )
    )


async def replace_resource_pool_snapshot(
    context: TaskContext,
    *,
    pool_name: str,
    entries: list[dict[str, Any]],
) -> bool:
    return bool(
        await _call_context_tool(
            context,
            "env.replace_resource_pool_snapshot",
            pool_name=pool_name,
            entries=list(entries),
        )
    )

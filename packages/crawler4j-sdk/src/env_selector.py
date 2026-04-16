"""Module env selector registration helpers."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class EnvSelectorInfo:
    """模块声明的环境选择器元数据。"""

    name: str
    display_name: str = ""
    description: str = ""
    returns_none: bool = False


def env_selector(
    name: str,
    *,
    display_name: str = "",
    description: str = "",
    returns_none: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """把模块函数注册为可被 ATM 调用的环境选择器。"""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(
            func,
            "_crawler4j_env_selector",
            EnvSelectorInfo(
                name=name,
                display_name=display_name or name,
                description=description,
                returns_none=returns_none,
            ),
        )
        return func

    return decorator


def get_env_selector_info(func: object) -> EnvSelectorInfo | None:
    return getattr(func, "_crawler4j_env_selector", None)


async def invoke_env_selector(
    func: Callable[..., Any],
    *args: Any,
) -> Any:
    result = func(*args)
    if inspect.isawaitable(result):
        return await result
    return result

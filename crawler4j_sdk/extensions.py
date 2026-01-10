"""SDK 扩展模块（非稳定）。

本模块包含非稳定的扩展类型定义。
这些类型用于特定业务场景，不属于 SDK 稳定契约。

警告 (Non-stable):
    本模块中的类型可能在 MINOR 版本中发生破坏性变化。
    通用脚本只应依赖 crawler4j_sdk 主模块导出的稳定类型。

参考规格: docs/srs/06-sdk/index.md (6.0.4.2 Non-stable)
"""

from dataclasses import dataclass
from typing import Any, Callable

# === 业务账号信息（Non-stable）===

@dataclass
class CtripAccountInfo:
    """携程账号信息（只读）。
    
    Warning:
        非稳定扩展，可能在 MINOR 版本中变化。
    
    Attributes:
        id: 账号 ID。
        phone_number: 手机号（脱敏或完整，取决于配置）。
        country_code: 国家区号，默认 +86。
    """
    id: int
    phone_number: str
    country_code: str = "+86"


@dataclass
class LaborAccountInfo:
    """劳保账号信息（只读）。
    
    Warning:
        非稳定扩展，可能在 MINOR 版本中变化。
    
    Attributes:
        id: 账号 ID。
        phone_number: 手机号。
        password: 密码（应在使用后尽快清零）。
    """
    id: int
    phone_number: str
    password: str


# === 扩展上下文字段（Non-stable）===

@dataclass
class ExtendedContextFields:
    """扩展的上下文字段。
    
    用于存放业务特定的上下文信息，不属于稳定契约。
    运行时可在注入 TaskContext 时附加这些字段到 ctx.state。
    
    Warning:
        非稳定扩展，可能在 MINOR 版本中变化。
    
    Attributes:
        ctrip_account: 携程账号信息。
        labor_account: 劳保账号信息。
        input_callback: 输入回调（用于手动模式）。
    
    Example:
        >>> # 运行时注入
        >>> ctx.state["_ext"] = ExtendedContextFields(
        ...     ctrip_account=CtripAccountInfo(id=1, phone_number="138****8000"),
        ...     labor_account=None,
        ...     input_callback=my_callback
        ... )
        >>> 
        >>> # 脚本中访问
        >>> ext = ctx.state.get("_ext")
        >>> if ext and ext.ctrip_account:
        ...     phone = ext.ctrip_account.phone_number
    """
    ctrip_account: CtripAccountInfo | None = None
    labor_account: LaborAccountInfo | None = None
    input_callback: Callable[..., Any] | None = None


# === 辅助函数 ===

def get_ctrip_account(ctx: Any) -> CtripAccountInfo | None:
    """从上下文获取携程账号信息的辅助函数。
    
    Args:
        ctx: TaskContext 对象。
    
    Returns:
        CtripAccountInfo 或 None。
    
    Example:
        >>> from crawler4j_sdk.extensions import get_ctrip_account
        >>> account = get_ctrip_account(ctx)
        >>> if account:
        ...     ctx.logger.info(f"使用账号: {account.phone_number}")
    """
    ext = ctx.state.get("_ext")
    if ext and hasattr(ext, "ctrip_account"):
        return ext.ctrip_account
    return None


def get_labor_account(ctx: Any) -> LaborAccountInfo | None:
    """从上下文获取劳保账号信息的辅助函数。
    
    Args:
        ctx: TaskContext 对象。
    
    Returns:
        LaborAccountInfo 或 None。
    """
    ext = ctx.state.get("_ext")
    if ext and hasattr(ext, "labor_account"):
        return ext.labor_account
    return None


def get_input_callback(ctx: Any) -> Callable[..., Any] | None:
    """从上下文获取输入回调的辅助函数。
    
    Args:
        ctx: TaskContext 对象。
    
    Returns:
        输入回调函数或 None。
    """
    ext = ctx.state.get("_ext")
    if ext and hasattr(ext, "input_callback"):
        return ext.input_callback
    return None

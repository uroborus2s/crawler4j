"""SDK 数据服务层。

本模块定义了 Crawler4j SDK 的数据服务契约。
提供脚本访问框架数据库能力的 Protocol 接口。

稳定契约 (Stable API - 同 MAJOR 版本内冻结):
    - DataService 聚合类
    - 子服务 Protocol: AccountService, StorageService, TaskRecordService

参考规格: docs/02-requirements/reference-srs/06-sdk/06-6-data-model.md
"""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

# === 子服务 Protocol ===

@runtime_checkable
class AccountService(Protocol):
    """账号服务接口。
    
    提供账号/身份类数据访问能力（读多写少）。
    """
    
    def get_ctrip_account(self, phone: str) -> dict[str, Any] | None:
        """获取携程账号信息。
        
        Args:
            phone: 手机号。
        
        Returns:
            账号信息字典或 None。
        """
        ...
    
    def update_ctrip_status(self, account_id: int, status: str) -> bool:
        """更新携程账号状态。
        
        Args:
            account_id: 账号 ID。
            status: 新状态。
        
        Returns:
            是否更新成功。
        """
        ...
    
    def get_labor_account(self, phone: str) -> dict[str, Any] | None:
        """获取劳保账号信息。
        
        Args:
            phone: 手机号。
        
        Returns:
            账号信息字典或 None。
        """
        ...
    
    def update_labor_status(self, account_id: int, status: str) -> bool:
        """更新劳保账号状态。
        
        Args:
            account_id: 账号 ID。
            status: 新状态。
        
        Returns:
            是否更新成功。
        """
        ...


@runtime_checkable
class StateService(Protocol):
    """状态服务接口（KV Store）。
    
    提供运行时状态的 KV 存储能力，支持 TTL。
    用于存储 Cookie、Token、Session、游标等。
    
    Example:
        >>> # 保存 Cookie（24小时过期）
        >>> ctx.db.storage.state.set(
        ...     key=f"cookies:{username}",
        ...     value=browser_cookies,
        ...     ttl=86400
        ... )
        >>> 
        >>> # 读取 Cookie
        >>> cached = ctx.db.storage.state.get(f"cookies:{username}")
    """
    
    def get(self, key: str) -> Any:
        """获取状态值。
        
        Args:
            key: 状态键名。
        
        Returns:
            状态值，若不存在或已过期返回 None。
        """
        ...
    
    def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """设置状态值。
        
        Args:
            key: 状态键名。
            value: 状态值（必须 JSON 可序列化）。
            ttl: 过期时间（秒），None 表示永不过期。
        
        Returns:
            是否设置成功。
        """
        ...
    
    def delete(self, key: str) -> bool:
        """删除状态值。
        
        Args:
            key: 状态键名。
        
        Returns:
            是否删除成功。
        """
        ...


@runtime_checkable
class StorageService(Protocol):
    """存储服务接口。
    
    提供全局存储能力，聚合 KV 和状态服务。
    """
    
    @property
    def state(self) -> StateService:
        """状态服务（KV Store with TTL）。"""
        ...
    
    def get_kv(self, key: str) -> Any:
        """获取全局 KV 值（简化接口）。
        
        Args:
            key: 键名。
        
        Returns:
            值，若不存在返回 None。
        """
        ...
    
    def set_kv(self, key: str, value: Any) -> bool:
        """设置全局 KV 值（简化接口，无 TTL）。
        
        Args:
            key: 键名。
            value: 值（必须 JSON 可序列化）。
        
        Returns:
            是否设置成功。
        """
        ...
    
    def delete_kv(self, key: str) -> bool:
        """删除全局 KV 值。
        
        Args:
            key: 键名。
        
        Returns:
            是否删除成功。
        """
        ...


@runtime_checkable
class TaskRecordService(Protocol):
    """任务记录服务接口。
    
    提供任务运行记录的持久化能力。
    """
    
    def record_submission(self, task_id: str, result: dict[str, Any]) -> bool:
        """记录任务提交结果。
        
        Args:
            task_id: 任务 ID。
            result: 结果数据（应脱敏）。
        
        Returns:
            是否记录成功。
        """
        ...
    
    def get_task_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """获取任务历史。
        
        Args:
            limit: 返回记录数量上限。
        
        Returns:
            任务历史列表。
        """
        ...


# === 数据服务聚合类 ===

@dataclass
class DataService:
    """数据服务聚合类。
    
    通过 ctx.db 访问框架提供的数据库能力。
    聚合了账号服务、存储服务和任务记录服务。
    
    Attributes:
        accounts: 账号服务接口。
        storage: 存储服务接口（包含 state 子服务）。
        tasks: 任务记录服务接口。
    
    Example:
        >>> # 获取账号
        >>> account = ctx.db.accounts.get_ctrip_account("13800138000")
        >>> 
        >>> # 状态存储（带 TTL）
        >>> ctx.db.storage.state.set("last_task_id", task.id, ttl=3600)
        >>> last_id = ctx.db.storage.state.get("last_task_id")
        >>> 
        >>> # 全局 KV（无 TTL）
        >>> ctx.db.storage.set_kv("cursor", cursor_value)
        >>> 
        >>> # 记录任务结果
        >>> ctx.db.tasks.record_submission(task_id, result_dict)
    
    Note:
        - 脚本使用前必须判空或调用 is_available()
        - 写操作尽量幂等，避免重试导致重复写
    """
    
    accounts: AccountService | None = None
    """账号服务接口。"""
    
    storage: StorageService | None = None
    """存储服务接口。"""
    
    tasks: TaskRecordService | None = None
    """任务记录服务接口。"""
    
    def is_available(self) -> bool:
        """检查数据服务是否可用。
        
        Returns:
            True 如果至少一个子服务可用。
        
        Example:
            >>> if ctx.db and ctx.db.is_available():
            ...     # 使用数据服务
            ...     pass
        """
        return any([
            self.accounts is not None,
            self.storage is not None,
            self.tasks is not None,
        ])

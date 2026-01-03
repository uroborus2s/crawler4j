"""SDK 数据服务层

提供脚本访问框架数据库的能力。
"""

from dataclasses import dataclass
from typing import Any, Protocol


class AccountService(Protocol):
    """账号服务接口"""
    
    def get_ctrip_account(self, phone: str) -> dict | None:
        """获取携程账号信息"""
        ...
    
    def update_ctrip_status(self, account_id: int, status: str) -> bool:
        """更新携程账号状态"""
        ...
    
    def get_labor_account(self, phone: str) -> dict | None:
        """获取劳保账号信息"""
        ...
    
    def update_labor_status(self, account_id: int, status: str) -> bool:
        """更新劳保账号状态"""
        ...


class StorageService(Protocol):
    """全局存储服务接口"""
    
    def get_kv(self, key: str) -> Any:
        """获取全局KV值"""
        ...
    
    def set_kv(self, key: str, value: Any) -> bool:
        """设置全局KV值"""
        ...
    
    def delete_kv(self, key: str) -> bool:
        """删除全局KV值"""
        ...


class TaskRecordService(Protocol):
    """任务记录服务接口"""
    
    def record_submission(self, task_id: str, result: dict) -> bool:
        """记录任务提交结果"""
        ...
    
    def get_task_history(self, limit: int = 100) -> list[dict]:
        """获取任务历史"""
        ...


@dataclass
class DataService:
    """数据服务聚合类
    
    通过 ctx.db 访问框架提供的数据库能力。
    
    Example:
        account = await ctx.db.accounts.get_ctrip_account("13800138000")
        ctx.db.storage.set_kv("last_task_id", task.id)
    """
    
    accounts: AccountService | None = None
    storage: StorageService | None = None
    tasks: TaskRecordService | None = None
    
    def is_available(self) -> bool:
        """检查数据服务是否可用"""
        return self.accounts is not None

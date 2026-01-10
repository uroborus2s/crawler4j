"""环境池与租约管理。

规格参考: docs/srs/05-framework-core/05-2-runtime-environment-management.md (5.2.3.1)

Pool 层维护实例池与状态机，负责挑选可用实例、并发控制与回收策略。
LeaseManager 为任务运行发放租约，处理超时与异常兜底。
"""

import asyncio
import json
import time
from typing import Callable

from src.core.persistence.database import STATE_DB, get_connection
from src.core.rem.models import (
    Environment,
    EnvKind,
    EnvLease,
    EnvRequirement,
    EnvStatus,
    EnvUnavailableError,
)
from src.utils.logger import logger


class EnvPool:
    """环境池。
    
    规格 5.2.3.1: 维护实例池与状态机。
    
    职责：
        - 维护环境实例列表
        - 挑选满足需求的可用实例
        - 并发控制与配额管理
        - 状态持久化与恢复
    """
    
    def __init__(
        self,
        max_instances: int = 10,
        max_leases_per_kind: dict[EnvKind, int] | None = None,
    ):
        """初始化环境池。
        
        Args:
            max_instances: 最大实例数
            max_leases_per_kind: 每类环境的最大租约数
        """
        self.max_instances = max_instances
        self.max_leases_per_kind = max_leases_per_kind or {}
        
        # 内存中的环境列表
        self._environments: dict[str, Environment] = {}
        self._lock = asyncio.Lock()
    
    async def add(self, env: Environment) -> None:
        """添加环境到池中。"""
        async with self._lock:
            self._environments[env.id] = env
            self._persist_env(env)
    
    async def remove(self, env_id: str) -> Environment | None:
        """从池中移除环境。"""
        async with self._lock:
            env = self._environments.pop(env_id, None)
            if env:
                self._delete_env(env_id)
            return env
    
    async def get(self, env_id: str) -> Environment | None:
        """获取环境实例。"""
        return self._environments.get(env_id)
    
    async def find_available(self, requirement: EnvRequirement) -> Environment | None:
        """查找满足需求的可用环境。
        
        Args:
            requirement: 环境需求
        
        Returns:
            满足需求的 READY 状态环境，若无则返回 None
        """
        async with self._lock:
            for env in self._environments.values():
                if env.status == EnvStatus.READY and requirement.matches(env):
                    return env
            return None
    
    async def update_status(self, env_id: str, status: EnvStatus) -> None:
        """更新环境状态。"""
        async with self._lock:
            env = self._environments.get(env_id)
            if env:
                env.status = status
                env.updated_at = int(time.time())
                self._persist_env(env)
    
    async def count_by_status(self, status: EnvStatus) -> int:
        """统计指定状态的环境数量。"""
        return sum(1 for env in self._environments.values() if env.status == status)
    
    async def count_by_kind(self, kind: EnvKind) -> int:
        """统计指定类型的环境数量。"""
        return sum(1 for env in self._environments.values() if env.kind == kind)
    
    async def list_all(self) -> list[Environment]:
        """列出所有环境。"""
        return list(self._environments.values())
    
    async def list_by_status(self, status: EnvStatus) -> list[Environment]:
        """列出指定状态的环境。"""
        return [env for env in self._environments.values() if env.status == status]
    
    def can_create(self) -> bool:
        """检查是否可以创建新环境（未达配额）。"""
        return len(self._environments) < self.max_instances
    
    # === 持久化方法 ===
    
    def _persist_env(self, env: Environment) -> None:
        """持久化环境到数据库。"""
        with get_connection(STATE_DB) as conn:
            conn.execute(
                """
                INSERT INTO environments (id, kind, provider, status, lease_id, task_run_id, capabilities, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    lease_id = excluded.lease_id,
                    task_run_id = excluded.task_run_id,
                    updated_at = excluded.updated_at
                """,
                (
                    env.id,
                    env.kind.value,
                    env.provider,
                    env.status.value,
                    env.lease_id,
                    env.task_run_id,
                    json.dumps({"labels": env.labels, "capabilities": list(env.capabilities)}),
                    env.created_at,
                    env.updated_at,
                )
            )
    
    def _delete_env(self, env_id: str) -> None:
        """从数据库删除环境。"""
        with get_connection(STATE_DB) as conn:
            conn.execute("DELETE FROM environments WHERE id = ?", (env_id,))
    
    async def load_from_db(self) -> None:
        """从数据库加载环境（用于崩溃恢复）。"""
        with get_connection(STATE_DB) as conn:
            cursor = conn.execute("SELECT * FROM environments")
            for row in cursor.fetchall():
                meta = json.loads(row["capabilities"]) if row["capabilities"] else {}
                env = Environment(
                    id=row["id"],
                    kind=EnvKind(row["kind"]),
                    provider=row["provider"],
                    status=EnvStatus(row["status"]),
                    labels=meta.get("labels", {}),
                    capabilities=set(meta.get("capabilities", [])),
                    lease_id=row["lease_id"],
                    task_run_id=row["task_run_id"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                self._environments[env.id] = env


class LeaseManager:
    """租约管理器。
    
    规格 5.2.3.1: 为任务运行发放租约，关联 task_run_id，处理超时与异常兜底。
    """
    
    def __init__(self, pool: EnvPool):
        """初始化租约管理器。
        
        Args:
            pool: 关联的环境池
        """
        self.pool = pool
        self._leases: dict[str, EnvLease] = {}
        self._lock = asyncio.Lock()
    
    async def acquire(
        self,
        env: Environment,
        task_run_id: str,
        timeout: int | None = None,
    ) -> EnvLease:
        """获取环境租约。
        
        Args:
            env: 环境实例
            task_run_id: 任务运行ID
            timeout: 超时时间（秒），超时后可强制回收
        
        Returns:
            环境租约
        """
        async with self._lock:
            now = int(time.time())
            expires_at = now + timeout if timeout else None
            
            lease = EnvLease(
                env_id=env.id,
                task_run_id=task_run_id,
                acquired_at=now,
                expires_at=expires_at,
            )
            
            # 更新环境状态
            env.status = EnvStatus.BUSY
            env.lease_id = lease.id
            env.task_run_id = task_run_id
            env.updated_at = now
            
            # 持久化
            self.pool._persist_env(env)
            self._leases[lease.id] = lease
            
            logger.info(f"[REM] 租约分配: lease={lease.id[:8]}... env={env.id[:8]}... task={task_run_id[:8]}...")
            
            return lease
    
    async def release(self, lease: EnvLease, token: str) -> Environment | None:
        """释放租约。
        
        Args:
            lease: 租约
            token: 验证令牌
        
        Returns:
            释放的环境实例，验证失败返回 None
        """
        async with self._lock:
            # 验证令牌
            if lease.token != token:
                logger.warning(f"[REM] 租约释放失败: token 不匹配")
                return None
            
            # 获取环境
            env = await self.pool.get(lease.env_id)
            if not env:
                logger.warning(f"[REM] 租约释放失败: 环境不存在 {lease.env_id}")
                return None
            
            # 清除租约信息
            env.lease_id = None
            env.task_run_id = None
            env.updated_at = int(time.time())
            
            # 移除租约
            self._leases.pop(lease.id, None)
            
            logger.info(f"[REM] 租约释放: lease={lease.id[:8]}... env={env.id[:8]}...")
            
            return env
    
    async def get_lease(self, lease_id: str) -> EnvLease | None:
        """获取租约。"""
        return self._leases.get(lease_id)
    
    async def list_expired(self) -> list[EnvLease]:
        """列出所有过期租约。"""
        now = int(time.time())
        return [
            lease for lease in self._leases.values()
            if lease.expires_at and lease.expires_at < now
        ]
    
    async def count_active(self) -> int:
        """统计活跃租约数。"""
        return len(self._leases)

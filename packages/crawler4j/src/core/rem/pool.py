"""环境池与租约管理。

规格参考: docs/02-requirements/reference-srs/05-framework-core/05-2-runtime-environment-management.md (5.2.3.1)

Pool 层维护实例池与状态机，负责挑选可用实例、并发控制与回收策略。
LeaseManager 为任务运行发放租约，处理超时与异常兜底。
"""

import asyncio
import json
import time
import uuid
from typing import Any

from src.core.foundation.logging import logger
from src.core.persistence.database import STATE_DB, get_connection
from src.core.rem.handle import BrowserHandle
from src.core.rem.models import (
    Environment,
    EnvKind,
    EnvLease,
    EnvRequirement,
    EnvStatus,
    ProxyConfig,
)


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
        max_instances: int,
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
        self._environments: dict[int, Environment] = {}
        self._lock = asyncio.Lock()
    
    async def add(self, env: Environment) -> None:
        """添加环境到池中。
        
        注意：对于新环境 (id=0)，先持久化获取真实 id，再添加到缓存，
        避免缓存中出现 key=0 的孤儿条目。
        """
        async with self._lock:
            old_id = env.id
            env.updated_at = int(time.time())
            # 先持久化（可能分配新 id）
            self._persist_env(env)
            # 如果 id 变化了（新环境），确保缓存使用正确的 key
            if old_id != env.id and old_id in self._environments:
                del self._environments[old_id]
            self._environments[env.id] = env
    
    async def remove(self, env_id: int) -> Environment | None:
        """从池中移除环境。
        
        统一处理：解绑 IP + 删除数据库记录。
        """
        from src.core.rem.ip_pool import get_ip_pool_manager
        
        async with self._lock:
            env = self._environments.pop(env_id, None)
            if env:
                # 统一解绑 IP（无论删除原因）
                try:
                    await get_ip_pool_manager().unbind_ip(env_id)
                except Exception:
                    pass  # 忽略解绑失败，确保删除流程继续
                self._delete_env(env_id)
            return env
    
    async def get(self, env_id: int) -> Environment | None:
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
    
    async def update_status(self, env_id: int, status: EnvStatus) -> None:
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
    
    def _persist_env(self, env: Environment) -> int:
        """持久化环境到数据库。
        
        Returns:
            分配的环境 ID（新环境为自增值，已有环境返回原 ID）
        """
        with get_connection(STATE_DB) as conn:
            # 序列化配置为 JSON
            proxy_config_json = json.dumps(env.proxy_config.to_dict()) if env.proxy_config else None
            
            if env.id == 0:
                # 新环境：INSERT 并获取自增 ID
                cursor = conn.execute(
                    """
                    INSERT INTO environments (
                        name, kind, provider, status, external_id, lease_id, task_run_id,
                        last_used_at, daily_usage_count, daily_usage_date,
                        proxy_config_json,
                        capabilities, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        env.name,
                        env.kind.value,
                        env.provider,
                        env.status.value,
                        env.external_id,
                        env.lease_id,
                        env.task_run_id,
                        env.last_used_at,
                        env.daily_usage_count,
                        env.daily_usage_date,
                        proxy_config_json,
                        json.dumps({"capabilities": list(env.capabilities)}),
                        env.created_at,
                        env.updated_at,
                    )
                )
                env.id = cursor.lastrowid or 0
                return env.id
            else:
                # 已有环境：UPDATE
                conn.execute(
                    """
                    UPDATE environments SET
                        name = ?,
                        status = ?,
                        external_id = ?,
                        lease_id = ?,
                        task_run_id = ?,
                        last_used_at = ?,
                        daily_usage_count = ?,
                        daily_usage_date = ?,
                        proxy_config_json = ?,
                        capabilities = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        env.name,
                        env.status.value,
                        env.external_id,
                        env.lease_id,
                        env.task_run_id,
                        env.last_used_at,
                        env.daily_usage_count,
                        env.daily_usage_date,
                        proxy_config_json,
                        json.dumps({"capabilities": list(env.capabilities)}),
                        env.updated_at,
                        env.id,
                    )
                )
                return env.id
    
    def _delete_env(self, env_id: int) -> None:
        """从数据库删除环境。"""
        with get_connection(STATE_DB) as conn:
            conn.execute("DELETE FROM environments WHERE id = ?", (env_id,))
    
    async def load_from_db(self) -> None:
        """从数据库加载环境（用于崩溃恢复）。"""
        from src.core.rem.models import ProxyConfig
        
        with get_connection(STATE_DB) as conn:
            cursor = conn.execute("SELECT * FROM environments")
            for row in cursor.fetchall():
                meta = json.loads(row["capabilities"]) if row["capabilities"] else {}
                
                # 反序列化配置
                proxy_config = None
                if row["proxy_config_json"]:
                    proxy_config = ProxyConfig.from_dict(json.loads(row["proxy_config_json"]))
                
                env = Environment(
                    id=row["id"],
                    name=row["name"] if "name" in row.keys() else "",
                    kind=EnvKind(row["kind"]),
                    provider=row["provider"],
                    status=EnvStatus(row["status"]),
                    external_id=row["external_id"],
                    capabilities=set(meta.get("capabilities", [])),
                    lease_id=row["lease_id"],
                    task_run_id=row["task_run_id"],
                    last_used_at=row["last_used_at"],
                    daily_usage_count=row["daily_usage_count"] or 0,
                    daily_usage_date=row["daily_usage_date"] or "",
                    proxy_config=proxy_config,
                    created_at=row["created_at"],
                )
                
                # 重建 handle：从 external_id 恢复 browser_id
                if row["external_id"]:
                    try:
                        browser_id = row["external_id"]
                        env.handle = BrowserHandle(browser_id=browser_id)
                    except (ValueError, TypeError):
                        # external_id 不是数字（如 Playwright 本地模式）
                        env.handle = BrowserHandle(browser_id=row["external_id"])
                self._environments[env.id] = env
    
    # === Metadata 操作 ===
    def get_metadata(self, env_id: int, namespace: str, key: str) -> Any:
        """获取元数据值。"""
        with get_connection(STATE_DB) as conn:
            cursor = conn.execute(
                "SELECT value, value_type FROM env_metadata WHERE env_id = ? AND namespace = ? AND key = ?",
                (env_id, namespace, key)
            )
            row = cursor.fetchone()
            if row:
                return self._decode_value(row["value"], row["value_type"])
            return None
    
    def set_metadata(
        self,
        env_id: int,
        namespace: str,
        key: str,
        value: Any,
        value_type: str = "string",
    ) -> bool:
        """设置元数据值。"""
        encoded_value = self._encode_value(value)
        now = int(time.time())
        with get_connection(STATE_DB) as conn:
            conn.execute(
                """
                INSERT INTO env_metadata (env_id, namespace, key, value, value_type, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(env_id, namespace, key) DO UPDATE SET
                    value = excluded.value,
                    value_type = excluded.value_type,
                    updated_at = excluded.updated_at
                """,
                (env_id, namespace, key, encoded_value, value_type, now, now)
            )
        return True
    
    def list_metadata(self, env_id: int, namespace: str | None = None) -> dict[str, Any]:
        """列出元数据。"""
        with get_connection(STATE_DB) as conn:
            if namespace:
                cursor = conn.execute(
                    "SELECT key, value, value_type FROM env_metadata WHERE env_id = ? AND namespace = ?",
                    (env_id, namespace)
                )
            else:
                cursor = conn.execute(
                    "SELECT namespace, key, value, value_type FROM env_metadata WHERE env_id = ?",
                    (env_id,)
                )
            
            result = {}
            for row in cursor.fetchall():
                if namespace:
                    result[row["key"]] = self._decode_value(row["value"], row["value_type"])
                else:
                    ns = row["namespace"]
                    if ns not in result:
                        result[ns] = {}
                    result[ns][row["key"]] = self._decode_value(row["value"], row["value_type"])
            return result
    
    def delete_metadata(self, env_id: int, namespace: str, key: str | None = None) -> int:
        """删除元数据，返回删除条数。"""
        with get_connection(STATE_DB) as conn:
            if key:
                cursor = conn.execute(
                    "DELETE FROM env_metadata WHERE env_id = ? AND namespace = ? AND key = ?",
                    (env_id, namespace, key)
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM env_metadata WHERE env_id = ? AND namespace = ?",
                    (env_id, namespace)
                )
            return cursor.rowcount
    
    def _encode_value(self, value: Any) -> str:
        """编码值为 JSON 字符串。"""
        return json.dumps(value, ensure_ascii=False)
    
    def _decode_value(self, value: str, value_type: str) -> Any:
        """解码 JSON 字符串为原始类型。"""
        if value is None:
            return None
        try:
            decoded = json.loads(value)
            if value_type == "int":
                return int(decoded)
            elif value_type == "float":
                return float(decoded)
            elif value_type == "bool":
                return bool(decoded)
            return decoded
        except (json.JSONDecodeError, ValueError):
            return value


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
        from src.core.rem.models import EnvUnavailableError

        async with self._lock:
            # 状态守卫: 固定池/常规任务都只允许 READY 环境进入新的租赁周期。
            if env.lease_id or env.status != EnvStatus.READY:
                raise EnvUnavailableError(
                    f"环境 {env.id} 已被占用 (status={env.status.value})",
                    stage="LEASE",
                    hint="请等待环境释放或选择其他环境",
                )
            
            now = int(time.time())
            expires_at = now + timeout if timeout else None
            
            lease = EnvLease(
                env_id=env.id,
                task_run_id=task_run_id,
                acquired_at=now,
                expires_at=expires_at,
            )
            
            # 发放租约后统一进入 BUSY，后续由 start/connect 再转成 RUNNING。
            env.status = EnvStatus.BUSY
            env.lease_id = lease.id
            env.task_run_id = task_run_id
            env.updated_at = now
            
            # 持久化
            self.pool._persist_env(env)
            self._leases[lease.id] = lease
            
            logger.info(f"[REM] 租约分配: lease={lease.id[:8]}... env={env.name[:8]}... task={task_run_id[:8]}...")
            
            return lease

    async def claim_created_env(
        self,
        env: Environment,
        task_run_id: str,
        timeout: int | None = None,
    ) -> EnvLease:
        """为刚创建完成的环境补发租约。

        `_create_env()` 成功返回时，环境已经过 open/connect，真实状态通常是
        `RUNNING`。这类环境不应再走只接受 `READY` 的普通 acquire 守卫，
        否则会把当前任务自己刚创建好的环境误判成“已被占用”。
        """
        from src.core.rem.models import EnvUnavailableError

        async with self._lock:
            if env.lease_id:
                raise EnvUnavailableError(
                    f"环境 {env.id} 已存在租约",
                    stage="LEASE",
                    hint="请等待环境释放或选择其他环境",
                )
            if env.status not in {EnvStatus.READY, EnvStatus.BUSY, EnvStatus.RUNNING}:
                raise EnvUnavailableError(
                    f"环境 {env.id} 当前状态不可认领 (status={env.status.value})",
                    stage="LEASE",
                    hint="请检查环境创建链路或重新创建环境",
                )

            now = int(time.time())
            expires_at = now + timeout if timeout else None
            lease = EnvLease(
                env_id=env.id,
                task_run_id=task_run_id,
                acquired_at=now,
                expires_at=expires_at,
            )

            if env.status == EnvStatus.READY:
                env.status = EnvStatus.BUSY
            env.lease_id = lease.id
            env.task_run_id = task_run_id
            env.updated_at = now

            self.pool._persist_env(env)
            self._leases[lease.id] = lease

            logger.info(
                f"[REM] 认领新建环境租约: lease={lease.id[:8]}... env={env.name[:8]}... task={task_run_id[:8]}..."
            )
            return lease

    async def acquire_atomic(
        self,
        requirement: EnvRequirement,
        timeout: int = 60,
    ) -> EnvLease:
        """Atomic acquire using DB transaction to prevent race conditions."""
        loop = asyncio.get_running_loop()
        
        def _execute_atomic_lease():
            with get_connection(STATE_DB) as conn:
                # SQLite IMMEDIATE transaction to lock DB for writing
                conn.execute("BEGIN IMMEDIATE")
                try:
                    # 1. Find available env
                    cursor = conn.execute(
                        """
                        SELECT id, name, status, kind, provider, external_id, capabilities, proxy_config_json
                        FROM environments 
                        WHERE status = ? AND kind = ? 
                        ORDER BY last_used_at ASC
                        """,
                        (EnvStatus.READY.value, requirement.kind.value)
                    )
                    row = None
                    for candidate in cursor.fetchall():
                        proxy_config = None
                        if candidate["proxy_config_json"]:
                            proxy_config = ProxyConfig.from_dict(json.loads(candidate["proxy_config_json"]))

                        meta = json.loads(candidate["capabilities"]) if candidate["capabilities"] else {}
                        env = Environment(
                            id=candidate["id"],
                            name=candidate["name"] or "",
                            kind=EnvKind(candidate["kind"]),
                            provider=candidate["provider"] or "",
                            status=EnvStatus(candidate["status"]),
                            external_id=candidate["external_id"],
                            capabilities=set(meta.get("capabilities", [])),
                            proxy_config=proxy_config,
                        )
                        if requirement.matches(env):
                            row = candidate
                            break

                    if not row:
                        return None
                    
                    env_id = row["id"]
                    now = int(time.time())
                    expires_at = now + timeout if timeout else None
                    lease_id = str(uuid.uuid4())
                    
                    # 2. Update env status
                    conn.execute(
                        """
                        UPDATE environments 
                        SET status = ?, lease_id = ?, task_run_id = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (EnvStatus.BUSY.value, lease_id, requirement.task_run_id, now, env_id)
                    )
                    
                    conn.commit()
                    
                    return {
                        "env_id": env_id,
                        "lease_id": lease_id,
                        "acquired_at": now,
                        "expires_at": expires_at,
                        "env_name": row["name"]
                    }
                except Exception as e:
                    conn.rollback()
                    raise e

        # Run SQL in thread
        result = await loop.run_in_executor(None, _execute_atomic_lease)
        
        if not result:
            from src.core.rem.models import EnvUnavailableError
            raise EnvUnavailableError(
                f"无可用环境 (kind={requirement.kind})",
                stage="LEASE_ATOMIC"
            )

        # 3. Update In-Memory Cache (EnvPool)
        # 必须更新缓存，否则后续 get_env 会读到旧状态
        # 注意：这里可能存在微小的 Race，但因为我们是"权威源->缓存"的单向更新，且持有 lease_id，风险可控。
        env = await self.pool.get(result["env_id"])
        if env:
            env.status = EnvStatus.BUSY
            env.lease_id = result["lease_id"]
            env.task_run_id = requirement.task_run_id
            env.updated_at = result["acquired_at"]
        
        # 4. Return Lease Object
        lease = EnvLease(
            id=result["lease_id"],
            env_id=result["env_id"],
            task_run_id=requirement.task_run_id,
            acquired_at=result["acquired_at"],
            expires_at=result["expires_at"]
        )
        self._leases[lease.id] = lease
        logger.info(f"[REM] Atomic Lease: lease={lease.id[:8]}... env={result['env_name']}... task={requirement.task_run_id[:8]}...")
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
                logger.warning("[REM] 租约释放失败: token 不匹配")
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
            
            logger.info(f"[REM] 租约释放: lease={lease.id[:8]}... env={env.name[:8]}...")
            
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

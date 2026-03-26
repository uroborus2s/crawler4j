"""ATM 运行时能力注入实现。

将 Core 能力以契约对象形式注入 TaskContext，供 model 脚本通过 SDK 访问。
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from crawler4j_contracts.context import (
    DatabaseCapability,
    EnvOpsCapability,
    IPPoolCapability,
    UICapability,
)
from src.core.persistence import get_kv_store
from src.core.rem.ip_pool import IPEntry, get_ip_pool_manager
from src.core.rem.manager import get_environment_manager


def _normalize_records(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        normalized.append(dict(item))

    return normalized


class CoreDatabaseCapabilityImpl(DatabaseCapability):
    """Core 侧基础数据能力实现（records + lock + state）。"""

    def __init__(self, module_name: str):
        self._module_name = module_name
        self._kv = get_kv_store()

    def _dataset_key(self, dataset: str) -> str:
        return f"module:{self._module_name}:dataset:{dataset}"

    def _lock_key(self, scope: str, key: str) -> str:
        return f"module:{self._module_name}:lock:{scope}:{key}"

    def list_records(self, dataset: str) -> list[dict[str, Any]]:
        raw = self._kv.get(self._dataset_key(dataset)) or []
        return _normalize_records(raw)

    def replace_records(self, dataset: str, records: list[dict[str, Any]]) -> bool:
        return self._kv.set(self._dataset_key(dataset), _normalize_records(records))

    def acquire_lock(
        self,
        scope: str,
        key: str,
        *,
        ttl: int,
        owner: dict[str, Any] | None = None,
    ) -> bool:
        lock_key = self._lock_key(scope, key)
        if self._kv.exists(lock_key):
            return False
        payload = {
            "module": self._module_name,
            "scope": scope,
            "key": key,
            "owner": owner or {},
            "claimed_at": int(time.time()),
        }
        return self._kv.set(lock_key, payload, ttl=ttl)

    def release_lock(self, scope: str, key: str) -> bool:
        return self._kv.delete(self._lock_key(scope, key))

    def is_locked(self, scope: str, key: str) -> bool:
        return self._kv.exists(self._lock_key(scope, key))

    def get_state(self, key: str) -> Any:
        return self._kv.get(key)

    def set_state(self, key: str, value: Any, ttl: int | None = None) -> bool:
        return self._kv.set(key, value, ttl=ttl)

    def exists_state(self, key: str) -> bool:
        return self._kv.exists(key)


class CoreIPPoolCapabilityImpl(IPPoolCapability):
    """Core 侧 IP 池能力实现。"""

    def _iter_candidate_entries(self, pool_id: str | None) -> list[IPEntry]:
        manager = get_ip_pool_manager()
        pools = []
        if pool_id:
            pool = manager.get_pool(pool_id)
            if pool:
                pools.append(pool)
        else:
            pools = manager.list_pools()

        entries: list[IPEntry] = []
        for pool in pools:
            entries.extend(pool.entries)
        return entries

    def pick_proxy(self, criteria: dict[str, Any] | None = None) -> dict[str, Any] | None:
        criteria = criteria or {}
        pool_id = str(criteria.get("pool_id", "")).strip() or None
        protocol = str(criteria.get("protocol", "")).strip().lower() or None
        min_safety_score = int(criteria.get("min_safety_score", 0))

        max_bound_count_raw = criteria.get("max_bound_count")
        max_bound_count = None
        if max_bound_count_raw is not None:
            try:
                max_bound_count = int(max_bound_count_raw)
            except (TypeError, ValueError):
                max_bound_count = None

        candidates = []
        for entry in self._iter_candidate_entries(pool_id):
            if entry.is_expired():
                continue
            if protocol and entry.protocol.lower() != protocol:
                continue
            if entry.safety_score < min_safety_score:
                continue
            if max_bound_count is not None and entry.bound_count > max_bound_count:
                continue
            candidates.append(entry)

        if not candidates:
            return None

        selected = sorted(candidates, key=lambda e: (e.bound_count, -e.safety_score, e.created_at))[0]
        auth = ""
        if selected.username and selected.password:
            auth = f"{selected.username}:{selected.password}@"
        proxy_url = f"{selected.protocol}://{auth}{selected.address}:{selected.port}"

        return {
            "id": selected.id,
            "pool_id": selected.pool_id,
            "protocol": selected.protocol,
            "type": selected.protocol,
            "host": selected.address,
            "port": selected.port,
            "username": selected.username or "",
            "password": selected.password or "",
            "proxy_url": proxy_url,
            "safety_score": selected.safety_score,
            "bound_count": selected.bound_count,
        }


class CoreEnvOpsCapabilityImpl(EnvOpsCapability):
    """Core 侧环境操作能力实现。"""

    async def set_proxy(
        self,
        env_id: int,
        *,
        proxy_value: str | None = None,
        proxy_pool_id: str | None = None,
    ) -> bool:
        manager = get_environment_manager()
        return await manager.update_env(
            env_id,
            proxy_value=proxy_value or None,
            proxy_pool_id=proxy_pool_id or None,
        )


class CoreUICapabilityImpl(UICapability):
    """Core 侧 UI 声明能力实现（通用数据表）。"""

    def __init__(self, module_name: str):
        self._module_name = module_name
        self._kv = get_kv_store()

    def _meta_key(self, view_id: str) -> str:
        return f"module:{self._module_name}:ui:data_table:{view_id}"

    def _dataset_key(self, dataset: str) -> str:
        return f"module:{self._module_name}:dataset:{dataset}"

    def declare_data_table(self, view_id: str, schema: dict[str, Any]) -> bool:
        meta = dict(schema or {})
        meta.setdefault("title", view_id)
        meta.setdefault("dataset", view_id)
        meta.setdefault("primary_key", "id")
        meta.setdefault("columns", [])

        dataset = str(meta.get("dataset") or view_id)
        if self._kv.get(self._dataset_key(dataset)) is None:
            self._kv.set(self._dataset_key(dataset), [])

        return self._kv.set(self._meta_key(view_id), meta)

    def get_data_table(self, view_id: str) -> dict[str, Any]:
        return self._kv.get(self._meta_key(view_id)) or {}


@dataclass
class RuntimeCapabilities:
    db: DatabaseCapability
    ip_pool: IPPoolCapability
    env_ops: EnvOpsCapability
    ui: UICapability


def build_runtime_capabilities(task_name: str) -> RuntimeCapabilities:
    module_name = (task_name or "").split(".")[0] or "default"
    return RuntimeCapabilities(
        db=CoreDatabaseCapabilityImpl(module_name),
        ip_pool=CoreIPPoolCapabilityImpl(),
        env_ops=CoreEnvOpsCapabilityImpl(),
        ui=CoreUICapabilityImpl(module_name),
    )

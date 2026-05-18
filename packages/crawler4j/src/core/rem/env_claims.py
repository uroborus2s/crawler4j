"""Host-owned environment claim metadata and module binding helpers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from crawler4j_contracts import TaskContext

from src.core.atm.models import TaskStatus
from src.core.atm.repository import TaskRepository, get_task_repository
from src.core.atm.runtime_capabilities import build_runtime_capabilities
from src.core.foundation.logging import logger
from src.core.mms.service import ModuleService, get_module_service

ENV_CLAIM_NAMESPACE = "host.env_claim"
ENV_CLAIM_OWNER_MODULE = "owner_module"
ENV_CLAIM_STATE = "state"
ENV_CLAIM_TASK_ID = "task_id"
ENV_CLAIM_CREATED_AT = "created_at"
ENV_CLAIM_CLAIMED_AT = "claimed_at"
ENV_CLAIM_ABANDONED_AT = "abandoned_at"

CLAIM_PENDING = "pending"
CLAIM_CLAIMED = "claimed"
CLAIM_ABANDONED = "abandoned"
CLAIM_STATES = frozenset({CLAIM_PENDING, CLAIM_CLAIMED, CLAIM_ABANDONED})

ACTIVE_TASK_STATUSES = frozenset({TaskStatus.PENDING, TaskStatus.RUNNING})


@dataclass(frozen=True)
class EnvClaim:
    env_id: int
    owner_module: str = ""
    state: str = ""
    task_id: str = ""
    created_at: int | None = None
    claimed_at: int | None = None
    abandoned_at: int | None = None

    @property
    def has_owner(self) -> bool:
        return bool(self.owner_module)

    @property
    def is_pending(self) -> bool:
        return self.state == CLAIM_PENDING

    @property
    def is_claimed(self) -> bool:
        return self.state == CLAIM_CLAIMED

    @property
    def is_abandoned(self) -> bool:
        return self.state == CLAIM_ABANDONED


def _normalize_claim_state(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in CLAIM_STATES else ""


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def get_env_claim(rem: Any, env_id: int | str) -> EnvClaim:
    list_metadata = getattr(rem, "list_metadata", None)
    metadata: dict[str, Any] = {}
    if callable(list_metadata):
        raw = await list_metadata(int(env_id), ENV_CLAIM_NAMESPACE)
        metadata = raw if isinstance(raw, dict) else {}
    return EnvClaim(
        env_id=int(env_id),
        owner_module=str(metadata.get(ENV_CLAIM_OWNER_MODULE) or "").strip(),
        state=_normalize_claim_state(metadata.get(ENV_CLAIM_STATE)),
        task_id=str(metadata.get(ENV_CLAIM_TASK_ID) or "").strip(),
        created_at=_as_int(metadata.get(ENV_CLAIM_CREATED_AT)),
        claimed_at=_as_int(metadata.get(ENV_CLAIM_CLAIMED_AT)),
        abandoned_at=_as_int(metadata.get(ENV_CLAIM_ABANDONED_AT)),
    )


async def set_pending_env_claim(rem: Any, env_id: int | str, *, owner_module: str, task_id: str) -> None:
    owner = str(owner_module or "").strip()
    task = str(task_id or "").strip()
    if not owner:
        raise ValueError("owner_module is required")
    set_metadata = getattr(rem, "set_metadata", None)
    if not callable(set_metadata):
        return
    now = int(time.time())
    await set_metadata(int(env_id), ENV_CLAIM_NAMESPACE, ENV_CLAIM_OWNER_MODULE, owner, "string")
    await set_metadata(int(env_id), ENV_CLAIM_NAMESPACE, ENV_CLAIM_STATE, CLAIM_PENDING, "string")
    await set_metadata(int(env_id), ENV_CLAIM_NAMESPACE, ENV_CLAIM_TASK_ID, task, "string")
    await set_metadata(int(env_id), ENV_CLAIM_NAMESPACE, ENV_CLAIM_CREATED_AT, now, "int")
    await set_metadata(int(env_id), ENV_CLAIM_NAMESPACE, ENV_CLAIM_CLAIMED_AT, "", "int")
    await set_metadata(int(env_id), ENV_CLAIM_NAMESPACE, ENV_CLAIM_ABANDONED_AT, "", "int")


async def set_claimed_env_claim(rem: Any, env_id: int | str, *, owner_module: str, task_id: str = "") -> None:
    await _set_claim_state(rem, env_id, state=CLAIM_CLAIMED, owner_module=owner_module, task_id=task_id)


async def set_abandoned_env_claim(rem: Any, env_id: int | str, *, owner_module: str, task_id: str = "") -> None:
    await _set_claim_state(rem, env_id, state=CLAIM_ABANDONED, owner_module=owner_module, task_id=task_id)


async def _set_claim_state(
    rem: Any,
    env_id: int | str,
    *,
    state: str,
    owner_module: str,
    task_id: str = "",
) -> None:
    owner = str(owner_module or "").strip()
    if not owner:
        return
    set_metadata = getattr(rem, "set_metadata", None)
    if not callable(set_metadata):
        return
    claim = await get_env_claim(rem, int(env_id))
    now = int(time.time())
    await set_metadata(int(env_id), ENV_CLAIM_NAMESPACE, ENV_CLAIM_OWNER_MODULE, owner, "string")
    await set_metadata(int(env_id), ENV_CLAIM_NAMESPACE, ENV_CLAIM_STATE, state, "string")
    await set_metadata(int(env_id), ENV_CLAIM_NAMESPACE, ENV_CLAIM_TASK_ID, task_id or claim.task_id, "string")
    if not claim.created_at:
        await set_metadata(int(env_id), ENV_CLAIM_NAMESPACE, ENV_CLAIM_CREATED_AT, now, "int")
    if state == CLAIM_CLAIMED:
        await set_metadata(int(env_id), ENV_CLAIM_NAMESPACE, ENV_CLAIM_CLAIMED_AT, now, "int")
        await set_metadata(int(env_id), ENV_CLAIM_NAMESPACE, ENV_CLAIM_ABANDONED_AT, "", "int")
    elif state == CLAIM_ABANDONED:
        await set_metadata(int(env_id), ENV_CLAIM_NAMESPACE, ENV_CLAIM_ABANDONED_AT, now, "int")


def _binding_field_entries(module_service: ModuleService | Any, module_name: str, context: TaskContext | None) -> list[tuple[str, str]]:
    descriptor = module_service.get_runtime_descriptor_v2(module_name, context)
    entries: list[tuple[str, str]] = []
    for table_name, entry in sorted(getattr(descriptor, "data_tables", {}).items()):
        field_name = str(getattr(entry.meta, "env_binding_field", "") or "").strip()
        if field_name:
            entries.append((str(table_name), field_name))
    return entries


def _query_binding_rows(context: TaskContext, table_name: str, field_name: str) -> list[dict[str, Any]]:
    rows = context.db.from_(table_name).select(field_name).execute()
    if rows is None:
        return []
    if not isinstance(rows, list):
        raise RuntimeError(f"env_binding_field query must return rows: {table_name}.{field_name}")
    return [dict(row) for row in rows if isinstance(row, dict)]


def module_bound_env_ids(
    module_name: str,
    *,
    module_service: ModuleService | Any | None = None,
    context: TaskContext | None = None,
) -> set[int]:
    service = module_service or get_module_service()
    entries = _binding_field_entries(service, module_name, context)
    if not entries:
        return set()
    query_context = context
    if query_context is None:
        caps = build_runtime_capabilities(module_name)
        query_context = TaskContext(env_id=0, task_name=module_name, logger=logger, db=caps.db, tools=caps.tools)
    env_ids: set[int] = set()
    for table_name, field_name in entries:
        for row in _query_binding_rows(query_context, table_name, field_name):
            raw_env_id = row.get(field_name)
            if raw_env_id is None or raw_env_id == "":
                continue
            try:
                env_ids.add(int(raw_env_id))
            except (TypeError, ValueError):
                logger.warning(
                    "[REM] 忽略非法 env_binding_field 值: module=%s table=%s field=%s value=%r",
                    module_name,
                    table_name,
                    field_name,
                    raw_env_id,
                )
    return env_ids


def is_env_bound_by_module(
    env_id: int | str,
    module_name: str,
    *,
    module_service: ModuleService | Any | None = None,
    context: TaskContext | None = None,
) -> bool:
    return int(env_id) in module_bound_env_ids(module_name, module_service=module_service, context=context)


async def refresh_env_claim_after_task(
    rem: Any,
    env_id: int | str,
    *,
    module_name: str,
    task_id: str,
    module_service: ModuleService | Any | None = None,
    context: TaskContext | None = None,
) -> EnvClaim:
    if is_env_bound_by_module(env_id, module_name, module_service=module_service, context=context):
        await set_claimed_env_claim(rem, env_id, owner_module=module_name, task_id=task_id)
    else:
        await set_abandoned_env_claim(rem, env_id, owner_module=module_name, task_id=task_id)
    return await get_env_claim(rem, env_id)


async def recover_pending_env_claims(
    rem: Any,
    *,
    module_service: ModuleService | Any | None = None,
    task_repository: TaskRepository | Any | None = None,
) -> int:
    """Resolve pending claims left by interrupted task runs."""

    envs = await rem.list_envs()
    if not envs:
        return 0
    repo = task_repository or get_task_repository()
    active_tasks = await repo.get_running_tasks()
    active_task_ids = {task.id for task in active_tasks if task.status in ACTIVE_TASK_STATUSES}
    service = module_service or get_module_service()
    recovered = 0
    for env in envs:
        claim = await get_env_claim(rem, int(env.id))
        if not claim.is_pending:
            continue
        if claim.task_id and claim.task_id in active_task_ids:
            continue
        try:
            if claim.owner_module and is_env_bound_by_module(int(env.id), claim.owner_module, module_service=service):
                await set_claimed_env_claim(
                    rem,
                    int(env.id),
                    owner_module=claim.owner_module,
                    task_id=claim.task_id,
                )
            elif claim.owner_module:
                await set_abandoned_env_claim(
                    rem,
                    int(env.id),
                    owner_module=claim.owner_module,
                    task_id=claim.task_id,
                )
            recovered += 1
        except Exception as exc:
            logger.warning(
                "[REM] pending env claim recovery failed: env_id=%s owner=%s error=%s",
                env.id,
                claim.owner_module,
                exc,
            )
    return recovered

"""Debug session repository."""

from __future__ import annotations

import asyncio
import json

from src.core.debug.models import DebugSession
from src.core.persistence.database import STATE_DB, get_connection


class DebugSessionRepository:
    def __init__(self):
        self._ensure_tables()

    async def _run_async(self, func, *args):
        return await asyncio.get_running_loop().run_in_executor(None, func, *args)

    def _ensure_tables(self) -> None:
        with get_connection(STATE_DB) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS debug_sessions (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL DEFAULT '',
                    job_name TEXT NOT NULL DEFAULT '',
                    module_name TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    workflow TEXT NOT NULL,
                    object_bindings_json TEXT NOT NULL DEFAULT '{}',
                    object_params_json TEXT NOT NULL DEFAULT '{}',
                    provider TEXT NOT NULL,
                    acquisition_mode TEXT NOT NULL,
                    fixed_env_id INTEGER,
                    candidates TEXT NOT NULL DEFAULT '',
                    candidate_params_json TEXT NOT NULL DEFAULT '{}',
                    creation_params_json TEXT NOT NULL,
                    creation_lifecycle TEXT NOT NULL DEFAULT 'ephemeral',
                    wait_timeout INTEGER NOT NULL,
                    timeout INTEGER NOT NULL,
                    attach_host TEXT NOT NULL,
                    attach_port INTEGER NOT NULL,
                    wait_for_attach INTEGER NOT NULL,
                    stop_on_entry INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    worker_pid INTEGER,
                    env_id TEXT,
                    created_at INTEGER NOT NULL,
                    started_at INTEGER,
                    finished_at INTEGER,
                    last_error TEXT NOT NULL
                )
                """
            )
            existing_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(debug_sessions)").fetchall()
            }
            migrations = {
                "job_id": "ALTER TABLE debug_sessions ADD COLUMN job_id TEXT NOT NULL DEFAULT ''",
                "job_name": "ALTER TABLE debug_sessions ADD COLUMN job_name TEXT NOT NULL DEFAULT ''",
                "object_bindings_json": (
                    "ALTER TABLE debug_sessions ADD COLUMN object_bindings_json TEXT NOT NULL DEFAULT '{}'"
                ),
                "object_params_json": (
                    "ALTER TABLE debug_sessions ADD COLUMN object_params_json TEXT NOT NULL DEFAULT '{}'"
                ),
                "creation_lifecycle": (
                    "ALTER TABLE debug_sessions ADD COLUMN creation_lifecycle TEXT NOT NULL DEFAULT 'ephemeral'"
                ),
                "fixed_env_id": "ALTER TABLE debug_sessions ADD COLUMN fixed_env_id INTEGER",
                "candidates": "ALTER TABLE debug_sessions ADD COLUMN candidates TEXT NOT NULL DEFAULT ''",
                "candidate_params_json": (
                    "ALTER TABLE debug_sessions ADD COLUMN candidate_params_json TEXT NOT NULL DEFAULT '{}'"
                ),
            }
            for column, sql in migrations.items():
                if column not in existing_columns:
                    conn.execute(sql)

    async def save_session(self, session: DebugSession) -> None:
        def _do():
            self._ensure_tables()
            with get_connection(STATE_DB) as conn:
                conn.execute(
                    """
                    INSERT INTO debug_sessions (
                        id, job_id, job_name, module_name, source_path, workflow,
                        object_bindings_json, object_params_json,
                        provider, acquisition_mode, fixed_env_id, candidates, candidate_params_json,
                        creation_params_json, creation_lifecycle, wait_timeout, timeout,
                        attach_host, attach_port, wait_for_attach, stop_on_entry,
                        state, worker_pid, env_id, created_at, started_at, finished_at, last_error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        job_id = excluded.job_id,
                        job_name = excluded.job_name,
                        module_name = excluded.module_name,
                        source_path = excluded.source_path,
                        workflow = excluded.workflow,
                        object_bindings_json = excluded.object_bindings_json,
                        object_params_json = excluded.object_params_json,
                        provider = excluded.provider,
                        acquisition_mode = excluded.acquisition_mode,
                        fixed_env_id = excluded.fixed_env_id,
                        candidates = excluded.candidates,
                        candidate_params_json = excluded.candidate_params_json,
                        creation_params_json = excluded.creation_params_json,
                        creation_lifecycle = excluded.creation_lifecycle,
                        wait_timeout = excluded.wait_timeout,
                        timeout = excluded.timeout,
                        attach_host = excluded.attach_host,
                        attach_port = excluded.attach_port,
                        wait_for_attach = excluded.wait_for_attach,
                        stop_on_entry = excluded.stop_on_entry,
                        state = excluded.state,
                        worker_pid = excluded.worker_pid,
                        env_id = excluded.env_id,
                        started_at = excluded.started_at,
                        finished_at = excluded.finished_at,
                        last_error = excluded.last_error
                    """,
                    (
                        session.id,
                        session.job_id,
                        session.job_name,
                        session.module_name,
                        session.source_path,
                        session.workflow,
                        json.dumps(session.object_bindings, ensure_ascii=False),
                        json.dumps(session.object_params, ensure_ascii=False),
                        session.provider,
                        session.acquisition_mode.value,
                        session.fixed_env_id,
                        session.candidates,
                        json.dumps(session.candidate_params, ensure_ascii=False),
                        json.dumps(session.creation_params, ensure_ascii=False),
                        session.creation_lifecycle.value,
                        session.wait_timeout,
                        session.timeout,
                        session.attach_host,
                        session.attach_port,
                        int(session.wait_for_attach),
                        int(session.stop_on_entry),
                        session.state.value,
                        session.worker_pid,
                        session.env_id,
                        session.created_at,
                        session.started_at,
                        session.finished_at,
                        session.last_error,
                    ),
                )

        await self._run_async(_do)

    async def get_session(self, session_id: str) -> DebugSession | None:
        def _do():
            self._ensure_tables()
            with get_connection(STATE_DB) as conn:
                row = conn.execute(
                    "SELECT * FROM debug_sessions WHERE id = ?",
                    (session_id,),
                ).fetchone()
            return self._row_to_session(row) if row else None

        return await self._run_async(_do)

    async def list_sessions(self) -> list[DebugSession]:
        def _do():
            self._ensure_tables()
            with get_connection(STATE_DB) as conn:
                rows = conn.execute(
                    "SELECT * FROM debug_sessions ORDER BY created_at DESC"
                ).fetchall()
            return [self._row_to_session(row) for row in rows]

        return await self._run_async(_do)

    def _row_to_session(self, row) -> DebugSession:
        return DebugSession(
            id=row["id"],
            job_id=row["job_id"] or "",
            job_name=row["job_name"] or "",
            module_name=row["module_name"],
            source_path=row["source_path"],
            workflow=row["workflow"],
            object_bindings=(
                json.loads(row["object_bindings_json"])
                if "object_bindings_json" in row.keys() and row["object_bindings_json"]
                else {}
            ),
            object_params=(
                json.loads(row["object_params_json"])
                if "object_params_json" in row.keys() and row["object_params_json"]
                else {}
            ),
            provider=row["provider"],
            acquisition_mode=row["acquisition_mode"],
            fixed_env_id=row["fixed_env_id"] if "fixed_env_id" in row.keys() else None,
            candidates=row["candidates"] if "candidates" in row.keys() else "",
            candidate_params=(
                json.loads(row["candidate_params_json"])
                if "candidate_params_json" in row.keys() and row["candidate_params_json"]
                else {}
            ),
            creation_params=json.loads(row["creation_params_json"]) if row["creation_params_json"] else {},
            creation_lifecycle=row["creation_lifecycle"] or "ephemeral",
            wait_timeout=row["wait_timeout"],
            timeout=row["timeout"],
            attach_host=row["attach_host"],
            attach_port=row["attach_port"],
            wait_for_attach=bool(row["wait_for_attach"]),
            stop_on_entry=bool(row["stop_on_entry"]),
            state=row["state"],
            worker_pid=row["worker_pid"],
            env_id=row["env_id"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            last_error=row["last_error"] or "",
        )


_repository: DebugSessionRepository | None = None


def get_debug_session_repository() -> DebugSessionRepository:
    global _repository
    if _repository is None:
        _repository = DebugSessionRepository()
    return _repository

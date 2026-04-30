import json
import sqlite3
from unittest.mock import patch

import pytest


def _create_legacy_debug_sessions_table(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE debug_sessions (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL DEFAULT '',
            job_name TEXT NOT NULL DEFAULT '',
            module_name TEXT NOT NULL,
            source_path TEXT NOT NULL,
            workflow TEXT NOT NULL,
            execution_params_json TEXT NOT NULL DEFAULT '{}',
            job_params_json TEXT NOT NULL DEFAULT '{}',
            params_json TEXT NOT NULL,
            object_bindings_json TEXT NOT NULL DEFAULT '{}',
            object_params_json TEXT NOT NULL DEFAULT '{}',
            hooks_module TEXT NOT NULL,
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
            keep_environment INTEGER NOT NULL,
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
    conn.execute(
        """
        INSERT INTO debug_sessions (
            id, job_id, job_name, module_name, source_path, workflow,
            execution_params_json, job_params_json, params_json,
            object_bindings_json, object_params_json, hooks_module,
            provider, acquisition_mode, fixed_env_id, candidates, candidate_params_json,
            creation_params_json, creation_lifecycle, wait_timeout, timeout,
            attach_host, attach_port, wait_for_attach, stop_on_entry, keep_environment,
            state, worker_pid, env_id, created_at, started_at, finished_at, last_error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "debug-legacy",
            "job-legacy",
            "Legacy Job",
            "demo_module",
            "/tmp/demo",
            "repair",
            json.dumps({"lang": "zh-CN"}),
            json.dumps({"city": "Shanghai"}),
            json.dumps({"lang": "zh-CN", "city": "Shanghai"}),
            "{}",
            "{}",
            "demo_module.hooks",
            "virtualbrowser",
            "create",
            None,
            "",
            "{}",
            "{}",
            "ephemeral",
            60,
            120,
            "127.0.0.1",
            5678,
            1,
            0,
            0,
            "created",
            None,
            None,
            100,
            None,
            None,
            "",
        ),
    )
    conn.commit()
    conn.close()


@pytest.mark.asyncio
async def test_debug_repository_migrates_legacy_hooks_module_column_and_can_write(tmp_path):
    _create_legacy_debug_sessions_table(tmp_path / "state.db")

    with patch("src.utils.paths.get_app_data_dir", return_value=tmp_path):
        from src.core.debug.models import DebugSession
        from src.core.debug.repository import DebugSessionRepository
        from src.core.persistence.database import STATE_DB, get_connection

        repo = DebugSessionRepository()

        legacy_session = await repo.get_session("debug-legacy")

        assert legacy_session is not None
        assert legacy_session.module_name == "demo_module"

        await repo.save_session(
            DebugSession(
                id="debug-new",
                job_id="job-new",
                job_name="New Job",
                module_name="demo_module",
                source_path="/tmp/demo",
                workflow="repair",
                provider="virtualbrowser",
                acquisition_mode="create",
                creation_params={},
            )
        )

        with get_connection(STATE_DB) as conn:
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(debug_sessions)").fetchall()
            }
            saved = conn.execute(
                "SELECT module_name FROM debug_sessions WHERE id = ?",
                ("debug-new",),
            ).fetchone()

    assert "hooks_module" not in columns
    assert "execution_params_json" not in columns
    assert "job_params_json" not in columns
    assert "params_json" not in columns
    assert saved["module_name"] == "demo_module"

import json
import sqlite3
from unittest.mock import patch

import pytest


def _create_legacy_jobs_table(db_path):
    conn = sqlite3.connect(db_path)
    run_profile = {
        "resource": {
            "acquisition": {
                "mode": "create",
                "provider": "virtualbrowser",
                "wait_timeout": 30,
            },
        },
        "execution": {
            "module": "demo_module",
            "workflow": "repair",
            "params": {"lang": "zh-CN"},
            "object_bindings": {},
            "object_params": {},
            "timeout": 120,
            "hooks_module": "demo_module.hooks",
        },
    }
    conn.execute(
        """
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT,
            run_profile_json TEXT,
            trigger_config TEXT,
            concurrency_target INTEGER,
            params TEXT,
            state TEXT,
            created_at INTEGER,
            updated_at INTEGER
        )
        """
    )
    conn.execute(
        """
        INSERT INTO jobs (
            id, name, type, run_profile_json, trigger_config,
            concurrency_target, params, state, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "job-legacy",
            "Legacy Job",
            "batch",
            json.dumps(run_profile),
            json.dumps({"type": "manual"}),
            1,
            json.dumps({"city": "Shanghai"}),
            "paused",
            100,
            100,
        ),
    )
    conn.commit()
    conn.close()


@pytest.mark.asyncio
async def test_task_repository_reads_legacy_run_profile_and_saves_without_hooks_module(tmp_path):
    _create_legacy_jobs_table(tmp_path / "state.db")

    with patch("src.utils.paths.get_app_data_dir", return_value=tmp_path):
        from src.core.atm.repository import TaskRepository
        from src.core.persistence.database import STATE_DB, get_connection

        repo = TaskRepository()

        job = await repo.get_job("job-legacy")

        assert job is not None
        assert job.run_profile is not None
        assert job.run_profile.execution is not None
        assert job.run_profile.execution.module == "demo_module"
        assert not hasattr(job.run_profile.execution, "hooks_module")

        await repo.save_job(job)

        with get_connection(STATE_DB) as conn:
            row = conn.execute(
                "SELECT run_profile_json FROM jobs WHERE id = ?",
                ("job-legacy",),
            ).fetchone()

    saved_profile = json.loads(row["run_profile_json"])
    assert "hooks_module" not in saved_profile["execution"]

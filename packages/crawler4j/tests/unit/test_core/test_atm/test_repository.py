import json
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_task_repository_persists_current_run_profile_schema(tmp_path):
    with patch("src.utils.paths.get_app_data_dir", return_value=tmp_path):
        from src.core.atm.models import Job, JobState, JobType, TriggerConfig
        from src.core.atm.repository import TaskRepository
        from src.core.atm.run_profile import ExecutionContext, RunProfile
        from src.core.persistence.database import STATE_DB, get_connection

        repo = TaskRepository()
        job = Job(
            id="job-current",
            name="Current Job",
            type=JobType.BATCH,
            run_profile=RunProfile(
                execution=ExecutionContext(
                    module="demo_module",
                    workflow="repair",
                    object_bindings={},
                    object_params={},
                    timeout=120,
                )
            ),
            trigger=TriggerConfig(type="manual"),
            concurrency_target=1,
            state=JobState.PAUSED,
            created_at=100,
            updated_at=100,
        )

        await repo.save_job(job)
        loaded = await repo.get_job("job-current")

        assert loaded is not None
        assert loaded.run_profile is not None
        assert loaded.run_profile.execution is not None
        assert loaded.run_profile.execution.module == "demo_module"

        with get_connection(STATE_DB) as conn:
            row = conn.execute(
                "SELECT run_profile_json FROM jobs WHERE id = ?",
                ("job-current",),
            ).fetchone()

    saved_profile = json.loads(row["run_profile_json"])
    assert saved_profile["execution"] == {
        "module": "demo_module",
        "workflow": "repair",
        "object_bindings": {},
        "object_params": {},
        "timeout": 120,
    }
    assert "hooks_module" not in saved_profile["execution"]
    assert "params" not in saved_profile["execution"]

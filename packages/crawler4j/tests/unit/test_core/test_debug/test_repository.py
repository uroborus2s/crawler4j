from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_debug_repository_uses_current_session_schema_and_can_write(tmp_path):
    with patch("src.utils.paths.get_app_data_dir", return_value=tmp_path):
        from src.core.debug.models import DebugSession
        from src.core.debug.repository import DebugSessionRepository
        from src.core.persistence.database import STATE_DB, get_connection

        repo = DebugSessionRepository()

        await repo.save_session(
            DebugSession(
                id="debug-current",
                job_id="job-current",
                job_name="Current Job",
                module_name="demo_module",
                source_path="/tmp/demo",
                workflow="repair",
                provider="virtualbrowser",
                acquisition_mode="create",
                creation_params={},
            )
        )

        loaded = await repo.get_session("debug-current")

        with get_connection(STATE_DB) as conn:
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(debug_sessions)").fetchall()
            }
            saved = conn.execute(
                "SELECT module_name FROM debug_sessions WHERE id = ?",
                ("debug-current",),
            ).fetchone()

    assert loaded is not None
    assert loaded.module_name == "demo_module"
    assert saved["module_name"] == "demo_module"
    assert "hooks_module" not in columns
    assert "execution_params_json" not in columns
    assert "job_params_json" not in columns
    assert "params_json" not in columns
    assert "keep_environment" not in columns

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.atm.models import Job, JobType, TriggerConfig, TriggerType
from src.core.atm.run_profile import AcquisitionMode, EnvType, ExecutionContext, ResourceConfig, RunProfile
from src.core.mms.models import ModuleStatus
from src.core.rem.import_job_service import ExistingEnvImportJobService


@pytest.mark.asyncio
async def test_import_job_service_builds_fixed_env_run_profile():
    env = SimpleNamespace(
        id=21,
        name="VB Imported",
        provider="virtualbrowser",
        external_id="301",
    )
    registry = SimpleNamespace(
        get_module=lambda module_name: SimpleNamespace(
            name=module_name,
            status=ModuleStatus.ENABLED,
            manifest=SimpleNamespace(
                workflows=[SimpleNamespace(name="main_flow")],
            ),
        )
    )
    repo = SimpleNamespace(
        save_job=AsyncMock(),
    )
    dispatcher = SimpleNamespace(dispatch=AsyncMock(return_value="task-21"))
    rem = SimpleNamespace(
        import_existing_env=AsyncMock(return_value=env),
        mark_existing_env_import_state=AsyncMock(),
    )

    service = ExistingEnvImportJobService(
        rem=rem,
        registry=registry,
        repo=repo,
        dispatcher=dispatcher,
    )
    service._track_watch_task = lambda coro: getattr(coro, "close", lambda: None)()

    result = await service.import_and_run(
        provider_name="virtualbrowser",
        env_name="VB Imported",
        module_name="demo_module",
        workflow_name="main_flow",
    )

    saved_job = repo.save_job.await_args.args[0]
    assert saved_job.run_profile.resource.acquisition.mode == AcquisitionMode.SELECT
    assert saved_job.run_profile.resource.acquisition.env_id == 21
    assert saved_job.run_profile.resource.acquisition.env_type == EnvType.VIRTUAL_BROWSER
    assert saved_job.run_profile.resource.acquisition.creation.params == {
        "provider": "virtualbrowser",
        "name": "VB Imported",
        "provider_env_id": "301",
        "provider_env_name": "VB Imported",
        "import_mode": "existing_env",
    }
    dispatcher.dispatch.assert_awaited_once_with(saved_job)
    assert result.env is env
    assert result.task_id == "task-21"


@pytest.mark.asyncio
async def test_import_job_service_reuses_manual_job_and_respects_concurrency(monkeypatch):
    published = []
    monkeypatch.setattr(
        "src.core.rem.import_job_service.get_event_bus",
        lambda: SimpleNamespace(publish=published.append),
    )
    envs_by_name = {
        "VB Env 101": SimpleNamespace(
            id=101,
            name="VB Env 101",
            provider="virtualbrowser",
            external_id="vb-101",
        ),
        "VB Env 102": SimpleNamespace(
            id=102,
            name="VB Env 102",
            provider="virtualbrowser",
            external_id="vb-102",
        ),
    }
    job = Job(
        id="job-import",
        name="Import Ctrip Env",
        type=JobType.BATCH,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        concurrency_target=1,
        run_profile=RunProfile(
            resource=ResourceConfig(),
            execution=ExecutionContext(module="demo_module", workflow="import_flow"),
        ),
    )
    registry = SimpleNamespace(
        get_module=lambda module_name: SimpleNamespace(
            name=module_name,
            status=ModuleStatus.ENABLED,
            manifest=SimpleNamespace(
                workflows=[SimpleNamespace(name="import_flow")],
            ),
        )
    )
    repo = SimpleNamespace(
        get_job=AsyncMock(return_value=job),
        save_job=AsyncMock(),
        count_active_tasks=AsyncMock(return_value=0),
    )
    dispatcher = SimpleNamespace(dispatch=AsyncMock(return_value="task-101"))
    rem = SimpleNamespace(
        import_existing_env=AsyncMock(side_effect=lambda _provider, name: envs_by_name[name]),
        mark_existing_env_import_state=AsyncMock(),
    )

    service = ExistingEnvImportJobService(
        rem=rem,
        registry=registry,
        repo=repo,
        dispatcher=dispatcher,
    )
    service._track_watch_task = lambda coro: getattr(coro, "close", lambda: None)()

    result = await service.import_and_run_with_job(
        provider_name="virtualbrowser",
        env_names=["VB Env 101", "VB Env 102"],
        job_id="job-import",
    )

    repo.save_job.assert_not_awaited()
    assert dispatcher.dispatch.await_count == 1
    dispatched_job = dispatcher.dispatch.await_args.args[0]
    assert dispatched_job.id == "job-import"
    assert dispatched_job.run_profile.resource.acquisition.mode == AcquisitionMode.SELECT
    assert dispatched_job.run_profile.resource.acquisition.env_id == 101
    assert dispatched_job.run_profile.resource.acquisition.creation.params == {
        "provider": "virtualbrowser",
        "name": "VB Env 101",
        "provider_env_id": "vb-101",
        "provider_env_name": "VB Env 101",
        "import_mode": "existing_env",
    }
    assert [env.id for env in result.envs] == [101, 102]
    assert result.job_id == "job-import"
    assert result.task_ids == ["task-101"]
    assert published
    assert published[0].data["phase"] == "queued"
    assert published[0].data["job_id"] == "job-import"
    assert published[0].data["job_name"] == "Import Ctrip Env"
    assert published[0].data["queued_count"] == 1

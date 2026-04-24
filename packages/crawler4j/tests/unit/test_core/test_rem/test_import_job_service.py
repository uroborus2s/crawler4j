from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.atm.run_profile import AcquisitionMode, EnvType
from src.core.mms.models import ModuleStatus
from src.core.rem.import_job_service import ExistingEnvImportJobService


@pytest.mark.asyncio
async def test_import_job_service_builds_fixed_env_run_profile():
    env = SimpleNamespace(
        id=21,
        name="imported-env",
        provider="virtualbrowser",
        provider_env_id="301",
        external_id="301",
        provider_env_name="VB Imported",
        provider_group="默认分组",
        provider_proxy={"protocol": "SOCKS5", "host": "127.0.0.1", "port": "1080"},
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
        provider_env_id="301",
        module_name="demo_module",
        workflow_name="main_flow",
    )

    saved_job = repo.save_job.await_args.args[0]
    assert saved_job.run_profile.resource.acquisition.mode == AcquisitionMode.SELECT
    assert saved_job.run_profile.resource.acquisition.env_id == 21
    assert saved_job.run_profile.resource.acquisition.env_type == EnvType.VIRTUAL_BROWSER
    assert saved_job.run_profile.resource.acquisition.creation.params == {
        "provider": "virtualbrowser",
        "provider_env_id": "301",
        "provider_env_name": "VB Imported",
        "provider_group": "默认分组",
        "provider_proxy": {"protocol": "SOCKS5", "host": "127.0.0.1", "port": "1080"},
        "import_mode": "existing_env",
    }
    dispatcher.dispatch.assert_awaited_once_with(saved_job)
    assert result.env is env
    assert result.task_id == "task-21"

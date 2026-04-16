from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from crawler4j_contracts import EnvAction, TaskResult, TaskSignal

from src.core.atm.dispatcher import TaskDispatcher
from src.core.atm.models import Job, Task, TaskStatus
from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    CreationConfig,
    EnvType,
    ExecutionContext,
    ResourceConfig,
    RunProfile,
)
from src.core.foundation.event_bus import EventType
from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource
from src.core.rem.models import Environment, EnvKind, EnvLease, EnvStatus


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    from src.core.persistence.database import init_database

    init_database()
    yield tmp_path


def _build_run_profile(timeout: int = 0) -> RunProfile:
    return RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                provider="virtualbrowser",
                env_type=EnvType.VIRTUAL_BROWSER,
                creation=CreationConfig(params={"groups": ["default"]}),
            ),
        ),
        execution=ExecutionContext(
            module="example_module",
            workflow="default",
            hooks_module="example_module",
            timeout=timeout,
            params={"seed": 1},
        ),
    )


def _build_env() -> tuple[Environment, EnvLease]:
    env = Environment(
        id=21,
        name="env-21",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        external_id="ext-21",
    )
    lease = EnvLease(id="lease-21", env_id=env.id, task_run_id="task-21", token="token-21")
    return env, lease


def _build_dispatcher(env: Environment, lease: EnvLease) -> TaskDispatcher:
    dispatcher = TaskDispatcher()
    dispatcher.repo = SimpleNamespace(save_task=AsyncMock())
    dispatcher.rem = SimpleNamespace(
        create_env=AsyncMock(return_value=env),
        lease_manager=SimpleNamespace(
            acquire=AsyncMock(return_value=lease),
            get_lease=AsyncMock(return_value=lease),
        ),
        start_env=AsyncMock(return_value=True),
        get_env=AsyncMock(return_value=env),
        recycle_env=AsyncMock(return_value=None),
        release=AsyncMock(return_value=True),
        release_keep_alive=AsyncMock(return_value=True),
        destroy_env=AsyncMock(return_value=True),
    )
    return dispatcher


@pytest.mark.asyncio
async def test_dispatcher_calls_success_hooks_and_merges_prepare_env(monkeypatch):
    run_profile = _build_run_profile()
    env, lease = _build_env()
    module_service = SimpleNamespace(run_module=AsyncMock(return_value={"status": "ok"}))

    async def hook(module_name, hook_name, context, *args):
        if hook_name == "prepare_env":
            return {"creation_params": {"fingerprint": {"randomize_all": True}}}
        return None

    module_service.call_hook = AsyncMock(side_effect=hook)
    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = _build_dispatcher(env, lease)
    task = Task(id="task-21", job_id="job-21")
    job = Job(id="job-21", name="job", run_profile=run_profile)

    await dispatcher._run_logic(task, job)

    dispatcher.rem.create_env.assert_awaited_once()
    assert dispatcher.rem.create_env.await_args.kwargs["ensure_runtime"] is False
    create_config = dispatcher.rem.create_env.await_args.kwargs["config"]
    assert create_config["creation_params"]["groups"] == ["default"]
    assert create_config["creation_params"]["fingerprint"]["randomize_all"] is True
    dispatcher.rem.start_env.assert_not_awaited()

    hook_names = [call.args[1] for call in module_service.call_hook.await_args_list]
    assert hook_names == ["prepare_env", "init_env", "before_run", "on_success", "on_cleanup"]
    assert task.status == TaskStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_dispatcher_calls_failure_and_cleanup_hooks_on_error(monkeypatch):
    run_profile = _build_run_profile()
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(side_effect=RuntimeError("boom")),
        call_hook=AsyncMock(return_value=None),
    )

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = _build_dispatcher(env, lease)
    task = Task(id="task-21", job_id="job-21")
    job = Job(id="job-21", name="job", run_profile=run_profile)

    await dispatcher._run_logic(task, job)

    hook_names = [call.args[1] for call in module_service.call_hook.await_args_list]
    assert hook_names == ["prepare_env", "init_env", "before_run", "on_failure", "on_cleanup"]
    assert task.status == TaskStatus.FAILED
    assert "boom" in task.error


@pytest.mark.asyncio
async def test_dispatcher_calls_timeout_and_cleanup_hooks_on_timeout(monkeypatch):
    run_profile = _build_run_profile(timeout=1)
    env, lease = _build_env()

    async def slow_run(module_name, context):
        await context.wait(1.2)
        return {"status": "late"}

    module_service = SimpleNamespace(
        run_module=AsyncMock(side_effect=slow_run),
        call_hook=AsyncMock(return_value=None),
    )

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = _build_dispatcher(env, lease)
    task = Task(id="task-21", job_id="job-21")
    job = Job(id="job-21", name="job", run_profile=run_profile)

    await dispatcher._run_logic(task, job)

    hook_names = [call.args[1] for call in module_service.call_hook.await_args_list]
    assert hook_names == ["prepare_env", "init_env", "before_run", "on_timeout", "on_cleanup"]
    assert task.status == TaskStatus.FAILED
    assert "Timeout" in task.error


@pytest.mark.asyncio
async def test_dispatcher_cleans_up_created_env_when_acquisition_fails(monkeypatch):
    run_profile = _build_run_profile()
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value={"status": "ok"}),
        call_hook=AsyncMock(return_value=None),
    )

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = _build_dispatcher(env, lease)
    dispatcher.rem.lease_manager.acquire = AsyncMock(side_effect=RuntimeError("lease failed"))

    task = Task(id="task-21", job_id="job-21")
    job = Job(id="job-21", name="job", run_profile=run_profile)

    await dispatcher._run_logic(task, job)

    assert task.status == TaskStatus.FAILED
    dispatcher.rem.release.assert_not_awaited()
    dispatcher.rem.recycle_env.assert_awaited_once_with(env)
    dispatcher.rem.destroy_env.assert_not_awaited()
    module_service.run_module.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatcher_confirms_waiting_task_and_runs_cleanup(monkeypatch):
    run_profile = _build_run_profile()
    env, lease = _build_env()
    cleanup_env_actions: list[dict[str, object]] = []

    async def hook(module_name, hook_name, context, *args):
        if hook_name == "on_cleanup":
            cleanup_env_actions.append(dict(context.runtime.get("env_action") or {}))
        return None

    module_service = SimpleNamespace(
        run_module=AsyncMock(
            return_value=TaskResult.ok(
                message="等待用户确认",
                signal=TaskSignal.wait_for_confirmation(
                    message="等待用户确认",
                    env_action=EnvAction.KEEP_ALIVE,
                ),
            )
        ),
        call_hook=AsyncMock(side_effect=hook),
    )

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = _build_dispatcher(env, lease)
    task = Task(id="task-21", job_id="job-21")
    dispatcher.repo.get_task = AsyncMock(return_value=task)
    job = Job(id="job-21", name="job", run_profile=run_profile)

    await dispatcher._run_logic(task, job)

    assert task.status == TaskStatus.WAITING_CONFIRMATION
    assert task.id in dispatcher._waiting_tasks
    dispatcher.rem.release.assert_not_awaited()
    dispatcher.rem.release_keep_alive.assert_not_awaited()
    dispatcher.rem.destroy_env.assert_not_awaited()

    confirmed = await dispatcher.confirm_task(task.id, success=False, message="黑号")

    assert confirmed is True
    assert task.status == TaskStatus.FAILED
    assert task.error == "黑号"
    assert task.id not in dispatcher._waiting_tasks
    dispatcher.rem.lease_manager.get_lease.assert_awaited_once_with(lease.id)
    dispatcher.rem.release.assert_awaited_once_with(lease)
    dispatcher.rem.release_keep_alive.assert_not_awaited()
    dispatcher.rem.destroy_env.assert_not_awaited()
    assert cleanup_env_actions == [
        {
            "action": "recycle",
            "env_id": env.id,
            "success": True,
        }
    ]

    hook_names = [call.args[1] for call in module_service.call_hook.await_args_list]
    assert hook_names == ["prepare_env", "init_env", "before_run", "on_failure", "on_cleanup"]


def test_dispatcher_publish_task_terminal_event(monkeypatch):
    dispatcher = TaskDispatcher()
    publish = MagicMock()
    monkeypatch.setattr("src.core.atm.dispatcher.get_event_bus", lambda: SimpleNamespace(publish=publish))

    dispatcher._publish_task_event(
        Task(id="task-1", job_id="job-1", status=TaskStatus.SUCCEEDED, env_id="12", error="")
    )
    dispatcher._publish_task_event(
        Task(id="task-2", job_id="job-2", status=TaskStatus.FAILED, env_id="21", error="boom")
    )
    dispatcher._publish_task_event(
        Task(id="task-3", job_id="job-3", status=TaskStatus.CANCELLED, env_id="33", error="cancel")
    )

    assert publish.call_count == 3
    first_event = publish.call_args_list[0].args[0]
    second_event = publish.call_args_list[1].args[0]
    third_event = publish.call_args_list[2].args[0]

    assert first_event.type == EventType.TASK_FINISHED
    assert first_event.data["job_id"] == "job-1"
    assert second_event.type == EventType.TASK_FAILED
    assert second_event.data["error"] == "boom"
    assert third_event.type == EventType.TASK_CANCELLED


def test_dispatcher_publish_waiting_confirmation_signal_event(monkeypatch):
    dispatcher = TaskDispatcher()
    publish = MagicMock()
    monkeypatch.setattr("src.core.atm.dispatcher.get_event_bus", lambda: SimpleNamespace(publish=publish))

    signal = TaskSignal.wait_for_confirmation(
        message="等待人工确认",
        env_action=EnvAction.KEEP_ALIVE,
        payload={
            "confirmation": {
                "title": "账号复核",
                "fields": [{"label": "账号", "value": "demo-account"}],
            }
        },
    ).to_dict()
    dispatcher._publish_task_signal_event(
        Task(
            id="task-wait-1",
            job_id="job-1",
            status=TaskStatus.WAITING_CONFIRMATION,
            message="等待人工确认",
            signal=signal,
        )
    )

    event = publish.call_args.args[0]
    assert event.type == EventType.TASK_SIGNAL
    assert event.task_run_id == "task-wait-1"
    assert event.data["job_id"] == "job-1"
    assert event.data["signal"]["payload"]["confirmation"]["title"] == "账号复核"


def test_dispatcher_clear_stop_for_job():
    dispatcher = TaskDispatcher()
    dispatcher._job_stop_requests.add("job-1")
    dispatcher.clear_stop_for_job("job-1")
    assert "job-1" not in dispatcher._job_stop_requests


@pytest.mark.asyncio
async def test_dispatcher_marks_dev_link_tasks_for_reload(monkeypatch):
    run_profile = _build_run_profile()
    env, lease = _build_env()
    seen_runtimes: list[dict[str, object]] = []
    module_info = ModuleInfo(
        name="example_module",
        manifest=ModuleManifest(name="example_module"),
        source=ModuleSource.DEV_LINK,
        path=Path("/tmp/example_module"),
    )

    async def hook(module_name, hook_name, context, *args):
        seen_runtimes.append(dict(context.runtime))
        return None

    async def run_module(module_name, context):
        seen_runtimes.append(dict(context.runtime))
        return {"status": "ok"}

    module_service = SimpleNamespace(
        registry=SimpleNamespace(get_module=lambda module_name: module_info),
        run_module=AsyncMock(side_effect=run_module),
        call_hook=AsyncMock(side_effect=hook),
    )

    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = _build_dispatcher(env, lease)
    task = Task(id="task-dev-link", job_id="job-dev-link")
    job = Job(id="job-dev-link", name="job", run_profile=run_profile)

    await dispatcher._run_logic(task, job)

    assert task.status == TaskStatus.SUCCEEDED
    assert seen_runtimes
    assert all(runtime["devel_mode"] is True for runtime in seen_runtimes)

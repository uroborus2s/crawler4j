from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.atm.dispatcher import TaskDispatcher
from src.core.atm.models import Job, Task, TaskStatus
from src.core.foundation.event_bus import EventType
from src.core.rem.models import Environment, EnvKind, EnvLease, EnvStatus
from src.core.tsm.models import (
    AcquisitionConfig,
    AcquisitionMode,
    CreationConfig,
    EnvType,
    ExecutionContext,
    MatchConfig,
    ResourceConfig,
    TaskStrategy,
)


def _build_strategy(timeout: int = 0) -> TaskStrategy:
    return TaskStrategy(
        id="hooked-strategy",
        name="hooked-strategy",
        resource=ResourceConfig(
            provider="virtualbrowser",
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                selector=MatchConfig(env_type=EnvType.VIRTUAL_BROWSER),
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
        lease_manager=SimpleNamespace(acquire=AsyncMock(return_value=lease)),
        start_env=AsyncMock(return_value=True),
        get_env=AsyncMock(return_value=env),
        release=AsyncMock(return_value=True),
        destroy_env=AsyncMock(return_value=True),
    )
    return dispatcher


@pytest.mark.asyncio
async def test_dispatcher_calls_success_hooks_and_merges_prepare_env(monkeypatch):
    strategy = _build_strategy()
    env, lease = _build_env()

    loader = SimpleNamespace(get=lambda strategy_id: strategy)
    module_service = SimpleNamespace(run_module=AsyncMock(return_value={"status": "ok"}))

    async def hook(module_name, hook_name, context, *args):
        if hook_name == "prepare_env":
            return {"creation_params": {"fingerprint": {"randomize_all": True}}}
        return None

    module_service.call_hook = AsyncMock(side_effect=hook)

    monkeypatch.setattr("src.core.tsm.get_strategy_loader", lambda: loader)
    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = _build_dispatcher(env, lease)
    task = Task(id="task-21", job_id="job-21")
    job = Job(id="job-21", name="job", strategy_id=strategy.id)

    await dispatcher._run_logic(task, job)

    dispatcher.rem.create_env.assert_awaited_once()
    assert dispatcher.rem.create_env.await_args.kwargs["ensure_runtime"] is False
    create_config = dispatcher.rem.create_env.await_args.kwargs["config"]
    assert create_config["creation_params"]["groups"] == ["default"]
    assert create_config["creation_params"]["fingerprint"]["randomize_all"] is True

    hook_names = [call.args[1] for call in module_service.call_hook.await_args_list]
    assert hook_names == ["prepare_env", "init_env", "before_run", "on_success", "on_cleanup"]
    assert task.status == TaskStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_dispatcher_calls_failure_and_cleanup_hooks_on_error(monkeypatch):
    strategy = _build_strategy()
    env, lease = _build_env()

    loader = SimpleNamespace(get=lambda strategy_id: strategy)
    module_service = SimpleNamespace(
        run_module=AsyncMock(side_effect=RuntimeError("boom")),
        call_hook=AsyncMock(return_value=None),
    )

    monkeypatch.setattr("src.core.tsm.get_strategy_loader", lambda: loader)
    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = _build_dispatcher(env, lease)
    task = Task(id="task-21", job_id="job-21")
    job = Job(id="job-21", name="job", strategy_id=strategy.id)

    await dispatcher._run_logic(task, job)

    hook_names = [call.args[1] for call in module_service.call_hook.await_args_list]
    assert hook_names == ["prepare_env", "init_env", "before_run", "on_failure", "on_cleanup"]
    assert task.status == TaskStatus.FAILED
    assert "boom" in task.error


@pytest.mark.asyncio
async def test_dispatcher_calls_timeout_and_cleanup_hooks_on_timeout(monkeypatch):
    strategy = _build_strategy(timeout=1)
    env, lease = _build_env()

    loader = SimpleNamespace(get=lambda strategy_id: strategy)

    async def slow_run(module_name, context):
        await context.wait(1.2)
        return {"status": "late"}

    module_service = SimpleNamespace(
        run_module=AsyncMock(side_effect=slow_run),
        call_hook=AsyncMock(return_value=None),
    )

    monkeypatch.setattr("src.core.tsm.get_strategy_loader", lambda: loader)
    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = _build_dispatcher(env, lease)
    task = Task(id="task-21", job_id="job-21")
    job = Job(id="job-21", name="job", strategy_id=strategy.id)

    await dispatcher._run_logic(task, job)

    hook_names = [call.args[1] for call in module_service.call_hook.await_args_list]
    assert hook_names == ["prepare_env", "init_env", "before_run", "on_timeout", "on_cleanup"]
    assert task.status == TaskStatus.FAILED
    assert "Timeout" in task.error


@pytest.mark.asyncio
async def test_dispatcher_cleans_up_created_env_when_acquisition_fails(monkeypatch):
    strategy = _build_strategy()
    env, lease = _build_env()

    loader = SimpleNamespace(get=lambda strategy_id: strategy)
    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value={"status": "ok"}),
        call_hook=AsyncMock(return_value=None),
    )

    monkeypatch.setattr("src.core.tsm.get_strategy_loader", lambda: loader)
    monkeypatch.setattr("src.core.mms.service.get_module_service", lambda: module_service)

    dispatcher = _build_dispatcher(env, lease)
    dispatcher.rem.start_env = AsyncMock(return_value=False)

    task = Task(id="task-21", job_id="job-21")
    job = Job(id="job-21", name="job", strategy_id=strategy.id)

    await dispatcher._run_logic(task, job)

    assert task.status == TaskStatus.FAILED
    dispatcher.rem.release.assert_awaited_once_with(lease)
    dispatcher.rem.destroy_env.assert_awaited_once_with(env.id)
    module_service.run_module.assert_not_awaited()


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


def test_dispatcher_clear_stop_for_job():
    dispatcher = TaskDispatcher()
    dispatcher._job_stop_requests.add("job-1")
    dispatcher.clear_stop_for_job("job-1")
    assert "job-1" not in dispatcher._job_stop_requests

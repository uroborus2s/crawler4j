from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.atm.execution_runner import ExecutionRequest, ExecutionRunner
from src.core.atm.models import Task, TaskStatus
from src.core.rem.models import Environment, EnvKind, EnvLease, EnvStatus
from src.core.atm.run_profile import AcquisitionMode, CreationLifecycle


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


def _build_request(
    *,
    mode: AcquisitionMode = AcquisitionMode.CREATE,
    timeout: int = 0,
    lifecycle: CreationLifecycle = CreationLifecycle.EPHEMERAL,
) -> ExecutionRequest:
    return ExecutionRequest(
        task=Task(id="task-21", job_id="job-21"),
        module_name="example_module",
        hooks_module="example_module",
        params={"seed": 1, "workflow": "default"},
        state={
            "job_id": "job-21",
            "task_id": "task-21",
        },
        provider_name="virtualbrowser",
        acquisition_mode=mode,
        selector_wait_timeout=60,
        creation_params={"groups": ["default"]},
        creation_lifecycle=lifecycle,
        execution_timeout=timeout,
    )


def _build_runner(env: Environment, lease: EnvLease, module_service) -> tuple[ExecutionRunner, SimpleNamespace]:
    rem = SimpleNamespace(
        acquire_atomic=AsyncMock(return_value=lease),
        create_env=AsyncMock(return_value=env),
        lease_manager=SimpleNamespace(acquire=AsyncMock(return_value=lease)),
        start_env=AsyncMock(return_value=True),
        get_env=AsyncMock(return_value=env),
        release=AsyncMock(return_value=True),
        destroy_env=AsyncMock(return_value=True),
    )
    return ExecutionRunner(rem=rem, mms=module_service), rem


@pytest.mark.asyncio
async def test_execution_runner_calls_success_hooks_and_merges_prepare_env():
    request = _build_request()
    env, lease = _build_env()

    async def hook(module_name, hook_name, context, *args):
        if hook_name == "prepare_env":
            return {"creation_params": {"fingerprint": {"randomize_all": True}}}
        return None

    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value={"status": "ok"}),
        call_hook=AsyncMock(side_effect=hook),
    )
    runner, rem = _build_runner(env, lease, module_service)

    updates: list[TaskStatus] = []
    contexts = []

    async def on_task_update(task: Task):
        updates.append(task.status)

    await runner.run(request, on_task_update=on_task_update, on_context_ready=contexts.append)

    rem.create_env.assert_awaited_once()
    assert rem.create_env.await_args.kwargs["ensure_runtime"] is False
    create_config = rem.create_env.await_args.kwargs["config"]
    assert create_config["creation_params"]["groups"] == ["default"]
    assert create_config["creation_params"]["fingerprint"]["randomize_all"] is True

    hook_names = [call.args[1] for call in module_service.call_hook.await_args_list]
    assert hook_names == ["prepare_env", "init_env", "before_run", "on_success", "on_cleanup"]
    assert updates == [TaskStatus.RUNNING, TaskStatus.SUCCEEDED]
    assert request.task.status == TaskStatus.SUCCEEDED
    assert request.task.env_id == str(env.id)
    assert contexts
    assert contexts[0].config["workflow"] == "default"
    assert contexts[0].tools is not None
    assert module_service.call_hook.await_args_list[0].args[2].tools is not None
    rem.release.assert_awaited_once_with(lease)
    rem.destroy_env.assert_awaited_once_with(env.id)


@pytest.mark.asyncio
async def test_execution_runner_calls_failure_and_cleanup_hooks_on_error():
    request = _build_request()
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(side_effect=RuntimeError("boom")),
        call_hook=AsyncMock(return_value=None),
    )
    runner, rem = _build_runner(env, lease, module_service)

    updates: list[TaskStatus] = []

    async def on_task_update(task: Task):
        updates.append(task.status)

    await runner.run(request, on_task_update=on_task_update)

    hook_names = [call.args[1] for call in module_service.call_hook.await_args_list]
    assert hook_names == ["prepare_env", "init_env", "before_run", "on_failure", "on_cleanup"]
    assert updates == [TaskStatus.RUNNING, TaskStatus.FAILED]
    assert request.task.status == TaskStatus.FAILED
    assert "boom" in request.task.error
    rem.release.assert_awaited_once_with(lease)
    rem.destroy_env.assert_awaited_once_with(env.id)


@pytest.mark.asyncio
async def test_execution_runner_calls_timeout_and_cleanup_hooks_on_timeout():
    request = _build_request(timeout=1)
    env, lease = _build_env()

    async def slow_run(module_name, context):
        await context.wait(1.2)
        return {"status": "late"}

    module_service = SimpleNamespace(
        run_module=AsyncMock(side_effect=slow_run),
        call_hook=AsyncMock(return_value=None),
    )
    runner, rem = _build_runner(env, lease, module_service)

    await runner.run(request)

    hook_names = [call.args[1] for call in module_service.call_hook.await_args_list]
    assert hook_names == ["prepare_env", "init_env", "before_run", "on_timeout", "on_cleanup"]
    assert request.task.status == TaskStatus.FAILED
    assert "Timeout" in request.task.error
    rem.release.assert_awaited_once_with(lease)
    rem.destroy_env.assert_awaited_once_with(env.id)


@pytest.mark.asyncio
async def test_execution_runner_cleans_up_created_env_when_acquisition_fails():
    request = _build_request()
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value={"status": "ok"}),
        call_hook=AsyncMock(return_value=None),
    )
    runner, rem = _build_runner(env, lease, module_service)
    rem.start_env = AsyncMock(return_value=False)

    await runner.run(request)

    assert request.task.status == TaskStatus.FAILED
    rem.release.assert_awaited_once_with(lease)
    rem.destroy_env.assert_awaited_once_with(env.id)
    module_service.run_module.assert_not_awaited()


@pytest.mark.asyncio
async def test_execution_runner_reuses_existing_env_for_match_mode():
    request = _build_request(mode=AcquisitionMode.MATCH, lifecycle=CreationLifecycle.PERSISTENT)
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value="ok"),
        call_hook=AsyncMock(return_value=None),
    )
    runner, rem = _build_runner(env, lease, module_service)

    await runner.run(request)

    rem.acquire_atomic.assert_awaited_once()
    rem.create_env.assert_not_awaited()
    rem.start_env.assert_awaited_once_with(env.id)
    module_service.run_module.assert_awaited_once()
    rem.release.assert_awaited_once_with(lease)
    rem.destroy_env.assert_not_awaited()
    assert request.task.status == TaskStatus.SUCCEEDED

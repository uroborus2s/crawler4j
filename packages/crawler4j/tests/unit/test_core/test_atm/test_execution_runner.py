from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from crawler4j_contracts import EnvAction, TaskResult, TaskSignal
from src.core.atm.execution_runner import ExecutionRequest, ExecutionRunner
from src.core.atm.models import Task, TaskStatus
from src.core.atm.run_profile import AcquisitionMode, CreationLifecycle
from src.core.foundation.logging import logger as app_logger
from src.core.rem.models import Environment, EnvKind, EnvLease, EnvStatus
from src.core.rem.models import ProxyMode


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
    lifecycle: CreationLifecycle = CreationLifecycle.PERSISTENT,
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
        reset=AsyncMock(return_value=None),
        release=AsyncMock(return_value=True),
        release_keep_alive=AsyncMock(return_value=True),
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
    rem.start_env.assert_not_awaited()

    hook_names = [call.args[1] for call in module_service.call_hook.await_args_list]
    assert hook_names == ["prepare_env", "init_env", "before_run", "on_success", "on_cleanup"]
    assert updates == [TaskStatus.RUNNING, TaskStatus.SUCCEEDED]
    assert request.task.status == TaskStatus.SUCCEEDED
    assert request.task.env_id == str(env.id)
    assert contexts
    assert contexts[0].config["workflow"] == "default"
    assert contexts[0].logger is app_logger
    assert contexts[0].tools is not None
    assert module_service.call_hook.await_args_list[0].args[2].tools is not None
    rem.release.assert_awaited_once_with(lease)
    rem.release_keep_alive.assert_not_awaited()
    rem.destroy_env.assert_not_awaited()


@pytest.mark.asyncio
async def test_execution_runner_routes_module_logs_through_app_logger():
    request = _build_request()
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(
            side_effect=lambda _module_name, context: context.logger.info("[test] module log") or TaskResult.ok()
        ),
        call_hook=AsyncMock(
            side_effect=lambda _module_name, hook_name, context, *args: (
                context.logger.info("[test] before_run log") if hook_name == "before_run" else None
            )
        ),
    )
    runner, _rem = _build_runner(env, lease, module_service)

    old_entries = list(app_logger._entries)
    app_logger._entries = []
    try:
        await runner.run(request)
        messages = [entry.message for entry in app_logger.get_entries(limit=20)]
    finally:
        app_logger._entries = old_entries

    assert "[test] before_run log" in messages
    assert "[test] module log" in messages


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
    rem.release_keep_alive.assert_not_awaited()
    rem.destroy_env.assert_not_awaited()


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
    rem.release_keep_alive.assert_not_awaited()
    rem.destroy_env.assert_not_awaited()


@pytest.mark.asyncio
async def test_execution_runner_cleans_up_created_env_when_acquisition_fails():
    request = _build_request()
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value={"status": "ok"}),
        call_hook=AsyncMock(return_value=None),
    )
    runner, rem = _build_runner(env, lease, module_service)
    rem.lease_manager.acquire = AsyncMock(side_effect=RuntimeError("lease failed"))

    await runner.run(request)

    assert request.task.status == TaskStatus.FAILED
    rem.get_env.assert_awaited_once_with(env.id)
    rem.reset.assert_awaited_once_with(env)
    rem.release.assert_not_awaited()
    rem.destroy_env.assert_not_awaited()
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


@pytest.mark.asyncio
async def test_execution_runner_marks_task_failed_for_taskresult_fail():
    request = _build_request()
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value=TaskResult.fail(message="black", error="black_account")),
        call_hook=AsyncMock(return_value=None),
    )
    runner, rem = _build_runner(env, lease, module_service)

    await runner.run(request)

    assert request.task.status == TaskStatus.FAILED
    assert request.task.error == "black_account"
    rem.release.assert_awaited_once_with(lease)
    rem.release_keep_alive.assert_not_awaited()
    rem.destroy_env.assert_not_awaited()


@pytest.mark.asyncio
async def test_execution_runner_wait_signal_keeps_task_waiting_confirmation():
    request = _build_request()
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(
            return_value=TaskResult.ok(
                message="等待确认",
                signal=TaskSignal.wait_for_confirmation(
                    message="等待确认",
                    env_action=EnvAction.KEEP_ALIVE,
                ),
            )
        ),
        call_hook=AsyncMock(return_value=None),
    )
    runner, rem = _build_runner(env, lease, module_service)

    execution_result = await runner.run(request)

    assert request.task.status == TaskStatus.WAITING_CONFIRMATION
    assert request.task.finished_at is None
    rem.release.assert_not_awaited()
    rem.release_keep_alive.assert_not_awaited()
    rem.destroy_env.assert_not_awaited()
    assert execution_result.signal is not None
    assert execution_result.signal.action.value == "wait_for_confirmation"


@pytest.mark.asyncio
async def test_execution_runner_exposes_env_action_to_cleanup_hook():
    request = _build_request()
    env, lease = _build_env()
    cleanup_env_actions: list[dict[str, object]] = []

    async def hook(module_name, hook_name, context, *args):
        if hook_name == "on_cleanup":
            cleanup_env_actions.append(dict(context.runtime.get("env_action") or {}))
        return None

    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value=TaskResult.ok(message="ok")),
        call_hook=AsyncMock(side_effect=hook),
    )
    runner, _ = _build_runner(env, lease, module_service)

    await runner.run(request)

    assert cleanup_env_actions == [
        {
            "action": "recycle",
            "env_id": env.id,
            "success": True,
        }
    ]


@pytest.mark.asyncio
async def test_execution_runner_destroys_env_only_when_signal_requests_it():
    request = _build_request()
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(
            return_value=TaskResult.ok(
                message="ok",
                signal=TaskSignal.succeed(message="ok", env_action=EnvAction.DESTROY),
            )
        ),
        call_hook=AsyncMock(return_value=None),
    )
    runner, rem = _build_runner(env, lease, module_service)

    await runner.run(request)

    rem.release.assert_not_awaited()
    rem.release_keep_alive.assert_awaited_once_with(lease)
    rem.destroy_env.assert_awaited_once_with(env.id)


@pytest.mark.asyncio
async def test_execution_runner_promotes_proxy_binding_from_creation_params():
    request = _build_request()
    request.creation_params = {
        "groups": ["default"],
        "proxy": {"mode": ProxyMode.POOL.value, "pool_id": "pool-1"},
    }
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value={"status": "ok"}),
        call_hook=AsyncMock(return_value=None),
    )
    runner, rem = _build_runner(env, lease, module_service)

    await runner.run(request)

    create_kwargs = rem.create_env.await_args.kwargs
    assert create_kwargs["config"]["creation_params"] == {"groups": ["default"]}
    assert create_kwargs["requirement"].proxy_config is not None
    assert create_kwargs["requirement"].proxy_config.mode == ProxyMode.POOL
    assert create_kwargs["requirement"].proxy_config.pool_id == "pool-1"

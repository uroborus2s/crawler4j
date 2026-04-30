import asyncio
import sys
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from crawler4j_contracts import TaskResult
from src.core.atm.execution_runner import ExecutionRequest, ExecutionRunner
from src.core.atm.models import Task, TaskStatus
from src.core.atm.run_profile import AcquisitionMode, CreationLifecycle
from src.core.foundation.logging import logger as app_logger
from src.core.rem.models import Environment, EnvKind, EnvLease, EnvStatus
from src.core.rem.models import ProxyMode


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    from src.core.persistence.database import init_database

    init_database()
    yield tmp_path


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
        workflow_name="default",
        state={
            "job_id": "job-21",
            "task_id": "task-21",
        },
        provider_name="virtualbrowser",
        acquisition_mode=mode,
        wait_timeout=60,
        creation_params={"groups": ["default"]},
        creation_lifecycle=lifecycle,
        execution_timeout=timeout,
    )


def _build_runner(env: Environment, lease: EnvLease, module_service) -> tuple[ExecutionRunner, SimpleNamespace]:
    if not hasattr(module_service, "get_runtime_descriptor_v2"):
        module_service.get_runtime_descriptor_v2 = Mock(return_value=SimpleNamespace(data_tables={}))
    metadata_store: dict[tuple[int, str, str], object] = {}

    async def set_metadata(env_id: int, namespace: str, key: str, value, value_type: str = "string"):
        metadata_store[(int(env_id), namespace, key)] = value

    async def list_metadata(env_id: int, namespace: str):
        return {
            key: value
            for (stored_env_id, stored_namespace, key), value in metadata_store.items()
            if stored_env_id == int(env_id) and stored_namespace == namespace
        }

    rem = SimpleNamespace(
        acquire_atomic=AsyncMock(return_value=lease),
        create_env=AsyncMock(return_value=env),
        list_envs=AsyncMock(return_value=[env]),
        set_metadata=AsyncMock(side_effect=set_metadata),
        list_metadata=AsyncMock(side_effect=list_metadata),
        metadata_store=metadata_store,
        lease_manager=SimpleNamespace(
            acquire=AsyncMock(return_value=lease),
            claim_created_env=AsyncMock(return_value=lease),
        ),
        start_env=AsyncMock(return_value=True),
        get_env=AsyncMock(return_value=env),
        recycle_env=AsyncMock(return_value=None),
        release=AsyncMock(return_value=True),
        release_keep_alive=AsyncMock(return_value=True),
        destroy_env=AsyncMock(return_value=True),
    )
    return ExecutionRunner(rem=rem, mms=module_service), rem


def test_execution_runner_uses_configured_default_timeout_budgets():
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value=TaskResult.ok(message="ok")),
    )

    runner, _ = _build_runner(env, lease, module_service)

    assert runner._env_recycle_timeout_seconds == 60.0


def test_execution_runner_reads_timeout_budget_overrides_from_config_center():
    from src.core.system.config_center import get_config_center

    config = get_config_center()
    config.set("atm.env_recycle_timeout_seconds", 90)

    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value=TaskResult.ok(message="ok")),
    )

    runner, _ = _build_runner(env, lease, module_service)

    assert runner._env_recycle_timeout_seconds == 90.0


@pytest.mark.asyncio
async def test_execution_runner_marks_module_cancel_reason_on_timeout():
    request = _build_request(timeout=0.01)
    env, lease = _build_env()
    cancel_reasons: list[str | None] = []

    async def run_module(_module_name, context):
        try:
            await asyncio.sleep(10)
        finally:
            cancel_reasons.append(context.runtime.get("_module_cancel_reason"))

    module_service = SimpleNamespace(run_module=run_module)
    runner, _ = _build_runner(env, lease, module_service)

    await runner.run(request)

    assert request.task.status == TaskStatus.FAILED
    assert cancel_reasons == ["timed_out"]


def _write_runtime_module_fixture(base_dir: Path, module_name: str) -> Path:
    module_dir = base_dir / module_name
    workflows_dir = module_dir / "workflows"
    for package_dir in (
        module_dir,
        module_dir / "interfaces",
        module_dir / "objects",
        workflows_dir,
        module_dir / "tasks",
        module_dir / "data",
    ):
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

    (module_dir / "runtime_db.py").write_text(
        dedent(
            """
            def record_event(context, event_type, *, entity_key=None, created_at=None, payload=None):
                event_id = context.db.audit("runtime_events").append(
                    event_type=event_type,
                    entity_key=entity_key,
                    created_at=created_at,
                    payload=dict(payload or {}),
                )
                return {"id": event_id, "event_type": event_type}
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (workflows_dir / "default.py").write_text(
        dedent(
            """
            from crawler4j_contracts import TaskContext, TaskResult, workflow
            from ..runtime_db import record_event


            @workflow(name="default")
            class DefaultWorkflow:
                async def run(self, ctx: TaskContext) -> TaskResult:
                    if not ctx.page:
                        return TaskResult.fail(message="missing page", error="page_missing")

                    start_url = ctx.get_config("start_url", "https://example.com/fallback")
                    await ctx.page.goto(start_url, wait_until="domcontentloaded")
                    title = await ctx.page.title()
                    html = await ctx.page.content()

                    record_event(
                        ctx,
                        "workflow.capture",
                        entity_key=ctx.page.url,
                        created_at=500,
                        payload={"title": title, "html_length": len(html)},
                    )

                    return TaskResult.ok(
                        message="page captured",
                        data={
                            "url": ctx.page.url,
                            "title": title,
                            "html": html,
                        },
                    )
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    return module_dir


def _purge_loaded_module(module_name: str) -> None:
    prefix = f"{module_name}."
    for loaded_name in list(sys.modules):
        if loaded_name == module_name or loaded_name.startswith(prefix):
            sys.modules.pop(loaded_name, None)


@pytest.mark.asyncio
async def test_execution_runner_runs_module_and_recycles_environment():
    from src.core.mms.settings_store import ModuleSettingsStore

    request = _build_request()
    env, lease = _build_env()
    store = ModuleSettingsStore()
    store.write_module_settings("example_module", {"accounts": {"default": "u1"}, "region": "cn"})
    store.write_workflow_settings("example_module", "default", {"accounts": {"enabled": True}})

    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value={"status": "ok"}),
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
    assert "fingerprint" not in create_config["creation_params"]
    rem.lease_manager.claim_created_env.assert_awaited_once_with(env, request.task.id)
    rem.start_env.assert_not_awaited()

    assert updates == [TaskStatus.RUNNING, TaskStatus.SUCCEEDED]
    assert request.task.status == TaskStatus.SUCCEEDED
    assert request.task.env_id == str(env.id)
    assert contexts
    assert contexts[0].config == {
        "accounts": {"default": "u1", "enabled": True},
        "region": "cn",
    }
    assert contexts[0].runtime["workflow"] == "default"
    assert "params" not in contexts[0].runtime
    assert "execution_params" not in contexts[0].runtime
    assert "job_params" not in contexts[0].runtime
    assert "runtime_params" not in contexts[0].runtime
    assert contexts[0].logger is app_logger
    assert contexts[0].tools is not None
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
    )
    runner, _rem = _build_runner(env, lease, module_service)

    old_entries = list(app_logger._entries)
    app_logger._entries = []
    try:
        await runner.run(request)
        messages = [entry.message for entry in app_logger.get_entries(limit=20)]
    finally:
        app_logger._entries = old_entries

    assert "[test] module log" in messages


@pytest.mark.asyncio
async def test_execution_runner_marks_failure_on_module_error():
    request = _build_request()
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(side_effect=RuntimeError("boom")),
    )
    runner, rem = _build_runner(env, lease, module_service)

    updates: list[TaskStatus] = []

    async def on_task_update(task: Task):
        updates.append(task.status)

    await runner.run(request, on_task_update=on_task_update)

    assert updates == [TaskStatus.RUNNING, TaskStatus.FAILED]
    assert request.task.status == TaskStatus.FAILED
    assert "boom" in request.task.error
    rem.release.assert_awaited_once_with(lease)
    rem.release_keep_alive.assert_not_awaited()
    rem.destroy_env.assert_not_awaited()


@pytest.mark.asyncio
async def test_execution_runner_marks_failure_on_execution_timeout():
    request = _build_request(timeout=1)
    env, lease = _build_env()

    async def slow_run(module_name, context):
        await context.wait(1.2)
        return {"status": "late"}

    module_service = SimpleNamespace(
        run_module=AsyncMock(side_effect=slow_run),
    )
    runner, rem = _build_runner(env, lease, module_service)

    await runner.run(request)

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
    )
    runner, rem = _build_runner(env, lease, module_service)
    rem.lease_manager.claim_created_env = AsyncMock(side_effect=RuntimeError("lease failed"))

    await runner.run(request)

    assert request.task.status == TaskStatus.FAILED
    rem.get_env.assert_awaited_once_with(env.id)
    rem.recycle_env.assert_awaited_once_with(env)
    rem.release.assert_not_awaited()
    rem.destroy_env.assert_not_awaited()
    module_service.run_module.assert_not_awaited()


@pytest.mark.asyncio
async def test_execution_runner_selects_first_ready_env_without_module_selector():
    request = _build_request(mode=AcquisitionMode.SELECT, lifecycle=CreationLifecycle.PERSISTENT)
    request.candidates_name = "ready_accounts"
    env, lease = _build_env()

    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value="ok"),
        resolve_env_candidates=Mock(return_value=[env.id]),
    )
    runner, rem = _build_runner(env, lease, module_service)
    runner._is_env_candidate_authorized = AsyncMock(return_value=True)
    updates: list[tuple[TaskStatus, str]] = []

    async def on_task_update(task: Task):
        updates.append((task.status, task.message))

    await runner.run(request, on_task_update=on_task_update)

    rem.list_envs.assert_awaited_once()
    rem.lease_manager.acquire.assert_awaited_once_with(env, request.task.id, timeout=60)
    rem.create_env.assert_not_awaited()
    rem.start_env.assert_awaited_once_with(env.id)
    module_service.run_module.assert_awaited_once()
    rem.release.assert_awaited_once_with(lease)
    rem.destroy_env.assert_not_awaited()
    assert request.task.status == TaskStatus.SUCCEEDED
    assert updates[:2] == [(TaskStatus.PENDING, "环境启动中"), (TaskStatus.RUNNING, "")]


@pytest.mark.asyncio
async def test_execution_runner_selects_fixed_env_without_module_selector():
    request = _build_request(mode=AcquisitionMode.SELECT, lifecycle=CreationLifecycle.PERSISTENT)
    request.fixed_env_id = 21
    env, lease = _build_env()

    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value="ok"),
    )
    runner, rem = _build_runner(env, lease, module_service)

    await runner.run(request)

    rem.get_env.assert_any_await(env.id)
    assert rem.get_env.await_count == 2
    rem.list_envs.assert_not_awaited()
    rem.lease_manager.acquire.assert_awaited_once_with(env, request.task.id, timeout=60)
    module_service.run_module.assert_awaited_once()
    assert request.task.status == TaskStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_execution_runner_marks_task_failed_for_taskresult_fail():
    request = _build_request()
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value=TaskResult.fail(message="black", error="black_account")),
    )
    runner, rem = _build_runner(env, lease, module_service)

    await runner.run(request)

    assert request.task.status == TaskStatus.FAILED
    assert request.task.error == "black_account"
    rem.release.assert_awaited_once_with(lease)
    rem.release_keep_alive.assert_not_awaited()
    rem.destroy_env.assert_not_awaited()


@pytest.mark.asyncio
async def test_execution_runner_records_env_recycle_after_releasing_environment():
    request = _build_request()
    env, lease = _build_env()

    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value=TaskResult.ok(message="ok")),
    )
    runner, rem = _build_runner(env, lease, module_service)

    result = await runner.run(request)

    assert result.task_context is not None
    assert result.task_context.runtime["env_recycle"]["action"] == "recycle"
    assert result.task_context.runtime["env_recycle"]["success"] is True
    rem.release.assert_awaited_once_with(lease)


@pytest.mark.asyncio
async def test_execution_runner_times_out_hanging_env_recycle_and_still_finishes_task():
    request = _build_request()
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value=TaskResult.ok(message="ok")),
    )
    runner, rem = _build_runner(env, lease, module_service)
    runner._env_recycle_timeout_seconds = 0.01

    async def hanging_release(*_args, **_kwargs):
        await asyncio.Event().wait()

    rem.release = AsyncMock(side_effect=hanging_release)

    execution_result = await asyncio.wait_for(runner.run(request), timeout=0.5)

    assert request.task.status == TaskStatus.SUCCEEDED
    assert execution_result.task_context is not None
    assert execution_result.task_context.runtime["env_recycle"]["action"] == "recycle"
    assert execution_result.task_context.runtime["env_recycle"]["success"] is False
    assert "timed out after" in execution_result.task_context.runtime["env_recycle"]["error"]
    rem.release.assert_awaited_once_with(lease)
    rem.release_keep_alive.assert_not_awaited()
    rem.destroy_env.assert_not_awaited()


@pytest.mark.asyncio
async def test_execution_runner_recycles_env_for_cancelled_task():
    request = _build_request()
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value=TaskResult.ok(message="ok")),
    )
    runner, rem = _build_runner(env, lease, module_service)
    stop_checks = iter([False, False, True])

    await runner.run(
        request,
        is_stop_requested=lambda: next(stop_checks, True),
    )

    assert request.task.status == TaskStatus.CANCELLED
    rem.release.assert_awaited_once_with(lease)
    rem.release_keep_alive.assert_not_awaited()
    rem.destroy_env.assert_not_awaited()


@pytest.mark.asyncio
async def test_execution_runner_interrupts_running_module_when_stop_requested():
    request = _build_request()
    env, lease = _build_env()
    module_started = asyncio.Event()
    module_cancelled = asyncio.Event()
    stop_requested = False

    async def blocking_run(module_name, context):
        module_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            module_cancelled.set()
            raise

    module_service = SimpleNamespace(
        run_module=AsyncMock(side_effect=blocking_run),
    )
    runner, rem = _build_runner(env, lease, module_service)

    run_task = asyncio.create_task(
        runner.run(
            request,
            is_stop_requested=lambda: stop_requested,
        )
    )

    await module_started.wait()
    stop_requested = True
    await asyncio.wait_for(run_task, timeout=0.5)

    assert request.task.status == TaskStatus.CANCELLED
    assert request.task.error == "Job paused during execution"
    assert module_cancelled.is_set()
    rem.release.assert_awaited_once_with(lease)
    rem.release_keep_alive.assert_not_awaited()
    rem.destroy_env.assert_not_awaited()


@pytest.mark.asyncio
async def test_execution_runner_recycles_env_during_acquisition_cleanup():
    request = _build_request()
    env, lease = _build_env()
    module_service = SimpleNamespace(
        run_module=AsyncMock(return_value=TaskResult.ok(message="ok")),
    )
    runner, rem = _build_runner(env, lease, module_service)
    stop_checks = iter([False, True])

    await runner.run(
        request,
        is_stop_requested=lambda: next(stop_checks, True),
    )

    assert request.task.status == TaskStatus.CANCELLED
    rem.release.assert_awaited_once_with(lease)
    rem.release_keep_alive.assert_not_awaited()
    rem.destroy_env.assert_not_awaited()
    module_service.run_module.assert_not_awaited()


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
    )
    runner, rem = _build_runner(env, lease, module_service)

    await runner.run(request)

    create_kwargs = rem.create_env.await_args.kwargs
    assert create_kwargs["config"]["creation_params"] == {"groups": ["default"]}
    assert create_kwargs["requirement"].proxy_config is not None
    assert create_kwargs["requirement"].proxy_config.mode == ProxyMode.POOL
    assert create_kwargs["requirement"].proxy_config.pool_id == "pool-1"


@pytest.mark.asyncio
async def test_execution_runner_runs_real_core_native_v2_module_and_audit_events(tmp_path):
    from src.core.mms.models import ModuleInfo, ModuleManifest
    from src.core.mms.service import ModuleService
    from src.core.mms.settings_store import ModuleSettingsStore
    from src.core.persistence import get_module_data_store

    module_name = "functional_runtime_module"
    module_dir = _write_runtime_module_fixture(tmp_path, module_name)
    env, lease = _build_env()

    class _FakePage:
        def __init__(self):
            self.url = "about:blank"
            self._title = "Module Runtime Title"
            self._html = "<html><body><h1>Runtime Content</h1></body></html>"
            self.visits: list[tuple[str, str | None]] = []

        async def goto(self, url: str, wait_until: str | None = None):
            self.url = url
            self.visits.append((url, wait_until))

        async def title(self) -> str:
            return self._title

        async def content(self) -> str:
            return self._html

    fake_page = _FakePage()
    env.capabilities = {"page"}
    env.handle = SimpleNamespace(page=fake_page, context=SimpleNamespace(name="browser-context"))
    manifest_data = {"resources": [], "views": [], "queries": [], "seeds": []}

    module_service = ModuleService()
    module_service.registry = SimpleNamespace(
        get_module=lambda name: ModuleInfo(
            name=module_name,
            manifest=ModuleManifest(name=module_name, runtime_api="core-native-v2", data=manifest_data),
            path=module_dir,
        )
    )

    store = ModuleSettingsStore()
    store.write_module_settings(module_name, {"start_url": "https://example.com/runtime"})

    request = _build_request(mode=AcquisitionMode.CREATE, lifecycle=CreationLifecycle.PERSISTENT)
    request.module_name = module_name
    request.workflow_name = "default"

    runner, rem = _build_runner(env, lease, module_service)

    try:
        execution_result = await runner.run(request)
    finally:
        _purge_loaded_module(module_name)

    assert execution_result.task.status == TaskStatus.SUCCEEDED
    assert execution_result.result is not None
    assert execution_result.result.data == {
        "url": "https://example.com/runtime",
        "title": "Module Runtime Title",
        "html": "<html><body><h1>Runtime Content</h1></body></html>",
    }
    assert fake_page.visits == [("https://example.com/runtime", "domcontentloaded")]

    rem.create_env.assert_awaited_once()
    rem.lease_manager.claim_created_env.assert_awaited_once_with(env, request.task.id)
    rem.release.assert_awaited_once_with(lease)
    rem.release_keep_alive.assert_not_awaited()
    rem.destroy_env.assert_not_awaited()

    events = get_module_data_store().query_audit_events(module_name, "runtime_events", order="asc")
    assert [event["event_type"] for event in events] == ["workflow.capture"]
    assert events[0]["dataset_name"] == "runtime_events"
    assert events[0]["entity_key"] == "https://example.com/runtime"
    assert events[0]["payload"] == {
        "title": "Module Runtime Title",
        "html_length": len("<html><body><h1>Runtime Content</h1></body></html>"),
    }

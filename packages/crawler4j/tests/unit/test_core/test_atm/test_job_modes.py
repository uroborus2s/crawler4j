import asyncio
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from unittest.mock import patch

import pytest
from crawler4j_contracts import EnvAction, TaskSignal

from src.core.atm.controller import JobController
from src.core.atm.models import Job, JobState, JobType, Task, TaskStatus, TriggerConfig, TriggerType
from src.core.atm.repository import TaskRepository
from src.core.atm.service import TaskService
from src.core.foundation.event_bus import Event, EventType
from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    ExecutionContext,
    MatchConfig,
    ResourceConfig,
    RunProfile,
)


@pytest.fixture
def temp_state_dir(tmp_path):
    with patch("src.utils.paths.get_app_data_dir", return_value=tmp_path):
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


@pytest.mark.asyncio
async def test_service_job_maintains_target_concurrency():
    controller = JobController()
    controller.repo = SimpleNamespace(count_active_tasks=AsyncMock(return_value=1))
    controller.dispatcher = SimpleNamespace(dispatch=AsyncMock())

    job = Job(
        id="service-job",
        name="service",
        type=JobType.SERVICE,
        state=JobState.ACTIVE,
        concurrency_target=3,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
    )

    await controller._reconcile_job(job)

    assert controller.dispatcher.dispatch.await_count == 2


@pytest.mark.asyncio
async def test_batch_job_registers_cron_schedule_on_reconcile():
    controller = JobController()
    controller._scheduler = SimpleNamespace(add_job=MagicMock(), remove_job=MagicMock())
    controller.dispatcher = SimpleNamespace(dispatch=AsyncMock())

    job = Job(
        id="batch-job",
        name="batch",
        type=JobType.BATCH,
        state=JobState.ACTIVE,
        concurrency_target=4,
        trigger=TriggerConfig(type=TriggerType.CRON, cron_expr="0 * * * *"),
    )

    await controller._reconcile_job(job)

    controller._scheduler.add_job.assert_called_once()
    add_job_kwargs = controller._scheduler.add_job.call_args.kwargs
    assert add_job_kwargs["id"] == "batch:batch-job"
    assert add_job_kwargs["args"] == ["batch-job"]
    assert controller._batch_job_ids["batch-job"] == "batch:batch-job"


@pytest.mark.asyncio
async def test_batch_job_dispatches_full_batch_when_cron_trigger_fires():
    controller = JobController()
    job = Job(
        id="batch-job",
        name="batch",
        type=JobType.BATCH,
        state=JobState.ACTIVE,
        concurrency_target=4,
        trigger=TriggerConfig(type=TriggerType.CRON, cron_expr="0 * * * *"),
    )
    controller.repo = SimpleNamespace(
        get_job=AsyncMock(return_value=job),
        count_active_tasks=AsyncMock(return_value=0),
    )
    controller.dispatcher = SimpleNamespace(dispatch=AsyncMock())

    await controller._on_batch_cron_fire(job.id)

    assert controller.dispatcher.dispatch.await_count == 4


@pytest.mark.asyncio
async def test_batch_job_skips_trigger_when_previous_batch_still_running():
    controller = JobController()
    job = Job(
        id="batch-job",
        name="batch",
        type=JobType.BATCH,
        state=JobState.ACTIVE,
        concurrency_target=4,
        trigger=TriggerConfig(type=TriggerType.CRON, cron_expr="0 * * * *"),
    )
    controller.repo = SimpleNamespace(
        get_job=AsyncMock(return_value=job),
        count_active_tasks=AsyncMock(return_value=2),
    )
    controller.dispatcher = SimpleNamespace(dispatch=AsyncMock())

    await controller._on_batch_cron_fire(job.id)

    controller.dispatcher.dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_pause_job_requests_stop_for_service_tasks():
    service = TaskService()
    job = Job(
        id="service-job",
        name="service",
        type=JobType.SERVICE,
        state=JobState.ACTIVE,
        concurrency_target=2,
    )
    service._repo = SimpleNamespace(get_job=AsyncMock(return_value=job), save_job=AsyncMock())
    service._controller = SimpleNamespace(request_job_stop=AsyncMock())

    result = await service.pause_job(job.id)

    assert result is True
    assert job.state == JobState.PAUSED
    service._repo.save_job.assert_awaited_once_with(job)
    service._controller.request_job_stop.assert_awaited_once_with(job.id)


@pytest.mark.asyncio
async def test_service_counts_active_tasks():
    service = TaskService()
    service._repo = SimpleNamespace(count_active_tasks=AsyncMock(return_value=2))

    count = await service.count_active_tasks("job-manual")

    assert count == 2
    service._repo.count_active_tasks.assert_awaited_once_with("job-manual")


@pytest.mark.asyncio
async def test_start_job_triggers_targeted_reconcile():
    service = TaskService()
    job = Job(
        id="service-job",
        name="service",
        type=JobType.SERVICE,
        state=JobState.PAUSED,
        run_profile=RunProfile(
            resource=ResourceConfig(
                provider="virtualbrowser",
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.MATCH,
                    selector=MatchConfig(wait_timeout=60),
                ),
            ),
            execution=ExecutionContext(module="demo_module", workflow="repair"),
        ),
        concurrency_target=2,
    )
    service._repo = SimpleNamespace(get_job=AsyncMock(return_value=job), save_job=AsyncMock())
    service._controller = SimpleNamespace(
        ensure_job_runtime_ready=AsyncMock(),
        request_job_resume=AsyncMock(),
        reconcile_job=AsyncMock(),
    )

    result = await service.start_job(job.id)
    assert result is True
    assert job.state == JobState.ACTIVE
    service._repo.save_job.assert_awaited_once_with(job)
    service._controller.request_job_resume.assert_awaited_once_with(job.id)

    await asyncio.sleep(0)
    service._controller.reconcile_job.assert_awaited_once_with(job.id)


@pytest.mark.asyncio
async def test_start_job_blocks_when_runtime_precheck_fails():
    service = TaskService()
    job = Job(
        id="service-job",
        name="service",
        type=JobType.SERVICE,
        state=JobState.PAUSED,
        run_profile=RunProfile(
            resource=ResourceConfig(
                provider="virtualbrowser",
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.MATCH,
                    selector=MatchConfig(wait_timeout=60),
                ),
            ),
            execution=ExecutionContext(module="demo_module", workflow="repair"),
        ),
        concurrency_target=2,
    )
    service._repo = SimpleNamespace(get_job=AsyncMock(return_value=job), save_job=AsyncMock())
    service._controller = SimpleNamespace(
        ensure_job_runtime_ready=AsyncMock(side_effect=RuntimeError("runtime not ready")),
        request_job_resume=AsyncMock(),
        reconcile_job=AsyncMock(),
    )

    result = await service.start_job(job.id)

    assert result is False
    assert job.state == JobState.PAUSED
    service._repo.save_job.assert_not_awaited()
    service._controller.request_job_resume.assert_not_awaited()
    service._controller.reconcile_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_service_job_forces_manual_trigger():
    service = TaskService()
    saved_jobs = []
    service._repo = SimpleNamespace(save_job=AsyncMock(side_effect=lambda job: saved_jobs.append(job)))
    run_profile = RunProfile(
        resource=ResourceConfig(
            provider="virtualbrowser",
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.MATCH,
                selector=MatchConfig(wait_timeout=60),
            ),
        ),
        execution=ExecutionContext(module="demo_module", workflow="repair"),
    )

    await service.create_job(
        name="service-job",
        job_type=JobType.SERVICE.value,
        trigger_config={"type": TriggerType.CRON.value, "cron_expr": "*/5 * * * *"},
        run_profile=run_profile,
        concurrency=2,
    )

    assert len(saved_jobs) == 1
    assert saved_jobs[0].trigger.type == TriggerType.MANUAL
    assert saved_jobs[0].trigger.cron_expr is None


@pytest.mark.asyncio
async def test_create_batch_job_accepts_manual_or_valid_cron():
    service = TaskService()
    saved_jobs = []
    service._repo = SimpleNamespace(save_job=AsyncMock(side_effect=lambda job: saved_jobs.append(job)))
    run_profile = RunProfile(
        resource=ResourceConfig(
            provider="virtualbrowser",
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.MATCH,
                selector=MatchConfig(wait_timeout=60),
            ),
        ),
        execution=ExecutionContext(module="demo_module", workflow="repair"),
    )

    await service.create_job(
        name="batch-job-manual",
        job_type=JobType.BATCH.value,
        trigger_config={"type": TriggerType.MANUAL.value},
        run_profile=run_profile,
        concurrency=2,
    )

    assert len(saved_jobs) == 1
    assert saved_jobs[0].trigger.type == TriggerType.MANUAL
    assert saved_jobs[0].trigger.cron_expr is None

    with pytest.raises(ValueError, match="Cron"):
        await service.create_job(
            name="batch-job-invalid",
            job_type=JobType.BATCH.value,
            trigger_config={"type": TriggerType.CRON.value, "cron_expr": "invalid-cron"},
            run_profile=run_profile,
            concurrency=2,
        )


@pytest.mark.asyncio
async def test_create_job_accepts_inline_run_profile():
    service = TaskService()
    saved_jobs = []
    service._repo = SimpleNamespace(save_job=AsyncMock(side_effect=lambda job: saved_jobs.append(job)))

    run_profile = RunProfile(
        resource=ResourceConfig(
            provider="virtualbrowser",
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.MATCH,
                selector=MatchConfig(wait_timeout=90),
            ),
        ),
        execution=ExecutionContext(module="demo_module", workflow="repair"),
    )

    await service.create_job(
        name="inline-job",
        job_type=JobType.BATCH.value,
        trigger_config={"type": TriggerType.CRON.value, "cron_expr": "0 * * * *"},
        run_profile=run_profile,
        concurrency=2,
    )

    assert len(saved_jobs) == 1
    assert saved_jobs[0].run_profile == run_profile


@pytest.mark.asyncio
async def test_run_job_once_dispatches_manual_batch_without_activating_job():
    service = TaskService()
    job = Job(
        id="batch-manual-job",
        name="manual-batch",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        run_profile=RunProfile(
            resource=ResourceConfig(
                provider="virtualbrowser",
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.MATCH,
                    selector=MatchConfig(wait_timeout=60),
                ),
            ),
            execution=ExecutionContext(module="demo_module", workflow="repair"),
        ),
        concurrency_target=3,
    )
    service._repo = SimpleNamespace(
        get_job=AsyncMock(return_value=job),
        save_job=AsyncMock(),
        count_active_tasks=AsyncMock(return_value=0),
    )
    service._controller = SimpleNamespace(
        ensure_job_runtime_ready=AsyncMock(),
        dispatcher=SimpleNamespace(dispatch=AsyncMock()),
    )

    result = await service.run_job_once(job.id)

    assert result is True
    assert job.state == JobState.PAUSED
    service._repo.save_job.assert_not_awaited()
    service._controller.ensure_job_runtime_ready.assert_awaited_once_with(job.id)
    assert service._controller.dispatcher.dispatch.await_count == 3


@pytest.mark.asyncio
async def test_start_job_runs_manual_batch_once():
    service = TaskService()
    job = Job(
        id="batch-manual-job",
        name="manual-batch",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        run_profile=RunProfile(
            resource=ResourceConfig(
                provider="virtualbrowser",
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.MATCH,
                    selector=MatchConfig(wait_timeout=60),
                ),
            ),
            execution=ExecutionContext(module="demo_module", workflow="repair"),
        ),
        concurrency_target=2,
    )
    service._repo = SimpleNamespace(
        get_job=AsyncMock(return_value=job),
        save_job=AsyncMock(),
        count_active_tasks=AsyncMock(return_value=0),
    )
    service._controller = SimpleNamespace(
        ensure_job_runtime_ready=AsyncMock(),
        dispatcher=SimpleNamespace(dispatch=AsyncMock()),
        request_job_resume=AsyncMock(),
        reconcile_job=AsyncMock(),
    )

    result = await service.start_job(job.id)

    assert result is True
    assert job.state == JobState.PAUSED
    service._repo.save_job.assert_not_awaited()
    service._controller.request_job_resume.assert_not_awaited()
    service._controller.reconcile_job.assert_not_awaited()
    assert service._controller.dispatcher.dispatch.await_count == 2


@pytest.mark.asyncio
async def test_run_job_once_blocks_when_previous_batch_still_running():
    service = TaskService()
    job = Job(
        id="batch-manual-job",
        name="manual-batch",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        run_profile=RunProfile(
            resource=ResourceConfig(
                provider="virtualbrowser",
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.MATCH,
                    selector=MatchConfig(wait_timeout=60),
                ),
            ),
            execution=ExecutionContext(module="demo_module", workflow="repair"),
        ),
        concurrency_target=2,
    )
    service._repo = SimpleNamespace(
        get_job=AsyncMock(return_value=job),
        save_job=AsyncMock(),
        count_active_tasks=AsyncMock(return_value=1),
    )
    service._controller = SimpleNamespace(
        ensure_job_runtime_ready=AsyncMock(),
        dispatcher=SimpleNamespace(dispatch=AsyncMock()),
    )

    result = await service.run_job_once(job.id)

    assert result is False
    service._repo.save_job.assert_not_awaited()
    service._controller.dispatcher.dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_job_switches_manual_batch_to_paused_and_requests_stop():
    service = TaskService()
    job = Job(
        id="service-job",
        name="service",
        type=JobType.SERVICE,
        state=JobState.ACTIVE,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        run_profile=RunProfile(
            resource=ResourceConfig(
                provider="virtualbrowser",
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.MATCH,
                    selector=MatchConfig(wait_timeout=60),
                ),
            ),
            execution=ExecutionContext(module="demo_module", workflow="repair"),
        ),
        concurrency_target=2,
    )
    service._repo = SimpleNamespace(get_job=AsyncMock(return_value=job), save_job=AsyncMock())
    service._controller = SimpleNamespace(
        request_job_stop=AsyncMock(),
        reconcile_job=AsyncMock(),
    )

    result = await service.update_job(
        job.id,
        job_type=JobType.BATCH.value,
        trigger_config={"type": TriggerType.MANUAL.value},
    )

    assert result is True
    assert job.type == JobType.BATCH
    assert job.trigger.type == TriggerType.MANUAL
    assert job.state == JobState.PAUSED
    service._controller.request_job_stop.assert_awaited_once_with(job.id)
    service._controller.reconcile_job.assert_not_awaited()


@pytest.mark.asyncio
async def test_repository_roundtrip_preserves_run_profile_snapshot(temp_state_dir):
    repo = TaskRepository()
    repo._run_async = AsyncMock(side_effect=lambda func, *args: func(*args))

    run_profile = RunProfile(
        resource=ResourceConfig(
            provider="virtualbrowser",
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.MATCH,
                selector=MatchConfig(wait_timeout=75),
            ),
        ),
        execution=ExecutionContext(module="demo_module", workflow="repair"),
    )
    job = Job(
        id="job-inline",
        name="inline",
        type=JobType.BATCH,
        trigger=TriggerConfig(type=TriggerType.CRON, cron_expr="0 * * * *"),
        run_profile=run_profile,
    )

    await repo.save_job(job)
    loaded = await repo.get_job(job.id)

    assert loaded is not None
    assert loaded.run_profile == run_profile


@pytest.mark.asyncio
async def test_repository_roundtrip_preserves_task_signal(temp_state_dir):
    repo = TaskRepository()
    repo._run_async = AsyncMock(side_effect=lambda func, *args: func(*args))

    job = Job(id="job-inline", name="inline")
    await repo.save_job(job)

    task = Task(
        id="task-inline",
        job_id="job-inline",
        status=TaskStatus.WAITING_CONFIRMATION,
        message="等待人工确认",
        signal=TaskSignal.wait_for_confirmation(
            message="等待人工确认",
            env_action=EnvAction.KEEP_ALIVE,
            payload={
                "confirmation": {
                    "title": "账号复核",
                    "fields": [{"label": "账号", "value": "demo-account"}],
                }
            },
        ).to_dict(),
    )

    await repo.save_task(task)
    loaded = await repo.get_task(task.id)

    assert loaded is not None
    assert loaded.signal == task.signal


@pytest.mark.asyncio
async def test_repository_delete_job_removes_tasks_before_job(monkeypatch):
    statements = []

    class _FakeConn:
        def execute(self, sql, params=()):
            statements.append((sql.strip(), params))
            return self

        def fetchone(self):
            return None

        def fetchall(self):
            return []

        def commit(self):
            return None

        def rollback(self):
            return None

    @contextmanager
    def _fake_get_connection(_db_name):
        yield _FakeConn()

    monkeypatch.setattr("src.core.atm.repository.get_connection", _fake_get_connection)
    repo = TaskRepository()
    repo._run_async = AsyncMock(side_effect=lambda func, *args: func(*args))

    await repo.delete_job("job-1")

    delete_sql = [sql for sql, _ in statements if sql.startswith("DELETE FROM")]
    assert delete_sql[-2:] == [
        "DELETE FROM tasks WHERE job_id = ?",
        "DELETE FROM jobs WHERE id = ?",
    ]


@pytest.mark.asyncio
async def test_controller_reconcile_job_only_reconciles_target():
    controller = JobController()
    service_job = Job(
        id="service-job",
        name="service",
        type=JobType.SERVICE,
        state=JobState.ACTIVE,
        concurrency_target=3,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
    )
    other_job = Job(
        id="other-job",
        name="other",
        type=JobType.SERVICE,
        state=JobState.ACTIVE,
        concurrency_target=2,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
    )

    async def _get_job(job_id: str):
        if job_id == service_job.id:
            return service_job
        if job_id == other_job.id:
            return other_job
        return None

    controller.repo = SimpleNamespace(get_job=AsyncMock(side_effect=_get_job), count_active_tasks=AsyncMock(return_value=1))
    controller.dispatcher = SimpleNamespace(dispatch=AsyncMock())

    await controller.reconcile_job(service_job.id)
    assert controller.dispatcher.dispatch.await_count == 2


@pytest.mark.asyncio
async def test_task_terminal_event_triggers_targeted_reconcile():
    controller = JobController()
    controller._running = True
    controller.reconcile_job = AsyncMock()

    controller._on_task_terminal_event(
        Event(
            type=EventType.TASK_FINISHED,
            data={"job_id": "service-job"},
        )
    )
    await asyncio.sleep(0)

    controller.reconcile_job.assert_awaited_once_with("service-job")


@pytest.mark.asyncio
async def test_recover_zombies_marks_pending_and_running_tasks_failed(monkeypatch):
    controller = JobController()
    pending = Task(id="task-pending", job_id="job-1", status=TaskStatus.PENDING)
    running = Task(id="task-running", job_id="job-1", status=TaskStatus.RUNNING, env_id="42")
    env = SimpleNamespace(id=42)

    controller.repo = SimpleNamespace(
        get_running_tasks=AsyncMock(return_value=[pending, running]),
        mark_tasks_failed=AsyncMock(),
    )

    rem = SimpleNamespace(
        get_env=AsyncMock(return_value=env),
        recycle_env=AsyncMock(return_value=None),
    )
    monkeypatch.setattr("src.core.rem.manager.get_environment_manager", lambda: rem)

    await controller._recover_zombies()

    rem.get_env.assert_awaited_once_with(42)
    rem.recycle_env.assert_awaited_once_with(env)
    controller.repo.mark_tasks_failed.assert_awaited_once()
    failed_ids, reason = controller.repo.mark_tasks_failed.await_args.args
    assert set(failed_ids) == {"task-pending", "task-running"}
    assert "Engine Crashed" in reason

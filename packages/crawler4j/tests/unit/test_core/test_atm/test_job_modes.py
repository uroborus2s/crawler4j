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
    ResourceConfig,
    RunProfile,
)


@pytest.fixture
def temp_state_dir(tmp_path):
    with patch("src.utils.paths.get_app_data_dir", return_value=tmp_path):
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


def _build_select_run_profile(wait_timeout: int = 60, resource_pool: str = "") -> RunProfile:
    return RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.SELECT,
                selector_name="random_ready",
                resource_pool=resource_pool,
                wait_timeout=wait_timeout,
            ),
        ),
        execution=ExecutionContext(module="demo_module", workflow="repair"),
    )


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
        run_profile=_build_select_run_profile(),
        concurrency_target=3,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
    )

    await controller._reconcile_job(job)

    assert controller.dispatcher.dispatch.await_count == 2


@pytest.mark.asyncio
async def test_controller_start_wires_bootstrap_before_service_periodic_loop():
    controller = JobController()
    call_order: list[str] = []

    async def _recover():
        call_order.append("recover")

    async def _bootstrap():
        call_order.append("bootstrap")

    def _start_scheduler():
        call_order.append("start_scheduler")

    def _subscribe():
        call_order.append("subscribe")

    def _start_service_loop():
        call_order.append("start_service_loop")

    controller._recover_zombies = AsyncMock(side_effect=_recover)
    controller._bootstrap_active_jobs = AsyncMock(side_effect=_bootstrap)
    controller._start_scheduler = MagicMock(side_effect=_start_scheduler)
    controller._start_service_reconcile_loop = MagicMock(side_effect=_start_service_loop)
    controller._subscribe_task_events = MagicMock(side_effect=_subscribe)

    await controller.start()

    assert call_order == [
        "recover",
        "start_scheduler",
        "subscribe",
        "bootstrap",
        "start_service_loop",
    ]


def test_start_scheduler_only_starts_apscheduler_without_service_tick_registration():
    controller = JobController()
    controller._scheduler = SimpleNamespace(start=MagicMock(), add_job=MagicMock())

    controller._start_scheduler()

    controller._scheduler.start.assert_called_once_with()
    controller._scheduler.add_job.assert_not_called()


@pytest.mark.asyncio
async def test_service_reconcile_loop_uses_single_interval_cadence_between_tick_starts(monkeypatch):
    controller = JobController()
    controller._running = True
    controller._service_reconcile_interval_seconds = 5.0
    current_time = 100.0
    sleep_calls: list[float] = []
    tick_starts: list[float] = []

    async def _sleep(seconds: float):
        sleep_calls.append(seconds)
        nonlocal current_time
        current_time += seconds

    async def _run_tick():
        nonlocal current_time
        tick_starts.append(current_time)
        current_time += 1.25
        if len(tick_starts) >= 2:
            controller._running = False

    monkeypatch.setattr("src.core.atm.controller.asyncio.sleep", _sleep)
    monkeypatch.setattr("src.core.atm.controller.time.monotonic", lambda: current_time)
    controller._run_service_reconcile_tick = AsyncMock(side_effect=_run_tick)

    await controller._service_reconcile_loop()

    assert tick_starts == [pytest.approx(105.0), pytest.approx(110.0)]
    assert sleep_calls == [pytest.approx(5.0), pytest.approx(3.75)]


@pytest.mark.asyncio
async def test_service_reconcile_tick_times_out_stuck_job_but_continues_following_jobs(monkeypatch):
    controller = JobController()
    controller._service_reconcile_timeout_seconds = 0.01
    cancelled = asyncio.Event()
    reconciled_job_ids: list[str] = []

    stuck_job = Job(
        id="service-job-stuck",
        name="service-stuck",
        type=JobType.SERVICE,
        state=JobState.ACTIVE,
        run_profile=_build_select_run_profile(),
        concurrency_target=1,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
    )
    healthy_job = Job(
        id="service-job-healthy",
        name="service-healthy",
        type=JobType.SERVICE,
        state=JobState.ACTIVE,
        run_profile=_build_select_run_profile(),
        concurrency_target=1,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
    )
    controller.repo = SimpleNamespace(list_active_jobs=AsyncMock(return_value=[stuck_job, healthy_job]))

    async def _reconcile(job: Job):
        reconciled_job_ids.append(job.id)
        if job.id == stuck_job.id:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

    warning_log = MagicMock()
    monkeypatch.setattr("src.core.atm.controller.logger.warning", warning_log)
    controller._reconcile_service_job = AsyncMock(side_effect=_reconcile)

    await controller._run_service_reconcile_tick()

    await asyncio.wait_for(cancelled.wait(), timeout=0.1)
    assert reconciled_job_ids == [stuck_job.id, healthy_job.id]
    warning_log.assert_any_call(
        "[ATM] Service reconcile job %s timed out after %.1fs; cancelling only this job and continuing sweep",
        stuck_job.id,
        controller._service_reconcile_timeout_seconds,
    )


@pytest.mark.asyncio
async def test_stop_service_reconcile_loop_cancels_pending_background_task():
    controller = JobController()

    async def _wait_forever():
        await asyncio.Event().wait()

    task = asyncio.create_task(_wait_forever())
    controller._service_reconcile_task = task

    await controller._stop_service_reconcile_loop()

    assert controller._service_reconcile_task is None
    assert task.cancelled()


@pytest.mark.asyncio
async def test_service_job_scale_up_skips_when_runtime_check_fails_before_dispatch():
    controller = JobController()
    controller.repo = SimpleNamespace(count_active_tasks=AsyncMock(return_value=1))
    controller.dispatcher = SimpleNamespace(dispatch=AsyncMock())
    controller._ensure_runtime_for_job = AsyncMock(side_effect=RuntimeError("module upgrading"))

    job = Job(
        id="service-job",
        name="service",
        type=JobType.SERVICE,
        state=JobState.ACTIVE,
        run_profile=_build_select_run_profile(),
        concurrency_target=3,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
    )

    await controller._reconcile_job(job)

    controller.dispatcher.dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_service_job_fixed_pool_resumes_waiting_tasks_up_to_current_capacity():
    controller = JobController()
    waiting_tasks = [
        Task(id="task-p1", job_id="service-job", status=TaskStatus.PENDING),
        Task(id="task-p2", job_id="service-job", status=TaskStatus.PENDING),
        Task(id="task-p3", job_id="service-job", status=TaskStatus.PENDING),
        Task(id="task-p4", job_id="service-job", status=TaskStatus.PENDING),
        Task(id="task-p5", job_id="service-job", status=TaskStatus.PENDING),
        Task(id="task-p6", job_id="service-job", status=TaskStatus.PENDING),
    ]
    controller.repo = SimpleNamespace(
        count_active_tasks=AsyncMock(return_value=10),
        count_tasks_by_statuses=AsyncMock(return_value=2),
        get_oldest_waiting_tasks=AsyncMock(return_value=waiting_tasks),
    )
    controller.dispatcher = SimpleNamespace(
        dispatch=AsyncMock(),
        resume_task=AsyncMock(return_value=True),
        has_live_task_loop=MagicMock(return_value=False),
    )
    controller._count_fixed_pool_capacity = AsyncMock(return_value=5)

    job = Job(
        id="service-job",
        name="service",
        type=JobType.SERVICE,
        state=JobState.ACTIVE,
        run_profile=_build_select_run_profile(resource_pool="bound_account_ready"),
        concurrency_target=10,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
    )

    await controller._reconcile_job(job)

    controller.dispatcher.dispatch.assert_not_awaited()
    assert controller.dispatcher.resume_task.await_count == 5
    resumed_ids = [call.args[0].id for call in controller.dispatcher.resume_task.await_args_list]
    assert resumed_ids == ["task-p1", "task-p2", "task-p3", "task-p4", "task-p5"]


@pytest.mark.asyncio
async def test_fixed_pool_resource_pool_reconcile_is_serialized_to_avoid_over_dispatch():
    controller = JobController()
    active_count = 0
    count_calls = 0
    first_count_entered = asyncio.Event()
    second_count_entered = asyncio.Event()
    allow_dispatch = asyncio.Event()

    async def _count_active_tasks(_job_id: str) -> int:
        nonlocal active_count, count_calls
        count_calls += 1
        if count_calls == 1:
            first_count_entered.set()
            try:
                await asyncio.wait_for(second_count_entered.wait(), timeout=0.05)
            except asyncio.TimeoutError:
                pass
        elif count_calls == 2:
            second_count_entered.set()
        return active_count

    async def _dispatch(_job: Job) -> None:
        nonlocal active_count
        await allow_dispatch.wait()
        active_count += 1

    job = Job(
        id="service-job",
        name="service",
        type=JobType.SERVICE,
        state=JobState.ACTIVE,
        run_profile=_build_select_run_profile(resource_pool="bound_account_ready"),
        concurrency_target=2,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
    )

    controller.repo = SimpleNamespace(
        list_active_jobs=AsyncMock(return_value=[job]),
        count_active_tasks=AsyncMock(side_effect=_count_active_tasks),
        count_tasks_by_statuses=AsyncMock(return_value=0),
        get_oldest_tasks_by_status=AsyncMock(return_value=[]),
    )
    controller.dispatcher = SimpleNamespace(dispatch=AsyncMock(side_effect=_dispatch))
    controller._count_fixed_pool_capacity = AsyncMock(return_value=0)

    first_task = asyncio.create_task(controller._reconcile_resource_pool_jobs("demo_module", "bound_account_ready"))
    second_task = asyncio.create_task(controller._reconcile_resource_pool_jobs("demo_module", "bound_account_ready"))

    await first_count_entered.wait()
    try:
        await asyncio.wait_for(second_count_entered.wait(), timeout=0.05)
    except asyncio.TimeoutError:
        pass
    allow_dispatch.set()

    await asyncio.gather(first_task, second_task)

    assert controller.dispatcher.dispatch.await_count == 2
    assert active_count == 2


@pytest.mark.asyncio
async def test_service_job_fixed_pool_wait_timeout_uses_waiting_since_and_publishes_failed_event(
    temp_state_dir,
    monkeypatch,
):
    import src.core.atm.controller as controller_module

    class _FakeEventBus:
        def __init__(self):
            self.events: list[Event] = []

        def subscribe(self, *_args, **_kwargs):
            return None

        def unsubscribe(self, *_args, **_kwargs):
            return None

        def publish(self, event: Event):
            self.events.append(event)

    now = 1_710_000_100
    event_bus = _FakeEventBus()
    monkeypatch.setattr(controller_module, "get_event_bus", lambda: event_bus)
    monkeypatch.setattr(controller_module.time, "time", lambda: now)

    repo = TaskRepository()
    repo._run_async = AsyncMock(side_effect=lambda func, *args: func(*args))

    controller = controller_module.JobController()
    controller.repo = repo
    controller._event_bus = event_bus
    controller.dispatcher = SimpleNamespace(
        dispatch=AsyncMock(),
        resume_task=AsyncMock(return_value=True),
        has_live_task_loop=MagicMock(return_value=False),
    )
    controller._count_fixed_pool_capacity = AsyncMock(return_value=1)

    job = Job(
        id="service-job",
        name="service",
        type=JobType.SERVICE,
        state=JobState.ACTIVE,
        run_profile=_build_select_run_profile(wait_timeout=30, resource_pool="bound_account_ready"),
        concurrency_target=1,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
    )
    await repo.save_job(job)

    expired_task = Task(
        id="task-expired",
        job_id=job.id,
        status=TaskStatus.PENDING,
        message="等待环境池工位: bound_account_ready",
        created_at=now - 300,
    )
    fresh_task = Task(
        id="task-fresh",
        job_id=job.id,
        status=TaskStatus.PENDING,
        message="等待环境池工位: bound_account_ready",
        created_at=now - 240,
    )
    setattr(expired_task, "waiting_since", now - 31)
    setattr(fresh_task, "waiting_since", now - 5)
    await repo.save_task(expired_task)
    await repo.save_task(fresh_task)

    await controller._reconcile_job(job)

    expired_loaded = await repo.get_task(expired_task.id)
    fresh_loaded = await repo.get_task(fresh_task.id)

    assert expired_loaded is not None
    assert expired_loaded.status == TaskStatus.FAILED
    assert expired_loaded.message == ""
    assert expired_loaded.error == "等待环境池工位超时: bound_account_ready (30s)"
    assert expired_loaded.waiting_since is None
    assert fresh_loaded is not None
    assert fresh_loaded.status == TaskStatus.PENDING
    controller.dispatcher.resume_task.assert_awaited_once()
    resumed_task, resumed_job = controller.dispatcher.resume_task.await_args.args
    assert resumed_task.id == fresh_task.id
    assert resumed_job.id == job.id
    assert len(event_bus.events) == 1
    event = event_bus.events[0]
    assert event.type == EventType.TASK_FAILED
    assert event.task_run_id == expired_task.id
    assert event.data["task_id"] == expired_task.id
    assert event.data["job_id"] == job.id
    assert event.data["error"] == "等待环境池工位超时: bound_account_ready (30s)"


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
        run_profile=_build_select_run_profile(),
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
        run_profile=_build_select_run_profile(),
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
async def test_batch_job_skips_trigger_when_runtime_check_fails_before_dispatch():
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
    controller._ensure_runtime_for_job = AsyncMock(side_effect=RuntimeError("module upgrading"))

    await controller._on_batch_cron_fire(job.id)

    controller.dispatcher.dispatch.assert_not_awaited()


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
        run_profile=_build_select_run_profile(),
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
        run_profile=_build_select_run_profile(),
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
async def test_ensure_job_runtime_ready_blocks_when_module_upgrade_lock_active(temp_state_dir):
    from src.core.mms.release_service import ModuleReleaseService

    controller = JobController()
    job = Job(
        id="service-job",
        name="service",
        type=JobType.SERVICE,
        state=JobState.PAUSED,
        run_profile=_build_select_run_profile(),
        concurrency_target=1,
    )
    controller.repo = SimpleNamespace(get_job=AsyncMock(return_value=job))

    service = ModuleReleaseService()
    async with service.hold_module_upgrade_lock("demo_module"):
        with pytest.raises(ValueError) as exc_info:
            await controller.ensure_job_runtime_ready(job.id)

    assert "升级维护" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_service_job_forces_manual_trigger():
    service = TaskService()
    saved_jobs = []
    service._repo = SimpleNamespace(save_job=AsyncMock(side_effect=lambda job: saved_jobs.append(job)))
    run_profile = _build_select_run_profile()

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
    run_profile = _build_select_run_profile()

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

    run_profile = _build_select_run_profile(wait_timeout=90)

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
        run_profile=_build_select_run_profile(),
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
    assert service._controller.ensure_job_runtime_ready.await_count == 2
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
        run_profile=_build_select_run_profile(),
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
        run_profile=_build_select_run_profile(),
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
async def test_run_job_once_rechecks_runtime_before_dispatch():
    service = TaskService()
    job = Job(
        id="batch-manual-job",
        name="manual-batch",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        run_profile=_build_select_run_profile(),
        concurrency_target=2,
    )
    service._repo = SimpleNamespace(
        get_job=AsyncMock(return_value=job),
        save_job=AsyncMock(),
        count_active_tasks=AsyncMock(return_value=0),
    )
    service._controller = SimpleNamespace(
        ensure_job_runtime_ready=AsyncMock(side_effect=[None, RuntimeError("module upgrading")]),
        dispatcher=SimpleNamespace(dispatch=AsyncMock()),
    )

    result = await service.run_job_once(job.id)

    assert result is False
    assert service._controller.ensure_job_runtime_ready.await_count == 2
    service._controller.dispatcher.dispatch.assert_not_awaited()


@pytest.mark.asyncio
async def test_stop_run_once_requests_job_stop_with_selected_env_action():
    service = TaskService()
    job = Job(
        id="batch-manual-job",
        name="manual-batch",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        run_profile=_build_select_run_profile(),
        concurrency_target=2,
    )
    service._repo = SimpleNamespace(
        get_job=AsyncMock(return_value=job),
        count_active_tasks=AsyncMock(return_value=1),
    )
    service._controller = SimpleNamespace(request_job_stop=AsyncMock())

    result = await service.stop_run_once(job.id, EnvAction.RECYCLE)

    assert result is True
    service._controller.request_job_stop.assert_awaited_once_with(job.id, env_action=EnvAction.RECYCLE)


@pytest.mark.asyncio
async def test_stop_run_once_rejects_destroy_for_selected_env_mode():
    service = TaskService()
    job = Job(
        id="batch-manual-job",
        name="manual-batch",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        run_profile=_build_select_run_profile(),
        concurrency_target=2,
    )
    service._repo = SimpleNamespace(
        get_job=AsyncMock(return_value=job),
        count_active_tasks=AsyncMock(return_value=1),
    )
    service._controller = SimpleNamespace(request_job_stop=AsyncMock())

    with pytest.raises(ValueError, match="不能删除环境"):
        await service.stop_run_once(job.id, EnvAction.DESTROY)

    service._controller.request_job_stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_stop_run_once_returns_false_when_no_active_tasks():
    service = TaskService()
    job = Job(
        id="batch-manual-job",
        name="manual-batch",
        type=JobType.BATCH,
        state=JobState.PAUSED,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        run_profile=_build_select_run_profile(),
        concurrency_target=2,
    )
    service._repo = SimpleNamespace(
        get_job=AsyncMock(return_value=job),
        count_active_tasks=AsyncMock(return_value=0),
    )
    service._controller = SimpleNamespace(request_job_stop=AsyncMock())

    result = await service.stop_run_once(job.id, EnvAction.RECYCLE)

    assert result is False
    service._controller.request_job_stop.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_job_switches_manual_batch_to_paused_and_requests_stop():
    service = TaskService()
    job = Job(
        id="service-job",
        name="service",
        type=JobType.SERVICE,
        state=JobState.ACTIVE,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        run_profile=_build_select_run_profile(),
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

    run_profile = _build_select_run_profile(wait_timeout=75)
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
        run_profile=_build_select_run_profile(),
        concurrency_target=3,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
    )
    other_job = Job(
        id="other-job",
        name="other",
        type=JobType.SERVICE,
        state=JobState.ACTIVE,
        run_profile=_build_select_run_profile(),
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
    waiting = Task(
        id="task-waiting",
        job_id="job-1",
        status=TaskStatus.PENDING,
        message="等待环境池工位: bound_account_ready",
        waiting_since=123,
    )
    running = Task(id="task-running", job_id="job-1", status=TaskStatus.RUNNING, env_id="42")
    env = SimpleNamespace(id=42)

    controller.repo = SimpleNamespace(
        get_running_tasks=AsyncMock(return_value=[pending, waiting, running]),
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

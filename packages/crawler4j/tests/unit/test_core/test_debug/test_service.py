import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.core.atm.models import Job, JobState
from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    CreationConfig,
    CreationLifecycle,
    EnvType,
    ExecutionContext,
    ResourceConfig,
    RunProfile,
)


class _FakeStream:
    def __init__(self):
        self._queue: asyncio.Queue[bytes] = asyncio.Queue()

    async def readline(self) -> bytes:
        return await self._queue.get()

    def feed_line(self, line: str) -> None:
        self._queue.put_nowait(line.encode("utf-8"))

    def close(self) -> None:
        self._queue.put_nowait(b"")


class _FakeProcess:
    def __init__(self, pid: int):
        self.pid = pid
        self.returncode: int | None = None
        self.stdout = _FakeStream()
        self.stderr = _FakeStream()
        self._wait_event = asyncio.Event()
        self.terminated = False
        self.killed = False

    async def wait(self) -> int:
        await self._wait_event.wait()
        return int(self.returncode or 0)

    def terminate(self) -> None:
        self.terminated = True
        self.finish(0)

    def kill(self) -> None:
        self.killed = True
        self.finish(-9)

    def finish(self, code: int) -> None:
        self.returncode = code
        self.stdout.close()
        self.stderr.close()
        self._wait_event.set()


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with patch("src.utils.paths.get_app_data_dir", return_value=tmp_path):
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


def _make_registry(module_path: Path, *, source=None):
    from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource

    module_source = source or ModuleSource.DEV_LINK

    module_info = ModuleInfo(
        name="demo_module",
        manifest=ModuleManifest(name="demo_module"),
        source=module_source,
        path=module_path,
    )
    return SimpleNamespace(get_module=lambda name: module_info if name == "demo_module" else None)


def _make_run_profile(*, wait_timeout: int = 90, lifecycle: CreationLifecycle = CreationLifecycle.EPHEMERAL, params: dict | None = None, timeout: int = 180) -> RunProfile:
    return RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                provider="virtualbrowser",
                env_type=EnvType.VIRTUAL_BROWSER,
                wait_timeout=wait_timeout,
                creation=CreationConfig(
                    lifecycle=lifecycle,
                    params=params or {"region": "cn"},
                ),
            ),
        ),
        execution=ExecutionContext(
            module="demo_module",
            workflow="repair",
            timeout=timeout,
        ),
    )


def _make_job() -> Job:
    return Job(
        id="job-1",
        name="Demo Job",
        run_profile=_make_run_profile(),
        params={"city": "Shanghai"},
    )


@pytest.mark.asyncio
async def test_debug_service_rejects_disabled_job(temp_data_dir):
    from src.core.debug.models import DebugSessionRequest
    from src.core.debug.service import DebugService

    job = _make_job()
    job.state = JobState.DISABLED
    service = DebugService(
        registry=_make_registry(temp_data_dir / "demo_module"),
        task_service=SimpleNamespace(get_job=lambda job_id: job if job_id == job.id else None),
        stop_timeout=0.01,
    )

    with pytest.raises(ValueError, match="已禁用"):
        await service.create_session(DebugSessionRequest(job_id=job.id))


def _make_inline_job() -> Job:
    return Job(
        id="job-inline",
        name="Inline Job",
        run_profile=_make_run_profile(
            wait_timeout=45,
            lifecycle=CreationLifecycle.PERSISTENT,
            params={"region": "sg"},
            timeout=300,
        ).model_copy(
            update={
                "execution": ExecutionContext(
                    module="demo_module",
                    workflow="repair",
                    timeout=300,
                )
            }
        ),
        params={"city": "Singapore"},
    )


def _make_auto_workflow_job() -> Job:
    return Job(
        id="job-auto",
        name="Auto Workflow Job",
        run_profile=_make_run_profile().model_copy(
            update={
                "execution": ExecutionContext(
                    module="demo_module",
                    workflow="",
                    timeout=300,
                )
            }
        ),
    )


def _make_candidate_job() -> Job:
    return Job(
        id="job-candidate",
        name="Candidate Job",
        run_profile=RunProfile(
            resource=ResourceConfig(
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.SELECT,
                    candidates="ready_accounts",
                    candidate_params={"tier": "gold", "limit": 5},
                    wait_timeout=30,
                ),
            ),
            execution=ExecutionContext(
                module="demo_module",
                workflow="repair",
                timeout=120,
            ),
        ),
        params={"city": "Shanghai"},
    )


@pytest.mark.asyncio
async def test_debug_service_tracks_worker_events_and_logs(monkeypatch, temp_data_dir):
    from src.core.debug.models import DebugSessionRequest, DebugSessionState
    from src.core.debug.protocol import encode_debug_event
    from src.core.debug.service import DebugService

    worker = _FakeProcess(pid=4321)

    async def fake_exec(*args, **kwargs):
        return worker

    job = _make_job()
    service = DebugService(
        registry=_make_registry(temp_data_dir / "demo_module"),
        task_service=SimpleNamespace(get_job=lambda job_id: job if job_id == job.id else None),
        stop_timeout=0.01,
    )

    monkeypatch.setattr("src.core.debug.service.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(service, "_allocate_attach_port", lambda host, port: port)

    session = await service.create_session(DebugSessionRequest(job_id=job.id))
    await service.start_session(session.id)

    worker.stdout.feed_line(
        encode_debug_event(
            {
                "type": "state",
                "state": DebugSessionState.WAITING_FOR_ATTACH.value,
                "attach_host": "127.0.0.1",
                "attach_port": 5678,
            }
        )
        + "\n"
    )
    worker.stderr.feed_line("worker stderr log\n")
    worker.stdout.feed_line(
        encode_debug_event(
            {
                "type": "state",
                "state": DebugSessionState.RUNNING.value,
                "env_id": "21",
            }
        )
        + "\n"
    )
    worker.stdout.feed_line(
        encode_debug_event(
            {
                "type": "state",
                "state": DebugSessionState.SUCCEEDED.value,
                "env_id": "21",
            }
        )
        + "\n"
    )
    worker.finish(0)

    await asyncio.sleep(0.05)

    current = await service.get_session(session.id)
    assert current is not None
    assert current.worker_pid == 4321
    assert current.state == DebugSessionState.SUCCEEDED
    assert current.env_id == "21"
    assert any("worker stderr log" in line for line in current.logs)

    payload = json.loads(service.get_session_file(session.id).read_text(encoding="utf-8"))
    assert payload["job_id"] == job.id
    assert "strategy_id" not in payload
    assert payload["module_name"] == "demo_module"
    assert payload["workflow"] == "repair"
    assert payload["provider"] == "virtualbrowser"
    assert payload["fixed_env_id"] is None
    assert payload["candidates"] == ""
    assert payload["candidate_params"] == {}
    assert payload["wait_timeout"] == 90
    assert payload["timeout"] == 180
    assert "execution_params" not in payload
    assert "job_params" not in payload
    assert "params" not in payload
    assert payload["creation_params"] == {"region": "cn"}


@pytest.mark.asyncio
async def test_debug_service_preserves_blank_workflow_for_v2_descriptor_resolution(temp_data_dir):
    from src.core.debug.models import DebugSessionRequest
    from src.core.debug.service import DebugService

    job = _make_auto_workflow_job()
    service = DebugService(
        registry=_make_registry(temp_data_dir / "demo_module"),
        task_service=SimpleNamespace(get_job=lambda job_id: job if job_id == job.id else None),
    )

    session = await service.create_session(DebugSessionRequest(job_id=job.id))

    assert session.workflow == ""


@pytest.mark.asyncio
async def test_debug_service_can_stop_and_restart_session(monkeypatch, temp_data_dir):
    from src.core.debug.models import DebugSessionRequest, DebugSessionState
    from src.core.debug.protocol import encode_debug_event
    from src.core.debug.service import DebugService

    workers = [_FakeProcess(pid=1001), _FakeProcess(pid=1002)]

    async def fake_exec(*args, **kwargs):
        return workers.pop(0)

    job = _make_job()
    service = DebugService(
        registry=_make_registry(temp_data_dir / "demo_module"),
        task_service=SimpleNamespace(get_job=lambda job_id: job if job_id == job.id else None),
        stop_timeout=0.01,
    )

    monkeypatch.setattr("src.core.debug.service.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(service, "_allocate_attach_port", lambda host, port: port)

    session = await service.create_session(DebugSessionRequest(job_id=job.id))
    await service.start_session(session.id)

    first_worker = service._processes[session.id]
    first_worker.stdout.feed_line(
        encode_debug_event({"type": "state", "state": DebugSessionState.WAITING_FOR_ATTACH.value}) + "\n"
    )
    await asyncio.sleep(0.05)

    assert await service.stop_session(session.id) is True
    await asyncio.sleep(0.05)

    stopped = await service.get_session(session.id)
    assert stopped is not None
    assert stopped.state == DebugSessionState.STOPPED
    assert first_worker.terminated is True

    restarted = await service.restart_session(session.id)
    assert restarted.worker_pid == 1002

    second_worker = service._processes[session.id]
    second_worker.stdout.feed_line(
        encode_debug_event({"type": "state", "state": DebugSessionState.RUNNING.value}) + "\n"
    )
    second_worker.stdout.feed_line(
        encode_debug_event({"type": "state", "state": DebugSessionState.SUCCEEDED.value}) + "\n"
    )
    second_worker.finish(0)

    await asyncio.sleep(0.05)

    current = await service.get_session(session.id)
    assert current is not None
    assert current.state == DebugSessionState.SUCCEEDED
    assert current.worker_pid == 1002


@pytest.mark.asyncio
async def test_debug_service_supports_inline_run_profile(monkeypatch, temp_data_dir):
    from src.core.debug.models import DebugSessionRequest, DebugSessionState
    from src.core.debug.protocol import encode_debug_event
    from src.core.debug.service import DebugService

    worker = _FakeProcess(pid=5555)

    async def fake_exec(*args, **kwargs):
        return worker

    job = _make_inline_job()
    service = DebugService(
        registry=_make_registry(temp_data_dir / "demo_module"),
        task_service=SimpleNamespace(get_job=lambda job_id: job if job_id == job.id else None),
        stop_timeout=0.01,
    )

    monkeypatch.setattr("src.core.debug.service.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(service, "_allocate_attach_port", lambda host, port: port)

    session = await service.create_session(DebugSessionRequest(job_id=job.id))
    await service.start_session(session.id)

    worker.stdout.feed_line(
        encode_debug_event({"type": "state", "state": DebugSessionState.SUCCEEDED.value, "env_id": "31"}) + "\n"
    )
    worker.finish(0)

    await asyncio.sleep(0.05)

    payload = json.loads(service.get_session_file(session.id).read_text(encoding="utf-8"))
    assert payload["job_id"] == job.id
    assert "strategy_id" not in payload
    assert payload["module_name"] == "demo_module"
    assert payload["workflow"] == "repair"
    assert payload["provider"] == "virtualbrowser"
    assert payload["wait_timeout"] == 45
    assert payload["timeout"] == 300
    assert "execution_params" not in payload
    assert "job_params" not in payload
    assert "params" not in payload
    assert payload["creation_params"] == {"region": "sg"}


@pytest.mark.asyncio
async def test_debug_service_payload_preserves_candidate_selection(monkeypatch, temp_data_dir):
    from src.core.debug.models import DebugSessionRequest, DebugSessionState
    from src.core.debug.protocol import encode_debug_event
    from src.core.debug.service import DebugService

    worker = _FakeProcess(pid=5678)

    async def fake_exec(*args, **kwargs):
        return worker

    job = _make_candidate_job()
    service = DebugService(
        registry=_make_registry(temp_data_dir / "demo_module"),
        task_service=SimpleNamespace(get_job=lambda job_id: job if job_id == job.id else None),
        stop_timeout=0.01,
    )

    monkeypatch.setattr("src.core.debug.service.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(service, "_allocate_attach_port", lambda host, port: port)

    session = await service.create_session(DebugSessionRequest(job_id=job.id))
    await service.start_session(session.id)

    worker.stdout.feed_line(
        encode_debug_event({"type": "state", "state": DebugSessionState.SUCCEEDED.value, "env_id": "31"}) + "\n"
    )
    worker.finish(0)

    await asyncio.sleep(0.05)

    payload = json.loads(service.get_session_file(session.id).read_text(encoding="utf-8"))
    assert payload["acquisition_mode"] == "select"
    assert payload["fixed_env_id"] is None
    assert payload["candidates"] == "ready_accounts"
    assert payload["candidate_params"] == {"tier": "gold", "limit": 5}
    assert payload["wait_timeout"] == 30


@pytest.mark.asyncio
async def test_debug_service_rejects_non_dev_link_modules(temp_data_dir):
    from src.core.debug.models import DebugSessionRequest
    from src.core.debug.service import DebugService
    from src.core.mms.models import ModuleSource

    job = _make_job()
    service = DebugService(
        registry=_make_registry(temp_data_dir / "modules" / "demo_module", source=ModuleSource.EXTERNAL),
        task_service=SimpleNamespace(get_job=lambda job_id: job if job_id == job.id else None),
    )

    with pytest.raises(ValueError, match="开发链接"):
        await service.create_session(
            DebugSessionRequest(
                job_id=job.id,
            )
        )


@pytest.mark.asyncio
async def test_debug_service_uses_embedded_worker_flag_when_frozen(monkeypatch, temp_data_dir):
    from src.core.debug.models import DebugSessionRequest
    from src.core.debug.service import DebugService

    captured: dict[str, tuple] = {}
    worker = _FakeProcess(pid=7777)

    async def fake_exec(*args, **kwargs):
        captured["args"] = args
        return worker

    job = _make_job()
    service = DebugService(
        registry=_make_registry(temp_data_dir / "demo_module"),
        task_service=SimpleNamespace(get_job=lambda job_id: job if job_id == job.id else None),
        python_executable="/Applications/Crawler4j.app/Contents/MacOS/Crawler4j",
        frozen=True,
        stop_timeout=0.01,
    )

    monkeypatch.setattr("src.core.debug.service.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(service, "_allocate_attach_port", lambda host, port: port)

    session = await service.create_session(DebugSessionRequest(job_id=job.id))
    await service.start_session(session.id)

    assert captured["args"] == (
        "/Applications/Crawler4j.app/Contents/MacOS/Crawler4j",
        "--crawler4j-debug-worker",
        str(service.get_session_file(session.id)),
    )

    worker.finish(0)
    await asyncio.sleep(0.05)

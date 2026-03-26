import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.core.atm.models import Job
from src.core.tsm.models import (
    AcquisitionConfig,
    AcquisitionMode,
    CreationConfig,
    CreationLifecycle,
    ExecutionContext,
    MatchConfig,
    ResourceConfig,
    TaskStrategy,
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


def _make_job() -> Job:
    return Job(
        id="job-1",
        name="Demo Job",
        strategy_id="strategy.demo",
        params={"city": "Shanghai"},
    )


def _make_strategy() -> TaskStrategy:
    return TaskStrategy(
        id="strategy.demo",
        name="Demo Strategy",
        resource=ResourceConfig(
            provider="virtualbrowser",
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                selector=MatchConfig(wait_timeout=90),
                creation=CreationConfig(
                    lifecycle=CreationLifecycle.EPHEMERAL,
                    params={"region": "cn"},
                ),
            ),
        ),
        execution=ExecutionContext(
            module="demo_module",
            workflow="repair",
            hooks_module="demo_module.hooks",
            params={"lang": "zh-CN"},
            timeout=180,
        ),
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
    strategy = _make_strategy()
    service = DebugService(
        registry=_make_registry(temp_data_dir / "demo_module"),
        task_service=SimpleNamespace(get_job=lambda job_id: job if job_id == job.id else None),
        strategy_loader=SimpleNamespace(get=lambda strategy_id: strategy if strategy_id == job.strategy_id else None),
        stop_timeout=0.01,
    )

    monkeypatch.setattr("src.core.debug.service.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(service, "_allocate_attach_port", lambda host, port: port)

    session = await service.create_session(
        DebugSessionRequest(job_id=job.id)
    )
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
    assert payload["strategy_id"] == job.strategy_id
    assert payload["module_name"] == "demo_module"
    assert payload["workflow"] == "repair"
    assert payload["hooks_module"] == "demo_module.hooks"
    assert payload["provider"] == "virtualbrowser"
    assert payload["wait_timeout"] == 90
    assert payload["timeout"] == 180
    assert payload["params"] == {"lang": "zh-CN", "city": "Shanghai"}
    assert payload["creation_params"] == {"region": "cn"}


@pytest.mark.asyncio
async def test_debug_service_can_stop_and_restart_session(monkeypatch, temp_data_dir):
    from src.core.debug.models import DebugSessionRequest, DebugSessionState
    from src.core.debug.protocol import encode_debug_event
    from src.core.debug.service import DebugService

    workers = [_FakeProcess(pid=1001), _FakeProcess(pid=1002)]

    async def fake_exec(*args, **kwargs):
        return workers.pop(0)

    job = _make_job()
    strategy = _make_strategy()
    service = DebugService(
        registry=_make_registry(temp_data_dir / "demo_module"),
        task_service=SimpleNamespace(get_job=lambda job_id: job if job_id == job.id else None),
        strategy_loader=SimpleNamespace(get=lambda strategy_id: strategy if strategy_id == job.strategy_id else None),
        stop_timeout=0.01,
    )

    monkeypatch.setattr("src.core.debug.service.create_subprocess_exec", fake_exec)
    monkeypatch.setattr(service, "_allocate_attach_port", lambda host, port: port)

    session = await service.create_session(
        DebugSessionRequest(job_id=job.id)
    )
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
async def test_debug_service_rejects_non_dev_link_modules(temp_data_dir):
    from src.core.debug.models import DebugSessionRequest
    from src.core.debug.service import DebugService
    from src.core.mms.models import ModuleSource

    job = _make_job()
    strategy = _make_strategy()
    service = DebugService(
        registry=_make_registry(temp_data_dir / "modules" / "demo_module", source=ModuleSource.EXTERNAL),
        task_service=SimpleNamespace(get_job=lambda job_id: job if job_id == job.id else None),
        strategy_loader=SimpleNamespace(get=lambda strategy_id: strategy if strategy_id == job.strategy_id else None),
    )

    with pytest.raises(ValueError, match="开发链接"):
        await service.create_session(
            DebugSessionRequest(
                job_id=job.id,
            )
        )

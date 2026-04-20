"""Debug session service."""

from __future__ import annotations

import asyncio
import inspect
import json
import socket
import sys
import time
from asyncio.subprocess import PIPE, create_subprocess_exec
from pathlib import Path

from src.core.atm.run_profile import CreationLifecycle
from src.core.debug.launcher import build_debug_worker_command
from src.core.debug.models import (
    FINAL_DEBUG_STATES,
    DebugSession,
    DebugSessionRequest,
    DebugSessionState,
)
from src.core.debug.protocol import decode_debug_event
from src.core.debug.repository import (
    DebugSessionRepository,
    get_debug_session_repository,
)
from src.core.debug.resolver import resolve_job_debug_target
from src.core.mms.models import ModuleSource
from src.core.mms.registry import ModuleRegistry, get_module_registry
from src.core.atm.service import TaskService, get_task_service
from src.utils.paths import get_app_data_dir


class DebugService:
    """调试会话生命周期服务。"""

    def __init__(
        self,
        *,
        repo: DebugSessionRepository | None = None,
        registry: ModuleRegistry | None = None,
        task_service: TaskService | None = None,
        worker_module: str = "src.core.debug.worker_entry",
        python_executable: str | None = None,
        frozen: bool | None = None,
        stop_timeout: float = 5.0,
    ):
        self.repo = repo or get_debug_session_repository()
        self.registry = registry or get_module_registry()
        self.task_service = task_service or get_task_service()
        self._worker_module = worker_module
        self._python_executable = python_executable or sys.executable
        self._frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
        self._stop_timeout = stop_timeout
        self._session_root = get_app_data_dir() / "debug_sessions"
        self._session_root.mkdir(parents=True, exist_ok=True)

        self._sessions: dict[str, DebugSession] = {}
        self._processes: dict[str, object] = {}
        self._stream_tasks: dict[str, list[asyncio.Task]] = {}
        self._watch_tasks: dict[str, asyncio.Task] = {}

    async def create_session(self, request: DebugSessionRequest) -> DebugSession:
        job_result = self.task_service.get_job(request.job_id)
        job = await job_result if inspect.isawaitable(job_result) else job_result
        if not job:
            raise ValueError(f"Job not found: {request.job_id}")

        target = resolve_job_debug_target(
            job,
            registry=self.registry,
        )
        if target.module.source != ModuleSource.DEV_LINK:
            raise ValueError(f"仅开发链接模块支持任务调试: {target.module.name}")

        session = DebugSession(
            job_id=job.id,
            job_name=job.name,
            module_name=target.module.name,
            source_path=str(target.module.path),
            workflow=target.workflow,
            execution_params=dict(target.execution_params),
            job_params=dict(target.job_params),
            params=dict(request.params) if request.params else dict(target.runtime_params),
            hooks_module=target.hooks_module,
            provider=target.run_profile.resource.acquisition.provider,
            selector_name=target.run_profile.resource.acquisition.selector_name,
            acquisition_mode=target.run_profile.resource.acquisition.mode,
            creation_params=dict(target.run_profile.resource.acquisition.creation.params),
            creation_lifecycle=(
                target.run_profile.resource.acquisition.creation.lifecycle
                if not request.keep_environment
                else CreationLifecycle.PERSISTENT
            ),
            wait_timeout=target.wait_timeout,
            timeout=request.timeout or target.timeout,
            attach_host=request.attach_host,
            attach_port=request.attach_port,
            wait_for_attach=request.wait_for_attach,
            stop_on_entry=request.stop_on_entry,
            keep_environment=request.keep_environment,
        )
        self._sessions[session.id] = session
        await self.repo.save_session(session)
        return session

    async def start_session(self, session_id: str) -> DebugSession:
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Debug session not found: {session_id}")
        if session.state in {
            DebugSessionState.STARTING,
            DebugSessionState.WAITING_FOR_ATTACH,
            DebugSessionState.RUNNING,
        }:
            return session

        session.attach_port = self._allocate_attach_port(session.attach_host, session.attach_port)
        session.state = DebugSessionState.STARTING
        session.started_at = int(time.time())
        session.finished_at = None
        session.last_error = ""
        session.worker_pid = None
        session.env_id = None
        session.logs.clear()
        await self.repo.save_session(session)

        session_file = self.get_session_file(session.id)
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(
            json.dumps(session.to_worker_payload(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        stop_flag = self._stop_flag_file(session.id)
        if stop_flag.exists():
            stop_flag.unlink()

        process = await create_subprocess_exec(
            *build_debug_worker_command(
                self._python_executable,
                session_file,
                worker_module=self._worker_module,
                frozen=self._frozen,
            ),
            stdout=PIPE,
            stderr=PIPE,
        )

        session.worker_pid = process.pid
        self._processes[session.id] = process
        await self.repo.save_session(session)

        stream_tasks = [
            asyncio.create_task(self._consume_stream(session.id, process.stdout, is_stderr=False)),
            asyncio.create_task(self._consume_stream(session.id, process.stderr, is_stderr=True)),
        ]
        self._stream_tasks[session.id] = stream_tasks
        self._watch_tasks[session.id] = asyncio.create_task(self._watch_process(session.id, process))

        return session

    async def stop_session(self, session_id: str) -> bool:
        session = await self.get_session(session_id)
        if not session:
            return False
        watch_task = self._watch_tasks.get(session_id)
        if session.state in FINAL_DEBUG_STATES:
            if watch_task:
                await watch_task
            return True

        session.state = DebugSessionState.STOPPING
        await self.repo.save_session(session)
        self._stop_flag_file(session_id).write_text("stop\n", encoding="utf-8")

        process = self._processes.get(session_id)
        if process:
            try:
                await asyncio.wait_for(process.wait(), timeout=self._stop_timeout)
            except asyncio.TimeoutError:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=self._stop_timeout)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()

        if watch_task:
            await watch_task

        return True

    async def restart_session(self, session_id: str) -> DebugSession:
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Debug session not found: {session_id}")

        await self.stop_session(session_id)
        session.state = DebugSessionState.CREATED
        session.worker_pid = None
        session.started_at = None
        session.finished_at = None
        session.env_id = None
        session.last_error = ""
        session.logs.clear()
        await self.repo.save_session(session)

        return await self.start_session(session_id)

    async def get_session(self, session_id: str) -> DebugSession | None:
        session = self._sessions.get(session_id)
        if session:
            return session

        session = await self.repo.get_session(session_id)
        if session:
            self._sessions[session.id] = session
        return session

    async def list_sessions(self) -> list[DebugSession]:
        if self._sessions:
            return list(self._sessions.values())

        sessions = await self.repo.list_sessions()
        for session in sessions:
            self._sessions[session.id] = session
        return sessions

    def get_session_file(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "session.json"

    async def shutdown(self) -> None:
        for session_id in list(self._processes.keys()):
            await self.stop_session(session_id)

    async def _consume_stream(self, session_id: str, stream, *, is_stderr: bool) -> None:
        if stream is None:
            return

        while True:
            line = await stream.readline()
            if not line:
                break

            text = line.decode("utf-8", errors="replace").rstrip()
            if not text:
                continue

            event = decode_debug_event(text)
            if event:
                await self._handle_worker_event(session_id, event)
                continue

            await self._append_log(session_id, text, source="stderr" if is_stderr else "stdout")

    async def _handle_worker_event(self, session_id: str, event: dict) -> None:
        session = await self.get_session(session_id)
        if not session:
            return

        event_type = event.get("type")
        if event_type == "state":
            state = event.get("state")
            if state:
                session.state = DebugSessionState(state)
            if "attach_host" in event and event["attach_host"]:
                session.attach_host = str(event["attach_host"])
            if "attach_port" in event and event["attach_port"]:
                session.attach_port = int(event["attach_port"])
            if "env_id" in event and event["env_id"] is not None:
                session.env_id = str(event["env_id"])
            if "last_error" in event and event["last_error"]:
                session.last_error = str(event["last_error"])
            if session.state in FINAL_DEBUG_STATES:
                session.finished_at = session.finished_at or int(time.time())
            await self.repo.save_session(session)
            return

        if event_type == "log":
            await self._append_log(session_id, str(event.get("message", "")))

    async def _append_log(self, session_id: str, message: str, *, source: str = "") -> None:
        session = await self.get_session(session_id)
        if not session:
            return

        prefix = f"[{source}] " if source else ""
        session.logs.append(prefix + message)
        if len(session.logs) > 500:
            session.logs = session.logs[-500:]

    async def _watch_process(self, session_id: str, process) -> None:
        return_code = await process.wait()
        stream_tasks = self._stream_tasks.pop(session_id, [])
        if stream_tasks:
            await asyncio.gather(*stream_tasks, return_exceptions=True)

        session = await self.get_session(session_id)
        if not session:
            return

        if session.state == DebugSessionState.STOPPING:
            session.state = DebugSessionState.STOPPED
            session.finished_at = int(time.time())
        elif session.state not in FINAL_DEBUG_STATES:
            session.finished_at = int(time.time())
            if return_code == 0:
                session.state = DebugSessionState.STOPPED
            else:
                session.state = DebugSessionState.FAILED
                if not session.last_error:
                    session.last_error = f"Debug worker exited with code {return_code}"

        await self.repo.save_session(session)
        self._processes.pop(session_id, None)
        self._watch_tasks.pop(session_id, None)

    def _session_dir(self, session_id: str) -> Path:
        return self._session_root / session_id

    def _stop_flag_file(self, session_id: str) -> Path:
        return self._session_dir(session_id) / "stop.flag"

    def _allocate_attach_port(self, host: str, preferred_port: int) -> int:
        if preferred_port > 0 and self._port_is_available(host, preferred_port):
            return preferred_port

        start = preferred_port + 1 if preferred_port > 0 else 5678
        for port in range(start, start + 50):
            if self._port_is_available(host, port):
                return port

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, 0))
            return int(sock.getsockname()[1])

    def _port_is_available(self, host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                return False
        return True


_service: DebugService | None = None


def get_debug_service() -> DebugService:
    global _service
    if _service is None:
        _service = DebugService()
    return _service

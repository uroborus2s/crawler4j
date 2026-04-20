import asyncio
import json
import socket
import time
from pathlib import Path
from textwrap import dedent

import pytest


class _DapClient:
    def __init__(self, host: str, port: int, *, timeout: float = 30.0):
        self._sock = socket.create_connection((host, port), timeout=timeout)
        self._sock.settimeout(timeout)
        self._seq = 1

    def close(self) -> None:
        self._sock.close()

    def send(self, command: str, arguments: dict | None = None) -> int:
        message = {
            "seq": self._seq,
            "type": "request",
            "command": command,
            "arguments": arguments or {},
        }
        self._seq += 1
        payload = json.dumps(message).encode("utf-8")
        packet = f"Content-Length: {len(payload)}\r\n\r\n".encode("utf-8") + payload
        self._sock.sendall(packet)
        return int(message["seq"])

    def recv(self) -> dict:
        header = b""
        while b"\r\n\r\n" not in header:
            header += self._recv_exact(1)

        raw_headers, rest = header.split(b"\r\n\r\n", 1)
        headers = {}
        for line in raw_headers.decode("utf-8").split("\r\n"):
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()

        body_len = int(headers["content-length"])
        body = rest + self._recv_exact(body_len - len(rest))
        return json.loads(body.decode("utf-8"))

    def _recv_exact(self, size: int) -> bytes:
        data = b""
        while len(data) < size:
            chunk = self._sock.recv(size - len(data))
            if not chunk:
                raise EOFError("DAP socket closed")
            data += chunk
        return data


def _wait_for_message(client: _DapClient, predicate, *, limit: int = 100) -> dict:
    messages: list[dict] = []
    for _ in range(limit):
        message = client.recv()
        messages.append(message)
        if predicate(message):
            return message
    raise AssertionError(f"Did not receive expected DAP message. Seen: {messages!r}")


def _find_marker_line(source: str, marker: str) -> int:
    for index, line in enumerate(source.splitlines(), start=1):
        if marker in line:
            return index
    raise AssertionError(f"marker not found: {marker}")


def _write_debuggable_module(base_dir: Path) -> tuple[Path, Path, int, Path, int]:
    module_dir = base_dir / "demo_module"
    tasks_dir = module_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    init_source = dedent(
        """
        from .tasks.login_task import run_login


        async def init_env(context):
            runtime_params = context.runtime.get("params", {})
            accounts = runtime_params.get("accounts", [])
            if accounts:
                context.state["selected_account_phone"] = accounts[0]["phone_number"]


        async def run(context):
            workflow = context.runtime.get("workflow", "login_workflow")
            if workflow != "login_workflow":
                raise ValueError(f"Unsupported workflow: {workflow}")
            return await run_login(context)  # MODULE_FRAME
        """
    ).strip() + "\n"
    task_source = dedent(
        """
        from crawler4j_sdk import TaskResult


        async def run_login(context):
            runtime_params = context.runtime.get("params", {})
            accounts = runtime_params.get("accounts", [])
            phone = accounts[0]["phone_number"] if accounts else ""
            if context.page:
                await context.page.goto(
                    runtime_params.get("login_url", "about:blank"),
                    wait_until="domcontentloaded",
                )
            selected_phone = phone  # BREAKPOINT
            return TaskResult.ok(phone=selected_phone)
        """
    ).strip() + "\n"
    manifest_source = dedent(
        """
        name: demo_module
        version: 1.0.0
        upgrade_source:
          type: github_release
          repo: example/demo_module
        workflows:
          - name: login_workflow
            display_name: 登录流程
        """
    ).strip() + "\n"

    (module_dir / "__init__.py").write_text(init_source, encoding="utf-8")
    (module_dir / "module.yaml").write_text(manifest_source, encoding="utf-8")
    (tasks_dir / "__init__.py").write_text("", encoding="utf-8")
    (tasks_dir / "login_task.py").write_text(task_source, encoding="utf-8")

    breakpoint_file = tasks_dir / "login_task.py"
    module_frame = module_dir / "__init__.py"
    return (
        module_dir,
        breakpoint_file,
        _find_marker_line(task_source, "# BREAKPOINT"),
        module_frame,
        _find_marker_line(init_source, "# MODULE_FRAME"),
    )


def _initialize_attach(client: _DapClient) -> None:
    client.send(
        "initialize",
        {
            "adapterID": "debugpy",
            "pathFormat": "path",
            "linesStartAt1": True,
            "columnsStartAt1": True,
            "supportsVariableType": True,
            "supportsVariablePaging": True,
            "supportsRunInTerminalRequest": False,
        },
    )
    _wait_for_message(
        client,
        lambda msg: msg.get("type") == "response" and msg.get("command") == "initialize",
    )

    client.send("attach", {"justMyCode": False, "subProcess": False})
    _wait_for_message(
        client,
        lambda msg: msg.get("type") == "event" and msg.get("event") == "initialized",
    )


def _set_breakpoints(client: _DapClient, breakpoint_file: Path, breakpoint_line: int) -> dict:
    client.send(
        "setBreakpoints",
        {
            "source": {"path": str(breakpoint_file)},
            "lines": [breakpoint_line],
            "breakpoints": [{"line": breakpoint_line}],
            "sourceModified": False,
        },
    )
    return _wait_for_message(
        client,
        lambda msg: msg.get("type") == "response" and msg.get("command") == "setBreakpoints",
    )


def _set_exception_breakpoints(client: _DapClient) -> None:
    client.send("setExceptionBreakpoints", {"filters": []})
    _wait_for_message(
        client,
        lambda msg: (
            msg.get("type") == "response"
            and msg.get("command") == "setExceptionBreakpoints"
        ),
    )


def _send_configuration_done(client: _DapClient) -> dict:
    client.send("configurationDone", {})
    return _wait_for_message(
        client,
        lambda msg: msg.get("type") == "event" and msg.get("event") == "stopped",
    )


def _send_configuration_done_response(client: _DapClient) -> dict:
    client.send("configurationDone", {})
    return _wait_for_message(
        client,
        lambda msg: msg.get("type") == "response" and msg.get("command") == "configurationDone",
    )


def _exercise_debug_attach(host: str, port: int, breakpoint_file: Path, breakpoint_line: int) -> dict:
    # The worker still needs to create and connect a real browser environment
    # after the initial stop-on-entry breakpoint resumes, so allow a longer DAP
    # socket timeout before declaring the module breakpoint missing.
    client = _DapClient(host, port, timeout=30.0)
    try:
        _initialize_attach(client)
        breakpoints_response = _set_breakpoints(client, breakpoint_file, breakpoint_line)
        _set_exception_breakpoints(client)
        initial_stop = _send_configuration_done(client)

        client.send("threads", {})
        threads_response = _wait_for_message(
            client,
            lambda msg: msg.get("type") == "response" and msg.get("command") == "threads",
        )
        thread_id = int(threads_response["body"]["threads"][0]["id"])

        client.send("continue", {"threadId": thread_id})
        _wait_for_message(
            client,
            lambda msg: msg.get("type") == "response" and msg.get("command") == "continue",
        )
        breakpoint_stop = _wait_for_message(
            client,
            lambda msg: msg.get("type") == "event" and msg.get("event") == "stopped",
        )

        client.send("stackTrace", {"threadId": thread_id})
        stack_trace = _wait_for_message(
            client,
            lambda msg: msg.get("type") == "response" and msg.get("command") == "stackTrace",
        )

        client.send("continue", {"threadId": thread_id})
        _wait_for_message(
            client,
            lambda msg: msg.get("type") == "response" and msg.get("command") == "continue",
        )

        return {
            "breakpoints_response": breakpoints_response,
            "initial_stop": initial_stop,
            "breakpoint_stop": breakpoint_stop,
            "stack_trace": stack_trace,
        }
    finally:
        client.close()


def _exercise_debug_attach_without_stop_on_entry(
    host: str,
    port: int,
    breakpoint_file: Path,
    breakpoint_line: int,
) -> dict:
    client = _DapClient(host, port, timeout=30.0)
    try:
        _initialize_attach(client)
        breakpoints_response = _set_breakpoints(client, breakpoint_file, breakpoint_line)
        _set_exception_breakpoints(client)
        configuration_done = _send_configuration_done_response(client)

        breakpoint_stop = _wait_for_message(
            client,
            lambda msg: msg.get("type") == "event" and msg.get("event") == "stopped",
            limit=200,
        )

        thread_id = breakpoint_stop.get("body", {}).get("threadId")
        if thread_id is None:
            client.send("threads", {})
            threads_response = _wait_for_message(
                client,
                lambda msg: msg.get("type") == "response" and msg.get("command") == "threads",
            )
            thread_id = int(threads_response["body"]["threads"][0]["id"])

        client.send("stackTrace", {"threadId": int(thread_id)})
        stack_trace = _wait_for_message(
            client,
            lambda msg: msg.get("type") == "response" and msg.get("command") == "stackTrace",
        )

        client.send("continue", {"threadId": int(thread_id)})
        _wait_for_message(
            client,
            lambda msg: msg.get("type") == "response" and msg.get("command") == "continue",
        )

        return {
            "breakpoints_response": breakpoints_response,
            "configuration_done": configuration_done,
            "breakpoint_stop": breakpoint_stop,
            "stack_trace": stack_trace,
        }
    finally:
        client.close()


async def _wait_for_session_state(debug_service, session_id: str, states: set, timeout: float = 15.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        session = await debug_service.get_session(session_id)
        if session and session.state in states:
            return session
        await asyncio.sleep(0.1)

    session = await debug_service.get_session(session_id)
    raise AssertionError(f"Timed out waiting for session state {states}: {session}")


async def _assert_session_stays_in_state(debug_service, session_id: str, state, duration: float = 0.5):
    deadline = time.time() + duration
    while time.time() < deadline:
        session = await debug_service.get_session(session_id)
        assert session is not None
        assert session.state == state
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_task_debug_session_hits_module_breakpoint(tmp_path, monkeypatch):
    from src.core.atm.service import TaskService
    from src.core.atm.run_profile import (
        AcquisitionConfig,
        AcquisitionMode,
        CreationConfig,
        CreationLifecycle,
        ExecutionContext,
        EnvType,
        ResourceConfig,
        RunProfile,
    )
    from src.core.debug.models import DebugSessionRequest, DebugSessionState
    from src.core.debug.service import DebugService
    from src.core.mms.registry import ModuleRegistry
    from src.core.persistence import init_database

    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))

    module_dir, breakpoint_file, breakpoint_line, module_frame, module_line = _write_debuggable_module(tmp_path)

    init_database()

    registry = ModuleRegistry()
    registry.register_dev_link(module_dir)

    run_profile = RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                provider="playwright_local",
                env_type=EnvType.CHROME,
                wait_timeout=30,
                creation=CreationConfig(lifecycle=CreationLifecycle.EPHEMERAL, params={}),
            ),
        ),
        execution=ExecutionContext(
            module="demo_module",
            workflow="login_workflow",
            params={
                "login_url": "about:blank",
                "accounts": [{"id": "u1", "phone_number": "13800000001", "country_code": "86"}],
                "auto_click_send_code": False,
            },
            timeout=60,
        ),
    )

    task_service = TaskService()
    job_id = await task_service.create_job(
        name="Debug E2E Module",
        job_type="service",
        run_profile=run_profile,
        params={"start_url": "about:blank"},
    )

    debug_service = DebugService(
        registry=registry,
        task_service=task_service,
    )

    session = None
    try:
        session = await debug_service.create_session(
            DebugSessionRequest(
                job_id=job_id,
                attach_host="127.0.0.1",
                attach_port=5678,
                wait_for_attach=True,
                stop_on_entry=True,
            )
        )
        await debug_service.start_session(session.id)

        session = await _wait_for_session_state(
            debug_service,
            session.id,
            {DebugSessionState.WAITING_FOR_ATTACH},
        )

        dap_result = await asyncio.to_thread(
            _exercise_debug_attach,
            session.attach_host,
            session.attach_port,
            breakpoint_file,
            breakpoint_line,
        )

        session = await _wait_for_session_state(
            debug_service,
            session.id,
            {
                DebugSessionState.SUCCEEDED,
                DebugSessionState.FAILED,
                DebugSessionState.STOPPED,
            },
        )
    finally:
        await debug_service.shutdown()

    verified_breakpoints = dap_result["breakpoints_response"]["body"]["breakpoints"]
    assert verified_breakpoints[0]["verified"] is True
    assert verified_breakpoints[0]["line"] == breakpoint_line

    assert dap_result["initial_stop"]["body"]["reason"] == "breakpoint"
    assert dap_result["breakpoint_stop"]["body"]["reason"] == "breakpoint"

    stack_frames = dap_result["stack_trace"]["body"]["stackFrames"]
    top_frame = stack_frames[0]
    assert Path(top_frame["source"]["path"]) == breakpoint_file
    assert top_frame["line"] == breakpoint_line

    module_frames = [
        frame
        for frame in stack_frames
        if Path(frame["source"]["path"]) == module_frame
    ]
    assert module_frames
    assert any(frame["line"] == module_line for frame in module_frames)

    assert session is not None
    assert session.state in {
        DebugSessionState.SUCCEEDED,
        DebugSessionState.FAILED,
        DebugSessionState.STOPPED,
    }


@pytest.mark.asyncio
async def test_task_debug_session_hits_module_breakpoint_without_stop_on_entry(tmp_path, monkeypatch):
    from src.core.atm.service import TaskService
    from src.core.atm.run_profile import (
        AcquisitionConfig,
        AcquisitionMode,
        CreationConfig,
        CreationLifecycle,
        ExecutionContext,
        EnvType,
        ResourceConfig,
        RunProfile,
    )
    from src.core.debug.models import DebugSessionRequest, DebugSessionState
    from src.core.debug.service import DebugService
    from src.core.mms.registry import ModuleRegistry
    from src.core.persistence import init_database

    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))

    module_dir, breakpoint_file, breakpoint_line, _module_frame, _module_line = _write_debuggable_module(tmp_path)

    init_database()

    registry = ModuleRegistry()
    registry.register_dev_link(module_dir)

    run_profile = RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                provider="playwright_local",
                env_type=EnvType.CHROME,
                wait_timeout=30,
                creation=CreationConfig(lifecycle=CreationLifecycle.EPHEMERAL, params={}),
            ),
        ),
        execution=ExecutionContext(
            module="demo_module",
            workflow="login_workflow",
            params={
                "login_url": "about:blank",
                "accounts": [{"id": "u1", "phone_number": "13800000001", "country_code": "86"}],
                "auto_click_send_code": False,
            },
            timeout=60,
        ),
    )

    task_service = TaskService()
    job_id = await task_service.create_job(
        name="Debug E2E Module Without Stop On Entry",
        job_type="service",
        run_profile=run_profile,
        params={"start_url": "about:blank"},
    )

    debug_service = DebugService(
        registry=registry,
        task_service=task_service,
    )

    session = None
    try:
        session = await debug_service.create_session(
            DebugSessionRequest(
                job_id=job_id,
                attach_host="127.0.0.1",
                attach_port=5678,
                wait_for_attach=True,
                stop_on_entry=False,
            )
        )
        await debug_service.start_session(session.id)

        session = await _wait_for_session_state(
            debug_service,
            session.id,
            {DebugSessionState.WAITING_FOR_ATTACH},
        )

        await _assert_session_stays_in_state(
            debug_service,
            session.id,
            DebugSessionState.WAITING_FOR_ATTACH,
            duration=1.5,
        )

        dap_result = await asyncio.to_thread(
            _exercise_debug_attach_without_stop_on_entry,
            session.attach_host,
            session.attach_port,
            breakpoint_file,
            breakpoint_line,
        )

        session = await _wait_for_session_state(
            debug_service,
            session.id,
            {
                DebugSessionState.SUCCEEDED,
                DebugSessionState.FAILED,
                DebugSessionState.STOPPED,
            },
        )
    finally:
        await debug_service.shutdown()

    verified_breakpoints = dap_result["breakpoints_response"]["body"]["breakpoints"]
    assert verified_breakpoints[0]["verified"] is True
    assert verified_breakpoints[0]["line"] == breakpoint_line

    assert dap_result["configuration_done"]["success"] is True
    assert dap_result["breakpoint_stop"]["body"]["reason"] == "breakpoint"

    stack_frames = dap_result["stack_trace"]["body"]["stackFrames"]
    top_frame = stack_frames[0]
    assert Path(top_frame["source"]["path"]) == breakpoint_file
    assert top_frame["line"] == breakpoint_line

    assert session is not None
    assert session.state in {
        DebugSessionState.SUCCEEDED,
        DebugSessionState.FAILED,
        DebugSessionState.STOPPED,
    }


@pytest.mark.asyncio
async def test_task_debug_session_waits_for_configuration_done_before_running(tmp_path, monkeypatch):
    from src.core.atm.service import TaskService
    from src.core.atm.run_profile import (
        AcquisitionConfig,
        AcquisitionMode,
        CreationConfig,
        CreationLifecycle,
        ExecutionContext,
        EnvType,
        ResourceConfig,
        RunProfile,
    )
    from src.core.debug.models import DebugSessionRequest, DebugSessionState
    from src.core.debug.service import DebugService
    from src.core.mms.registry import ModuleRegistry
    from src.core.persistence import init_database

    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))

    module_dir, breakpoint_file, breakpoint_line, _module_frame, _module_line = _write_debuggable_module(tmp_path)

    init_database()

    registry = ModuleRegistry()
    registry.register_dev_link(module_dir)

    run_profile = RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                provider="playwright_local",
                env_type=EnvType.CHROME,
                wait_timeout=30,
                creation=CreationConfig(lifecycle=CreationLifecycle.EPHEMERAL, params={}),
            ),
        ),
        execution=ExecutionContext(
            module="demo_module",
            workflow="login_workflow",
            params={
                "login_url": "about:blank",
                "accounts": [{"id": "u1", "phone_number": "13800000001", "country_code": "86"}],
                "auto_click_send_code": False,
            },
            timeout=60,
        ),
    )

    task_service = TaskService()
    job_id = await task_service.create_job(
        name="Debug E2E Wait Config",
        job_type="service",
        run_profile=run_profile,
        params={"start_url": "about:blank"},
    )

    debug_service = DebugService(
        registry=registry,
        task_service=task_service,
    )

    session = None
    client = None
    try:
        session = await debug_service.create_session(
            DebugSessionRequest(
                job_id=job_id,
                attach_host="127.0.0.1",
                attach_port=5678,
                wait_for_attach=True,
                stop_on_entry=True,
            )
        )
        await debug_service.start_session(session.id)

        session = await _wait_for_session_state(
            debug_service,
            session.id,
            {DebugSessionState.WAITING_FOR_ATTACH},
        )

        client = _DapClient(session.attach_host, session.attach_port, timeout=30.0)
        _initialize_attach(client)
        _set_breakpoints(client, breakpoint_file, breakpoint_line)
        _set_exception_breakpoints(client)

        await _assert_session_stays_in_state(
            debug_service,
            session.id,
            DebugSessionState.WAITING_FOR_ATTACH,
        )

        initial_stop = _send_configuration_done(client)
        assert initial_stop["body"]["reason"] == "breakpoint"
    finally:
        if client is not None:
            client.close()
        await debug_service.shutdown()


@pytest.mark.asyncio
async def test_task_debug_session_waits_for_dap_handshake_before_running(tmp_path, monkeypatch):
    from src.core.atm.service import TaskService
    from src.core.atm.run_profile import (
        AcquisitionConfig,
        AcquisitionMode,
        CreationConfig,
        CreationLifecycle,
        ExecutionContext,
        EnvType,
        ResourceConfig,
        RunProfile,
    )
    from src.core.debug.models import DebugSessionRequest, DebugSessionState
    from src.core.debug.service import DebugService
    from src.core.mms.registry import ModuleRegistry
    from src.core.persistence import init_database

    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home_dir))

    module_dir, breakpoint_file, breakpoint_line, _module_frame, _module_line = _write_debuggable_module(tmp_path)

    init_database()

    registry = ModuleRegistry()
    registry.register_dev_link(module_dir)

    run_profile = RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                provider="playwright_local",
                env_type=EnvType.CHROME,
                wait_timeout=30,
                creation=CreationConfig(lifecycle=CreationLifecycle.EPHEMERAL, params={}),
            ),
        ),
        execution=ExecutionContext(
            module="demo_module",
            workflow="login_workflow",
            params={
                "login_url": "about:blank",
                "accounts": [{"id": "u1", "phone_number": "13800000001", "country_code": "86"}],
                "auto_click_send_code": False,
            },
            timeout=60,
        ),
    )

    task_service = TaskService()
    job_id = await task_service.create_job(
        name="Debug E2E Wait Handshake",
        job_type="service",
        run_profile=run_profile,
        params={"start_url": "about:blank"},
    )

    debug_service = DebugService(
        registry=registry,
        task_service=task_service,
    )

    session = None
    client = None
    try:
        session = await debug_service.create_session(
            DebugSessionRequest(
                job_id=job_id,
                attach_host="127.0.0.1",
                attach_port=5678,
                wait_for_attach=True,
                stop_on_entry=True,
            )
        )
        await debug_service.start_session(session.id)

        session = await _wait_for_session_state(
            debug_service,
            session.id,
            {DebugSessionState.WAITING_FOR_ATTACH},
        )

        client = _DapClient(session.attach_host, session.attach_port, timeout=30.0)

        await _assert_session_stays_in_state(
            debug_service,
            session.id,
            DebugSessionState.WAITING_FOR_ATTACH,
        )

        _initialize_attach(client)
        _set_breakpoints(client, breakpoint_file, breakpoint_line)
        _set_exception_breakpoints(client)
        initial_stop = _send_configuration_done(client)
        assert initial_stop["body"]["reason"] == "breakpoint"
    finally:
        if client is not None:
            client.close()
        await debug_service.shutdown()

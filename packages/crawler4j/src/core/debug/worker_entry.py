"""Debug worker subprocess entry."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys
from typing import Any

from crawler4j_contracts import EnvAction
from src.core.atm.execution_runner import ExecutionRequest, ExecutionRunner
from src.core.debug.launcher import configure_debugpy_for_frozen_bundle
from src.core.atm.run_profile import AcquisitionMode, CreationLifecycle
from src.core.debug.models import DebugSessionState
from src.core.debug.protocol import encode_debug_event
from src.core.persistence import init_database
from src.core.rem.manager import get_environment_manager


def _emit_event(payload: dict[str, Any]) -> None:
    print(encode_debug_event(payload), flush=True)


async def _wait_for_attach(debugpy_module, stop_flag: Path) -> bool:
    wait_task = asyncio.create_task(asyncio.to_thread(debugpy_module.wait_for_client))
    stop_requested = False

    while True:
        if wait_task.done():
            try:
                await wait_task
            except Exception:
                if stop_requested or stop_flag.exists():
                    return False
                raise
            return not stop_requested and not stop_flag.exists()

        if stop_flag.exists():
            stop_requested = True
            try:
                debugpy_module.wait_for_client.cancel()
            except RuntimeError:
                # wait_for_client() may not have installed its cancel hook yet.
                pass

        await asyncio.sleep(0.1)


def _map_final_state(task_status: str) -> DebugSessionState:
    mapping = {
        "succeeded": DebugSessionState.SUCCEEDED,
        "failed": DebugSessionState.FAILED,
        "cancelled": DebugSessionState.STOPPED,
    }
    return mapping.get(task_status, DebugSessionState.FAILED)


async def main_async(config_path: str) -> int:
    init_database()

    config_file = Path(config_path)
    session_dir = config_file.parent
    stop_flag = session_dir / "stop.flag"
    payload = json.loads(config_file.read_text(encoding="utf-8"))

    try:
        import debugpy
    except ImportError as exc:
        _emit_event(
            {
                "type": "state",
                "state": DebugSessionState.FAILED.value,
                "last_error": f"debugpy is not installed: {exc}",
            }
        )
        return 1

    await get_environment_manager().startup(recover_crashed=False)

    configure_debugpy_for_frozen_bundle(
        debugpy,
        executable=sys.executable,
        session_dir=session_dir,
        frozen=bool(getattr(sys, "frozen", False)),
    )
    debugpy.listen((payload["attach_host"], int(payload["attach_port"])))
    if payload.get("wait_for_attach", True):
        _emit_event(
            {
                "type": "state",
                "state": DebugSessionState.WAITING_FOR_ATTACH.value,
                "attach_host": payload["attach_host"],
                "attach_port": int(payload["attach_port"]),
            }
        )
        attached = await _wait_for_attach(debugpy, stop_flag)
        if not attached:
            _emit_event({"type": "state", "state": DebugSessionState.STOPPED.value})
            return 0

    if stop_flag.exists():
        _emit_event({"type": "state", "state": DebugSessionState.STOPPED.value})
        return 0

    if payload.get("stop_on_entry", False):
        debugpy.breakpoint()

    from src.core.mms.registry import get_module_registry

    get_module_registry().refresh()

    _emit_event({"type": "state", "state": DebugSessionState.RUNNING.value})

    from src.core.atm.models import Task

    request = ExecutionRequest(
        task=Task(id=payload["id"], job_id=payload.get("job_id", f"debug:{payload['id']}")),
        module_name=payload["module_name"],
        workflow_name=payload.get("workflow") or "default",
        object_bindings=dict(payload.get("object_bindings") or {}),
        object_params=dict(payload.get("object_params") or {}),
        devel_mode=bool(payload.get("devel_mode", True)),
        state={
            "debug_session_id": payload["id"],
            "job_id": payload.get("job_id", ""),
            "task_id": payload["id"],
        },
        provider_name=payload.get("provider") or "playwright_local",
        acquisition_mode=AcquisitionMode(payload.get("acquisition_mode", AcquisitionMode.CREATE.value)),
        fixed_env_id=payload.get("fixed_env_id"),
        candidates_name=str(payload.get("candidates") or ""),
        candidate_params=dict(payload.get("candidate_params") or {}),
        creation_params=dict(payload.get("creation_params") or {}),
        creation_lifecycle=CreationLifecycle(
            payload.get("creation_lifecycle", CreationLifecycle.PERSISTENT.value)
        ),
        wait_timeout=int(payload.get("wait_timeout", 60)),
        execution_timeout=int(payload.get("timeout", 0)),
        default_env_action=EnvAction.KEEP_ALIVE if payload.get("keep_environment") else None,
    )

    runner = ExecutionRunner()
    result = await runner.run(
        request,
        is_stop_requested=lambda: stop_flag.exists(),
    )

    final_state = _map_final_state(result.task.status.value)
    _emit_event(
        {
            "type": "state",
            "state": final_state.value,
            "env_id": result.task.env_id,
            "last_error": result.task.error,
        }
    )
    return 0 if final_state != DebugSessionState.FAILED else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="蛛行演略（crawler4j） debug worker")
    parser.add_argument("config_path")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args.config_path)))


if __name__ == "__main__":
    main()

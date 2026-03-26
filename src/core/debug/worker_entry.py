"""Debug worker subprocess entry."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from src.core.atm.execution_runner import ExecutionRequest, ExecutionRunner
from src.core.debug.models import DebugSessionState
from src.core.debug.protocol import encode_debug_event
from src.core.persistence import init_database
from src.core.rem.manager import get_environment_manager
from src.core.tsm.models import AcquisitionMode, CreationLifecycle


def _emit_event(payload: dict[str, Any]) -> None:
    print(encode_debug_event(payload), flush=True)


async def _wait_for_attach(debugpy_module, stop_flag: Path) -> bool:
    while not debugpy_module.is_client_connected():
        if stop_flag.exists():
            return False
        await asyncio.sleep(0.1)
    return True


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

    await get_environment_manager().startup()

    from src.core.mms.registry import get_module_registry

    get_module_registry().refresh()

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

    _emit_event({"type": "state", "state": DebugSessionState.RUNNING.value})

    from src.core.atm.models import Task

    request = ExecutionRequest(
        task=Task(id=payload["id"], job_id=payload.get("job_id", f"debug:{payload['id']}")),
        module_name=payload["module_name"],
        hooks_module=payload.get("hooks_module") or payload["module_name"],
        params={**(payload.get("params") or {}), "workflow": payload.get("workflow") or "default"},
        state={
            "debug_session_id": payload["id"],
            "job_id": payload.get("job_id", ""),
            "task_id": payload["id"],
            "strategy_id": payload.get("strategy_id", ""),
        },
        provider_name=payload.get("provider") or "playwright_local",
        acquisition_mode=AcquisitionMode(payload.get("acquisition_mode", AcquisitionMode.CREATE.value)),
        creation_params=dict(payload.get("creation_params") or {}),
        creation_lifecycle=CreationLifecycle(
            payload.get("creation_lifecycle", CreationLifecycle.EPHEMERAL.value)
        ),
        selector_wait_timeout=int(payload.get("wait_timeout", 60)),
        execution_timeout=int(payload.get("timeout", 0)),
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
    parser = argparse.ArgumentParser(description="Crawler4j debug worker")
    parser.add_argument("config_path")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args.config_path)))


if __name__ == "__main__":
    main()

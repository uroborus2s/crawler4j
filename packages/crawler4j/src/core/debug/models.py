"""Debug session data models."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.core.atm.run_profile import AcquisitionMode, CreationLifecycle


class DebugSessionState(StrEnum):
    CREATED = "created"
    STARTING = "starting"
    WAITING_FOR_ATTACH = "waiting_for_attach"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    STOPPING = "stopping"
    STOPPED = "stopped"


FINAL_DEBUG_STATES = {
    DebugSessionState.SUCCEEDED,
    DebugSessionState.FAILED,
    DebugSessionState.STOPPED,
}


@dataclass
class DebugSessionRequest:
    job_id: str
    timeout: int = 0
    attach_host: str = "127.0.0.1"
    attach_port: int = 5678
    wait_for_attach: bool = True
    stop_on_entry: bool = False


@dataclass
class DebugSession:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    job_id: str = ""
    job_name: str = ""
    module_name: str = ""
    source_path: str = ""
    workflow: str = ""
    object_bindings: dict[str, str] = field(default_factory=dict)
    object_params: dict[str, dict[str, Any]] = field(default_factory=dict)
    provider: str = "playwright_local"
    acquisition_mode: AcquisitionMode = AcquisitionMode.CREATE
    fixed_env_id: int | None = None
    candidates: str = ""
    candidate_params: dict[str, Any] = field(default_factory=dict)
    creation_params: dict[str, Any] = field(default_factory=dict)
    creation_lifecycle: CreationLifecycle = CreationLifecycle.PERSISTENT
    wait_timeout: int = 60
    timeout: int = 0
    attach_host: str = "127.0.0.1"
    attach_port: int = 5678
    wait_for_attach: bool = True
    stop_on_entry: bool = False
    state: DebugSessionState = DebugSessionState.CREATED
    worker_pid: int | None = None
    env_id: str | None = None
    created_at: int = field(default_factory=lambda: int(time.time()))
    started_at: int | None = None
    finished_at: int | None = None
    last_error: str = ""
    logs: list[str] = field(default_factory=list, repr=False)

    def __post_init__(self):
        if isinstance(self.acquisition_mode, str):
            self.acquisition_mode = AcquisitionMode(self.acquisition_mode)
        if isinstance(self.creation_lifecycle, str):
            self.creation_lifecycle = CreationLifecycle(self.creation_lifecycle)
        if isinstance(self.state, str):
            self.state = DebugSessionState(self.state)

    def is_final(self) -> bool:
        return self.state in FINAL_DEBUG_STATES

    def to_worker_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "job_name": self.job_name,
            "module_name": self.module_name,
            "source_path": self.source_path,
            "workflow": self.workflow,
            "object_bindings": self.object_bindings,
            "object_params": self.object_params,
            "provider": self.provider,
            "acquisition_mode": self.acquisition_mode.value,
            "fixed_env_id": self.fixed_env_id,
            "candidates": self.candidates,
            "candidate_params": self.candidate_params,
            "creation_params": self.creation_params,
            "creation_lifecycle": self.creation_lifecycle.value,
            "wait_timeout": self.wait_timeout,
            "timeout": self.timeout,
            "attach_host": self.attach_host,
            "attach_port": self.attach_port,
            "wait_for_attach": self.wait_for_attach,
            "stop_on_entry": self.stop_on_entry,
        }

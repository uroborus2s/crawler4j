"""自动化任务管理 (Automation Task Management) V2."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    "Job": "src.core.atm.models",
    "JobState": "src.core.atm.models",
    "JobType": "src.core.atm.models",
    "Task": "src.core.atm.models",
    "TaskStatus": "src.core.atm.models",
    "TriggerConfig": "src.core.atm.models",
    "TaskRepository": "src.core.atm.repository",
    "get_task_repository": "src.core.atm.repository",
    "TaskService": "src.core.atm.service",
    "get_task_service": "src.core.atm.service",
    "JobController": "src.core.atm.controller",
    "get_job_controller": "src.core.atm.controller",
    "TaskDispatcher": "src.core.atm.dispatcher",
    "get_task_dispatcher": "src.core.atm.dispatcher",
}

__all__ = list(_EXPORT_MODULES)


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(name)
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value

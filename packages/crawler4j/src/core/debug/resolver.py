"""Helpers for building task-centric debug targets."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.atm.job_runtime import resolve_job_run_profile
from src.core.atm.run_profile import RunProfile
from src.core.atm.models import Job
from src.core.mms.models import ModuleInfo
from src.core.mms.registry import ModuleRegistry, get_module_registry


@dataclass
class JobDebugTarget:
    job: Job
    run_profile: RunProfile
    module: ModuleInfo
    workflow: str
    hooks_module: str
    execution_params: dict = field(default_factory=dict)
    job_params: dict = field(default_factory=dict)
    runtime_params: dict = field(default_factory=dict)
    timeout: int = 0
    wait_timeout: int = 60


def resolve_job_debug_target(
    job: Job,
    *,
    registry: ModuleRegistry | None = None,
) -> JobDebugTarget:
    module_registry = registry or get_module_registry()

    run_profile = resolve_job_run_profile(job)
    if not run_profile.execution:
        raise ValueError(f"Job {job.id} missing run_profile.execution")
    if not run_profile.execution.module:
        raise ValueError(f"Job {job.id} missing run_profile.execution.module")

    module = module_registry.get_module(run_profile.execution.module)
    if not module:
        raise ValueError(f"Module '{run_profile.execution.module}' not found")
    if not module.path:
        raise ValueError(f"Module '{run_profile.execution.module}' has no valid path")

    return JobDebugTarget(
        job=job,
        run_profile=run_profile,
        module=module,
        workflow=run_profile.execution.workflow or "default",
        hooks_module=run_profile.execution.hooks_module or run_profile.execution.module,
        execution_params=dict(run_profile.execution.params),
        job_params=dict(job.params),
        runtime_params={**run_profile.execution.params, **job.params},
        timeout=run_profile.execution.timeout,
        wait_timeout=run_profile.resource.acquisition.wait_timeout,
    )

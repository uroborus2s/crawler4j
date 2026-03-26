"""Helpers for building task-centric debug targets."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.atm.models import Job
from src.core.mms.models import ModuleInfo
from src.core.mms.registry import ModuleRegistry, get_module_registry
from src.core.tsm.loader import StrategyLoader, get_strategy_loader
from src.core.tsm.models import TaskStrategy


@dataclass
class JobDebugTarget:
    job: Job
    strategy: TaskStrategy
    module: ModuleInfo
    workflow: str
    hooks_module: str
    params: dict = field(default_factory=dict)
    timeout: int = 0
    wait_timeout: int = 60


def resolve_job_debug_target(
    job: Job,
    *,
    strategy_loader: StrategyLoader | None = None,
    registry: ModuleRegistry | None = None,
) -> JobDebugTarget:
    loader = strategy_loader or get_strategy_loader()
    module_registry = registry or get_module_registry()

    strategy = loader.get(job.strategy_id)
    if not strategy:
        raise ValueError(f"Strategy {job.strategy_id} not found")
    if not strategy.execution:
        raise ValueError(f"Strategy {job.strategy_id} missing execution config")
    if not strategy.execution.module:
        raise ValueError(f"Strategy {job.strategy_id} missing execution.module")

    module = module_registry.get_module(strategy.execution.module)
    if not module:
        raise ValueError(f"Module '{strategy.execution.module}' not found")
    if not module.path:
        raise ValueError(f"Module '{strategy.execution.module}' has no valid path")

    return JobDebugTarget(
        job=job,
        strategy=strategy,
        module=module,
        workflow=strategy.execution.workflow or "default",
        hooks_module=strategy.execution.hooks_module or strategy.execution.module,
        params={**strategy.execution.params, **job.params},
        timeout=strategy.execution.timeout,
        wait_timeout=strategy.resource.acquisition.selector.wait_timeout,
    )

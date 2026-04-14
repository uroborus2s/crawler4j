"""Job 运行配置解析。"""

from __future__ import annotations

from src.core.atm.models import Job
from src.core.atm.run_profile import RunProfile


def describe_job_runtime(
    job: Job,
) -> tuple[str, str]:
    try:
        run_profile = resolve_job_run_profile(job)
    except Exception as exc:
        return "未配置", str(exc)

    module_name = run_profile.execution.module if run_profile.execution and run_profile.execution.module else "-"
    workflow_name = run_profile.execution.workflow if run_profile.execution and run_profile.execution.workflow else "default"
    provider_name = run_profile.resource.provider if run_profile.resource else "-"
    return ("运行模板", f"{module_name}/{workflow_name} | Provider: {provider_name}")


def resolve_job_run_profile(job: Job) -> RunProfile:
    if not job.run_profile:
        raise ValueError(f"Job {job.id} missing run_profile")
    return job.run_profile

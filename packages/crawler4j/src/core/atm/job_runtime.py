"""Job 运行配置解析。"""

from __future__ import annotations

from src.core.atm.models import Job
from src.core.atm.run_profile import AcquisitionMode, RunProfile


def describe_job_runtime(
    job: Job,
) -> tuple[str, str]:
    try:
        run_profile = resolve_job_run_profile(job)
    except Exception as exc:
        return "未配置", str(exc)

    module_name = run_profile.execution.module if run_profile.execution and run_profile.execution.module else "-"
    workflow_name = run_profile.execution.workflow if run_profile.execution and run_profile.execution.workflow else "自动解析"
    acquisition = run_profile.resource.acquisition
    if acquisition.mode == AcquisitionMode.CREATE:
        mode_text = "创建环境"
        detail = f"Provider: {acquisition.provider}"
    else:
        mode_text = "选择环境"
        candidates_text = acquisition.candidates or "-"
        detail = f"候选查询: {candidates_text}"
    return ("运行模板", f"{module_name}/{workflow_name} | {mode_text} | {detail}")


def resolve_job_run_profile(job: Job) -> RunProfile:
    if not job.run_profile:
        raise ValueError(f"Job {job.id} missing run_profile")
    return job.run_profile

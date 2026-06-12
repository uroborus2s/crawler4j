from src.core.atm.job_runtime import describe_job_runtime
from src.core.atm.models import Job
from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    ExecutionContext,
    ResourceConfig,
    RunProfile,
)


def test_describe_job_runtime_shows_fixed_env_for_select_mode():
    job = Job(
        id="job-fixed",
        name="fixed-env-job",
        run_profile=RunProfile(
            resource=ResourceConfig(
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.SELECT,
                    env_id=21,
                ),
            ),
            execution=ExecutionContext(
                module="demo_module",
                workflow="repair",
            ),
        ),
    )

    label, description = describe_job_runtime(job)

    assert label == "运行模板"
    assert "指定环境: 21" in description
    assert "候选查询" not in description


def test_describe_job_runtime_shows_candidates_for_select_mode():
    job = Job(
        id="job-candidates",
        name="candidate-job",
        run_profile=RunProfile(
            resource=ResourceConfig(
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.SELECT,
                    candidates="bound_account_ready",
                ),
            ),
            execution=ExecutionContext(
                module="demo_module",
                workflow="repair",
            ),
        ),
    )

    _, description = describe_job_runtime(job)

    assert "候选查询: bound_account_ready" in description

import pytest

from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    CreationConfig,
    CreationLifecycle,
    EnvType,
    ExecutionContext,
    ResourceConfig,
    RunProfile,
)


def test_run_profile_serialization_roundtrip_for_select_mode():
    run_profile = RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.SELECT,
                candidates="ready_accounts",
                candidate_params={"limit": 20},
                wait_timeout=120,
            ),
        ),
        execution=ExecutionContext(
            module="demo_module",
            workflow="repair",
            params={"city": "Shanghai"},
            timeout=300,
        ),
    )

    loaded = RunProfile.from_yaml(run_profile.to_yaml())

    assert loaded == run_profile


def test_run_profile_serialization_roundtrip_for_candidate_select_mode():
    run_profile = RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.SELECT,
                candidates="ready_accounts",
                wait_timeout=120,
            ),
        ),
        execution=ExecutionContext(
            module="demo_module",
            workflow="repair",
        ),
    )

    loaded = RunProfile.from_yaml(run_profile.to_yaml())

    assert loaded == run_profile


def test_execution_context_rejects_removed_hooks_module():
    with pytest.raises(ValueError, match="hooks_module"):
        ExecutionContext(
            module="demo_module",
            workflow="repair",
            hooks_module="demo_module.hooks",
        )


def test_run_profile_serialization_roundtrip_for_create_mode():
    run_profile = RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                provider="virtualbrowser",
                env_type=EnvType.VIRTUAL_BROWSER,
                wait_timeout=60,
                creation=CreationConfig(
                    lifecycle=CreationLifecycle.PERSISTENT,
                    params={"virtualbrowser": {"chrome_version": 145}},
                ),
            ),
        ),
        execution=ExecutionContext(
            module="demo_module",
            workflow="repair",
        ),
    )

    loaded = RunProfile.from_yaml(run_profile.to_yaml())

    assert loaded == run_profile


def test_run_profile_rejects_unknown_fields():
    invalid_yaml = """
resource:
  acquisition:
    mode: select
    candidates: ready_accounts
execution:
  module: demo_module
  workflow: repair
unknown_extra_field: demo
"""

    with pytest.raises(Exception):
        RunProfile.from_yaml(invalid_yaml)


def test_run_profile_rejects_removed_retry_field():
    invalid_yaml = """
resource:
  acquisition:
    mode: select
    candidates: ready_accounts
execution:
  module: demo_module
  workflow: repair
retry:
  max_attempts: 2
"""

    with pytest.raises(Exception):
        RunProfile.from_yaml(invalid_yaml)


def test_run_profile_rejects_removed_match_selector_fields():
    invalid_yaml = """
resource:
  acquisition:
    mode: match
    selector:
      wait_timeout: 60
execution:
  module: demo_module
  workflow: repair
"""

    with pytest.raises(Exception):
        RunProfile.from_yaml(invalid_yaml)


def test_select_mode_requires_candidates_or_env_id():
    with pytest.raises(ValueError, match="candidates or env_id"):
        AcquisitionConfig(
            mode=AcquisitionMode.SELECT,
            candidates="",
        )


def test_select_mode_rejects_removed_selector_name():
    with pytest.raises(ValueError, match="selector_name"):
        AcquisitionConfig(
            mode=AcquisitionMode.SELECT,
            candidates="ready_accounts",
            selector_name="random_ready",
        )


def test_select_mode_rejects_removed_resource_pool():
    with pytest.raises(ValueError, match="resource_pool"):
        AcquisitionConfig(
            mode=AcquisitionMode.SELECT,
            resource_pool="bound_account_ready",
        )


def test_select_mode_accepts_fixed_env_id():
    config = AcquisitionConfig(
        mode=AcquisitionMode.SELECT,
        env_id=12,
    )

    assert config.env_id == 12

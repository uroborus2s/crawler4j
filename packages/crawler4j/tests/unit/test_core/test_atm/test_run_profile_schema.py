import pytest

from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    ExecutionContext,
    MatchConfig,
    ResourceConfig,
    RunProfile,
)


def test_run_profile_serialization_roundtrip():
    run_profile = RunProfile(
        resource=ResourceConfig(
            provider="virtualbrowser",
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.MATCH,
                selector=MatchConfig(wait_timeout=120),
            ),
        ),
        execution=ExecutionContext(
            module="demo_module",
            workflow="repair",
            hooks_module="demo_module.hooks",
            params={"city": "Shanghai"},
            timeout=300,
        ),
    )

    loaded = RunProfile.from_yaml(run_profile.to_yaml())

    assert loaded == run_profile


def test_run_profile_rejects_unknown_fields():
    invalid_yaml = """
resource:
  provider: virtualbrowser
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
  provider: virtualbrowser
execution:
  module: demo_module
  workflow: repair
retry:
  max_attempts: 2
"""

    with pytest.raises(Exception):
        RunProfile.from_yaml(invalid_yaml)

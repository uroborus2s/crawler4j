import pytest

from src.core.tsm.models import (
    AcquisitionMode,
    CreationLifecycle,
    EnvType,
    ExecutionContext,
    ResourceConfig,
    TaskStrategy,
)


def test_strategy_uses_resource_schema_only():
    strategy = TaskStrategy(
        id="resource-only",
        name="resource-only",
        resource=ResourceConfig(
            provider="virtualbrowser",
            acquisition={
                "mode": AcquisitionMode.CREATE,
                "selector": {
                    "env_type": EnvType.VIRTUAL_BROWSER,
                    "tags": {"region": "cn"},
                    "wait_timeout": 90,
                },
                "creation": {
                    "lifecycle": CreationLifecycle.PERSISTENT,
                    "params": {"fingerprint": {"randomize_all": True}},
                },
            },
        ),
    )

    yaml_text = strategy.to_yaml()
    assert "resource:" in yaml_text
    assert "scaling:" not in yaml_text


def test_strategy_yaml_roundtrip_for_hooks_module():
    strategy = TaskStrategy(
        id="hooks-roundtrip",
        name="hooks-roundtrip",
        resource=ResourceConfig(
            provider="virtualbrowser",
            acquisition={"selector": {"env_type": EnvType.VIRTUAL_BROWSER}},
        ),
        execution=ExecutionContext(
            module="ctrip",
            workflow="labor_workflow",
            hooks_module="ctrip.tasks.claim_task",
            timeout=300,
        ),
    )

    loaded = TaskStrategy.from_yaml(strategy.to_yaml())
    assert loaded.execution is not None
    assert loaded.execution.module == "ctrip"
    assert loaded.execution.hooks_module == "ctrip.tasks.claim_task"


def test_unknown_top_level_fields_are_rejected():
    invalid_yaml = """
id: invalid
name: invalid
bad_field:
  enabled: true
"""
    with pytest.raises(Exception):
        TaskStrategy.from_yaml(invalid_yaml)


def test_hybrid_acquisition_mode_is_rejected():
    invalid_yaml = """
id: invalid-hybrid
name: invalid-hybrid
resource:
  provider: virtualbrowser
  acquisition:
    mode: hybrid
"""
    with pytest.raises(Exception):
        TaskStrategy.from_yaml(invalid_yaml)

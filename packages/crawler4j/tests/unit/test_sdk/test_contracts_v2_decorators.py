"""core-native-v2 decorator contract tests."""

from __future__ import annotations

from typing import Annotated

import pytest

from crawler4j_contracts import (
    CRAWLER4J_META_ATTR,
    HOST_RESERVED_DATA_FIELDS,
    Crawler4jMeta,
    DataTableIndexSpec,
    InjectSpec,
    ParameterOptionSpec,
    ParameterSpec,
    component,
    data_query,
    data_table,
    interface,
    object_inject,
    object_param,
    page_action,
    workflow,
)


def test_v2_decorators_attach_metadata_without_instantiating_business_objects():
    instantiated = {"component": 0, "workflow": 0}

    @interface(name="labor", label="Labor capability")
    class Labor:
        pass

    @component(
        name="api_labor",
        label="API labor",
        implements="labor",
        parameters=[
            {"name": "base_url", "type": "string", "required": True},
            ParameterSpec(name="timeout", type="integer", default=30),
        ],
    )
    class ApiLabor:
        def __init__(self, base_url: str, timeout: int = 30):
            instantiated["component"] += 1
            self.base_url = base_url
            self.timeout = timeout

    @workflow(
        name="quiz_workflow",
        label="Quiz workflow",
        inject=[{"name": "labor", "type": "interface", "target": "labor"}],
    )
    class QuizWorkflow:
        def __init__(self, labor: Labor):
            instantiated["workflow"] += 1
            self.labor = labor

    @page_action(name="open_login_page", label="Open login page")
    async def open_login_page(ctx, url: str):
        return {"url": url}

    assert instantiated == {"component": 0, "workflow": 0}
    assert getattr(Labor, CRAWLER4J_META_ATTR) == Crawler4jMeta(
        kind="interface",
        name="labor",
        label="Labor capability",
    )
    assert getattr(ApiLabor, CRAWLER4J_META_ATTR) == Crawler4jMeta(
        kind="component",
        name="api_labor",
        label="API labor",
        implements="labor",
        parameters=(
            ParameterSpec(name="base_url", type="string", required=True),
            ParameterSpec(name="timeout", type="integer", default=30),
        ),
    )
    assert getattr(QuizWorkflow, CRAWLER4J_META_ATTR) == Crawler4jMeta(
        kind="workflow",
        name="quiz_workflow",
        label="Quiz workflow",
        inject=(InjectSpec(name="labor", type="interface", target="labor"),),
    )
    assert getattr(open_login_page, CRAWLER4J_META_ATTR).kind == "page_action"


def test_data_table_and_query_metadata_express_schema_indexes_and_output_schema():
    table_schema = [{"name": "account_id", "type": "string", "required": True}]

    @data_table(
        name="accounts",
        label="Accounts",
        schema=table_schema,
        indexes=[
            {"name": "by_account", "fields": ["account_id"], "unique": True},
            DataTableIndexSpec(fields=("status",)),
        ],
    )
    class AccountsTable:
        pass

    @data_query(
        name="ready_accounts",
        source="accounts",
        sql="SELECT account_id FROM {{resource:accounts}}",
        output_schema=[{"name": "account_id", "type": "string"}],
    )
    def ready_accounts():
        pass

    assert getattr(AccountsTable, CRAWLER4J_META_ATTR).indexes == (
        DataTableIndexSpec(name="by_account", fields=("account_id",), unique=True),
        DataTableIndexSpec(fields=("status",)),
    )
    assert getattr(ready_accounts, CRAWLER4J_META_ATTR).source == "accounts"


def test_parameter_and_inject_specs_normalize_supported_shapes():
    @component(
        name="api_labor",
        implements="labor",
        inject=[InjectSpec(name="client", type="object", target="http_client")],
        parameters=[
            {
                "name": "mode",
                "type": "enum",
                "options": [{"label": "Fast", "value": "fast"}, "safe"],
            },
        ],
    )
    class ApiLabor:
        pass

    meta = getattr(ApiLabor, CRAWLER4J_META_ATTR)
    assert meta.inject == (InjectSpec(name="client", type="object", target="http_client"),)
    assert meta.parameters == (
        ParameterSpec(
            name="mode",
            type="enum",
            options=(
                ParameterOptionSpec(label="Fast", value="fast"),
                ParameterOptionSpec(label="safe", value="safe"),
            ),
        ),
    )


def test_component_and_workflow_merge_class_and_init_annotation_metadata():
    @interface(name="labor")
    class Labor:
        pass

    @component(name="api_labor", implements="labor")
    class ApiLabor:
        client: Annotated[object, object_inject(type="object", target="http_client")]
        region: Annotated[str, object_param(default="cn")]

        def __init__(
            self,
            base_url: Annotated[str, object_param(label="Base URL")],
            timeout: Annotated[int, object_param(min=1, max=120)] = 30,
        ) -> None:
            self.base_url = base_url
            self.timeout = timeout

    @workflow(name="quiz_workflow")
    class QuizWorkflow:
        def __init__(
            self,
            labor: Annotated[Labor, object_inject(type="interface", target="labor")],
        ) -> None:
            self.labor = labor

    component_meta = getattr(ApiLabor, CRAWLER4J_META_ATTR)
    assert component_meta.inject == (InjectSpec(name="client", type="object", target="http_client"),)
    assert component_meta.parameters == (
        ParameterSpec(name="region", type="string", default="cn"),
        ParameterSpec(name="base_url", type="string", label="Base URL", required=True),
        ParameterSpec(name="timeout", type="integer", default=30, min=1, max=120),
    )
    assert getattr(QuizWorkflow, CRAWLER4J_META_ATTR).inject == (
        InjectSpec(name="labor", type="interface", target="labor"),
    )


def test_host_reserved_data_fields_are_exported_for_sdk_and_core_validation():
    assert {"created_at", "updated_at", "create_at", "update_at"} <= HOST_RESERVED_DATA_FIELDS


def test_v2_metadata_validation_rejects_unsupported_shapes():
    with pytest.raises(ValueError, match="kind"):
        Crawler4jMeta(kind="task", name="legacy")
    with pytest.raises(ValueError, match="implements"):
        component(name="api_labor", implements="")
    with pytest.raises(ValueError, match="enum"):
        component(name="api_labor", implements="labor", parameters=[{"name": "mode", "type": "enum"}])
    with pytest.raises(ValueError, match="workflow.*parameters"):
        workflow(name="quiz_workflow", parameters=[{"name": "legacy", "type": "string"}])
    with pytest.raises(ValueError, match="schema"):
        data_table(name="accounts", schema=["account_id"])

"""core-native-v2 decorator contract tests."""

from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from typing import Annotated, Literal

import pytest

from crawler4j_contracts import (
    CRAWLER4J_META_ATTR,
    EnvCandidates,
    HOST_RESERVED_DATA_FIELDS,
    MANAGED_DATASET_RESERVED_DATA_FIELDS,
    Crawler4jMeta,
    DataTableIndexSpec,
    InjectSpec,
    ParameterOptionSpec,
    ParameterSpec,
    component,
    data_table,
    data_view,
    env_cleanup_candidates,
    env_candidates,
    interface,
    object_inject,
    object_param,
    page,
    page_action,
    ui_action,
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

    @ui_action(name="create_account_from_ui", label="Create account")
    def create_account_from_ui(ctx, payload: dict):
        return {"payload": payload}

    @page(
        name="dashboard",
        label="Dashboard",
        icon="chart",
        schema={"type": "Page", "title": "Dashboard", "children": []},
    )
    def load_dashboard_page(ctx, page_id: str, params: dict | None = None):
        return {"page_id": page_id}

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
    assert getattr(create_account_from_ui, CRAWLER4J_META_ATTR) == Crawler4jMeta(
        kind="ui_action",
        name="create_account_from_ui",
        label="Create account",
    )
    assert getattr(load_dashboard_page, CRAWLER4J_META_ATTR) == Crawler4jMeta(
        kind="page",
        name="dashboard",
        label="Dashboard",
        icon="chart",
        menu=True,
        page_schema={"type": "Page", "title": "Dashboard", "children": []},
    )


def test_data_table_and_view_metadata_express_schema_indexes_and_view_schema():
    table_schema = [
        {"name": "env_id", "type": "integer", "required": True},
        {"name": "account_id", "type": "string", "required": True},
    ]

    @data_table(
        name="accounts",
        label="Accounts",
        storage_mode="managed_dataset",
        cleanup_policy="keep",
        env_binding_field="env_id",
        schema=table_schema,
        indexes=[
            {"name": "by_account", "fields": ["account_id"], "unique": True},
            DataTableIndexSpec(fields=("status",)),
        ],
    )
    class AccountsTable:
        pass

    @data_view(
        name="account_overview",
        sources=["accounts"],
        sql="SELECT account_id FROM {{resource:accounts}}",
        schema=[{"name": "account_id", "type": "string"}],
    )
    def account_overview():
        pass

    assert getattr(AccountsTable, CRAWLER4J_META_ATTR).indexes == (
        DataTableIndexSpec(name="by_account", fields=("account_id",), unique=True),
        DataTableIndexSpec(fields=("status",)),
    )
    assert getattr(AccountsTable, CRAWLER4J_META_ATTR).storage_mode == "managed_dataset"
    assert getattr(AccountsTable, CRAWLER4J_META_ATTR).cleanup_policy == "keep"
    assert getattr(AccountsTable, CRAWLER4J_META_ATTR).env_binding_field == "env_id"
    assert getattr(account_overview, CRAWLER4J_META_ATTR).sources == ("accounts",)
    assert getattr(account_overview, CRAWLER4J_META_ATTR).cleanup_policy == "drop_view"


def test_data_table_custom_table_supports_auto_increment_record_key_schema():
    @data_table(
        name="accounts",
        record_key_field="id",
        schema=[
            {"name": "id", "type": "integer", "auto_increment": True},
            {"name": "account_id", "type": "string"},
        ],
    )
    class AccountsTable:
        pass

    meta = getattr(AccountsTable, CRAWLER4J_META_ATTR)
    assert meta.storage_mode == "custom_table"
    assert meta.schema[0] == {"name": "id", "type": "integer", "auto_increment": True}


def test_data_table_rejects_invalid_auto_increment_schema():
    with pytest.raises(ValueError, match="auto_increment.*record_key_field"):

        @data_table(
            name="accounts",
            record_key_field="account_id",
            schema=[
                {"name": "id", "type": "integer", "auto_increment": True},
                {"name": "account_id", "type": "string"},
            ],
        )
        class InvalidNonKeyAutoIncrement:
            pass

    with pytest.raises(ValueError, match="auto_increment.*integer"):

        @data_table(
            name="accounts",
            record_key_field="id",
            schema=[
                {"name": "id", "type": "string", "auto_increment": True},
            ],
        )
        class InvalidTextAutoIncrement:
            pass

    with pytest.raises(ValueError, match="auto_increment.*custom_table"):

        @data_table(
            name="accounts",
            storage_mode="managed_dataset",
            record_key_field="id",
            schema=[
                {"name": "id", "type": "integer", "auto_increment": True},
            ],
        )
        class InvalidManagedAutoIncrement:
            pass

    with pytest.raises(ValueError, match="data_view.*auto_increment"):

        @data_view(
            name="account_overview",
            sources=["accounts"],
            sql="SELECT id FROM {{resource:accounts}}",
            schema=[{"name": "id", "type": "integer", "auto_increment": True}],
        )
        def invalid_view():
            pass


def test_env_candidates_metadata_and_query_chain():
    @env_candidates(name="ctrip_gold_old_account", label="携程高等级老账号")
    def ctrip_gold_old_account(params):
        return (
            EnvCandidates.from_table("ctrip_accounts")
            .filter(status="ready")
            .intersect(EnvCandidates.from_table("ctrip_accounts").filter(member_level__in=["gold", "platinum"]))
            .exclude(EnvCandidates.from_table("ctrip_accounts").filter(status="blacklisted"))
            .order_by("last_used_at", "-registered_at")
            .limit(params.get("limit", 100))
        )

    meta = getattr(ctrip_gold_old_account, CRAWLER4J_META_ATTR)
    assert meta == Crawler4jMeta(
        kind="env_candidates",
        name="ctrip_gold_old_account",
        label="携程高等级老账号",
    )

    query = ctrip_gold_old_account({"limit": 20})
    assert query.to_plan() == {
        "kind": "env_candidates",
        "op": "minus",
        "source": "ctrip_accounts",
        "env_field": "env_id",
        "left": {
            "kind": "env_candidates",
            "op": "intersect",
            "source": "ctrip_accounts",
            "env_field": "env_id",
            "left": {
                "kind": "env_candidates",
                "op": "select",
                "source": "ctrip_accounts",
                "env_field": "env_id",
                "where": [{"field": "status", "op": "eq", "value": "ready"}],
                "order_by": [],
                "limit": None,
            },
            "right": {
                "kind": "env_candidates",
                "op": "select",
                "source": "ctrip_accounts",
                "env_field": "env_id",
                "where": [{"field": "member_level", "op": "in", "value": ["gold", "platinum"]}],
                "order_by": [],
                "limit": None,
            },
            "order_by": [],
            "limit": None,
        },
        "right": {
            "kind": "env_candidates",
            "op": "select",
            "source": "ctrip_accounts",
            "env_field": "env_id",
            "where": [{"field": "status", "op": "eq", "value": "blacklisted"}],
            "order_by": [],
            "limit": None,
        },
        "order_by": [
            {"field": "last_used_at", "direction": "asc"},
            {"field": "registered_at", "direction": "desc"},
        ],
        "limit": 20,
    }


def test_env_cleanup_candidates_metadata_reuses_env_candidates_query_chain():
    @env_cleanup_candidates(name="unused_accounts", label="长期未用账号环境")
    def unused_accounts(params):
        return (
            EnvCandidates.from_table("accounts")
            .filter(status="unused")
            .order_by("last_used_at")
            .limit(params.get("limit", 50))
        )

    meta = getattr(unused_accounts, CRAWLER4J_META_ATTR)
    assert meta == Crawler4jMeta(
        kind="env_cleanup_candidates",
        name="unused_accounts",
        label="长期未用账号环境",
    )

    assert unused_accounts({"limit": 10}).to_plan() == {
        "kind": "env_candidates",
        "op": "select",
        "source": "accounts",
        "env_field": "env_id",
        "where": [{"field": "status", "op": "eq", "value": "unused"}],
        "order_by": [{"field": "last_used_at", "direction": "asc"}],
        "limit": 10,
    }


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


def test_object_param_annotation_infers_extended_builtin_types():
    @component(name="api_labor", implements="labor")
    class ApiLabor:
        start_date: Annotated[date, object_param()]
        mode: Annotated[Literal["sync", "async"], object_param(default="sync")]
        tags: Annotated[list[str], object_param(default=["default"])]
        limits: Annotated[dict[str, int], object_param(default={"daily": 10})]
        download_dir: Annotated[Path, object_param()]
        optional_count: Annotated[int | None, object_param()]

        def __init__(
            self,
            deadline: Annotated[datetime, object_param()],
            run_at: Annotated[time, object_param()],
        ) -> None:
            self.deadline = deadline
            self.run_at = run_at

    parameters = {item.name: item for item in getattr(ApiLabor, CRAWLER4J_META_ATTR).parameters}

    assert parameters["start_date"].type == "date"
    assert parameters["start_date"].required is True
    assert parameters["deadline"].type == "datetime"
    assert parameters["run_at"].type == "time"
    assert parameters["download_dir"].type == "path"
    assert parameters["tags"].type == "array"
    assert parameters["tags"].item_schema == {"type": "string"}
    assert parameters["limits"].type == "object"
    assert parameters["limits"].schema == {"additional_type": "integer"}
    assert parameters["optional_count"].type == "integer"
    assert parameters["optional_count"].required is False
    assert parameters["mode"].type == "enum"
    assert [(item.label, item.value) for item in parameters["mode"].options] == [
        ("sync", "sync"),
        ("async", "async"),
    ]


def test_host_reserved_data_fields_are_exported_for_sdk_and_core_validation():
    assert {"created_at", "updated_at", "create_at", "update_at"} <= HOST_RESERVED_DATA_FIELDS
    assert {
        "created_at",
        "updated_at",
        "create_at",
        "update_at",
        "record_index",
        "record_key",
        "run_status",
        "record_status",
    } <= MANAGED_DATASET_RESERVED_DATA_FIELDS


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
    with pytest.raises(ValueError, match="env_binding_field must exist"):
        data_table(name="accounts", env_binding_field="env_id", schema=[{"name": "account_id", "type": "string"}])
    with pytest.raises(ValueError, match="env_binding_field must be integer"):
        data_table(name="accounts", env_binding_field="env_id", schema=[{"name": "env_id", "type": "string"}])

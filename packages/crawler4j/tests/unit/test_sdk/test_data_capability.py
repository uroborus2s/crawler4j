"""SDK 数据能力契约测试。"""

from __future__ import annotations

from typing import Any

import crawler4j_sdk
import pytest
from crawler4j_contracts import DatabaseExecutor, TaskContext, ToolSpec, ToolsCapability


class _FakeTools:
    def __init__(self, available_tools: set[str] | None = None):
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.available_tools = available_tools or {
            "captcha.match_slider",
            "env.set_proxy",
        }

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self.available_tools

    def list_tools(self) -> list[ToolSpec]:
        specs = [
            ToolSpec(name="captcha.match_slider", description="识别滑块验证码缺口位置"),
            ToolSpec(name="env.set_proxy", description="为当前环境设置代理", is_async=True),
        ]
        return [spec for spec in specs if spec.name in self.available_tools]

    def call(self, tool_name: str, /, **kwargs):
        self.calls.append((tool_name, kwargs))
        return {"tool_name": tool_name, "kwargs": kwargs}


class _FakeDbExecutor:
    def __init__(self):
        self.described: list[str] = []
        self.plans: list[dict[str, Any]] = []

    def describe_source(self, source: str) -> dict[str, Any]:
        self.described.append(source)
        return {
            "source": source,
            "source_kind": "relation",
            "storage_mode": "custom_table",
            "record_key_field": "account_id",
            "columns": [
                {"name": "account_id", "type": "text"},
                {"name": "amount", "type": "number"},
                {"name": "status", "type": "text"},
            ],
            "joins": [
                {
                    "target": "account_profiles",
                    "types": ["inner", "left"],
                    "on": [{"left": "account_id", "right": "account_id"}],
                }
            ],
        }

    def execute_plan(self, plan: dict[str, Any]) -> Any:
        self.plans.append(plan)
        return [{"account_id": "A001", "total_amount": 10.5}]


def test_sdk_exports_expected_stable_surface():
    fake_tools = _FakeTools()
    expected_exports = {
        "get_version",
        "get_compatible_dependency_spec",
        "get_compatible_sdk_dependency_spec",
        "get_compatible_contracts_dependency_spec",
    }

    assert isinstance(fake_tools, ToolsCapability)
    assert set(crawler4j_sdk.__all__) == expected_exports

    ctx = TaskContext(env_id=1, task_name="demo", tools=fake_tools)
    assert ctx.tools is fake_tools
    assert not any(spec.name.startswith("db.") for spec in fake_tools.list_tools())


def test_task_context_db_fluent_api_builds_select_query_plan():
    executor = _FakeDbExecutor()
    assert isinstance(executor, DatabaseExecutor)
    ctx = TaskContext(env_id=1, task_name="demo", db=TaskContext(0, "inner").db.bind(executor))

    rows = (
        ctx.db.from_("billing_entries")
        .join("account_profiles", on={"account_id": "account_id"}, how="left")
        .where(["status", "=", "done"])
        .where(["or", ["account_id", "=", "A001"], ["account_id", "=", "A002"]])
        .group_by("account_id")
        .sum("amount", alias="total_amount")
        .count(alias="total_count")
        .order_by("total_amount", "desc")
        .limit(20)
        .execute()
    )

    assert rows == [{"account_id": "A001", "total_amount": 10.5}]
    assert executor.described == ["billing_entries"]
    assert executor.plans == [
        {
            "kind": "select",
            "base": {"source": "billing_entries"},
            "joins": [
                {
                    "target": "account_profiles",
                    "type": "left",
                    "on": [{"left": "account_id", "right": "account_id"}],
                }
            ],
            "select": [
                {"kind": "aggregate", "func": "sum", "field": "amount", "alias": "total_amount"},
                {"kind": "aggregate", "func": "count", "field": "*", "alias": "total_count"},
            ],
            "where": [
                {"field": "status", "op": "eq", "value": "done"},
                {
                    "kind": "group",
                    "operator": "or",
                    "conditions": [
                        {"field": "account_id", "op": "eq", "value": "A001"},
                        {"field": "account_id", "op": "eq", "value": "A002"},
                    ],
                },
            ],
            "group_by": ["account_id"],
            "order_by": [{"field": "total_amount", "direction": "desc"}],
            "limit": 20,
            "offset": 0,
        }
    ]


def test_task_context_db_describe_returns_host_descriptor():
    executor = _FakeDbExecutor()
    ctx = TaskContext(env_id=1, task_name="demo", db=TaskContext(0, "inner").db.bind(executor))

    descriptor = ctx.db.describe("billing_entries")

    assert descriptor["source"] == "billing_entries"
    assert descriptor["source_kind"] == "relation"
    assert descriptor["columns"][0] == {"name": "account_id", "type": "text"}
    assert executor.described == ["billing_entries"]
    assert executor.plans == []


@pytest.mark.parametrize(
    ("method_name", "expected_alias"),
    [
        ("sum", "sum_amount"),
        ("avg", "avg_amount"),
        ("min", "min_amount"),
        ("max", "max_amount"),
    ],
)
def test_task_context_db_aggregate_uses_default_alias(method_name, expected_alias):
    executor = _FakeDbExecutor()
    ctx = TaskContext(env_id=1, task_name="demo", db=TaskContext(0, "inner").db.bind(executor))

    getattr(ctx.db.from_("billing_entries"), method_name)("amount").execute()

    assert executor.plans[0]["select"] == [
        {"kind": "aggregate", "func": method_name, "field": "amount", "alias": expected_alias}
    ]


def test_task_context_db_select_accepts_field_array_and_nested_where_plan():
    executor = _FakeDbExecutor()
    ctx = TaskContext(env_id=1, task_name="demo", db=TaskContext(0, "inner").db.bind(executor))

    ctx.db.from_("billing_entries").select(["account_id", "status"]).where(
        ["and", ["amount", ">", 10], ["or", ["status", "=", "ready"], ["status", "=", "pending"]]]
    ).execute()

    assert executor.plans[0]["select"] == [
        {"kind": "column", "field": "account_id"},
        {"kind": "column", "field": "status"},
    ]
    assert executor.plans[0]["where"] == [
        {"field": "amount", "op": "gt", "value": 10},
        {
            "kind": "group",
            "operator": "or",
            "conditions": [
                {"field": "status", "op": "eq", "value": "ready"},
                {"field": "status", "op": "eq", "value": "pending"},
            ],
        },
    ]


def test_task_context_db_supports_view_select_and_replace_plan():
    executor = _FakeDbExecutor()
    ctx = TaskContext(env_id=1, task_name="demo", db=TaskContext(0, "inner").db.bind(executor))

    ctx.db.from_("account_overview").select(["account_id"]).where(["status", "=", "ready"]).execute()
    ctx.db.into("accounts").replace([{"account_id": "A001", "status": "ready"}])

    assert executor.plans == [
        {
            "kind": "select",
            "base": {"source": "account_overview"},
            "joins": [],
            "select": [{"kind": "column", "field": "account_id"}],
            "where": [{"field": "status", "op": "eq", "value": "ready"}],
            "group_by": [],
            "order_by": [],
            "limit": None,
            "offset": 0,
        },
        {
            "kind": "replace_records",
            "resource": "accounts",
            "records": [{"account_id": "A001", "status": "ready"}],
        },
    ]


def test_task_context_db_supports_concurrency_safe_write_plans():
    executor = _FakeDbExecutor()
    ctx = TaskContext(env_id=1, task_name="demo", db=TaskContext(0, "inner").db.bind(executor))

    ctx.db.into("accounts").add([{"status": "new"}])
    ctx.db.into("accounts").upsert([{"account_id": "A001", "status": "ready"}])
    ctx.db.into("accounts").update_where({"status": "used"}, where=["account_id", "=", "A001"])
    ctx.db.into("accounts").delete_where(where=["status", "=", "expired"])

    assert executor.plans == [
        {
            "kind": "add_records",
            "resource": "accounts",
            "records": [{"status": "new"}],
        },
        {
            "kind": "upsert_records",
            "resource": "accounts",
            "records": [{"account_id": "A001", "status": "ready"}],
        },
        {
            "kind": "update_records",
            "resource": "accounts",
            "fields": {"status": "used"},
            "where": [{"field": "account_id", "op": "eq", "value": "A001"}],
        },
        {
            "kind": "delete_records",
            "resource": "accounts",
            "where": [{"field": "status", "op": "eq", "value": "expired"}],
        },
    ]


def test_task_context_db_writer_where_accepts_query_builder_callable():
    executor = _FakeDbExecutor()
    ctx = TaskContext(env_id=1, task_name="demo", db=TaskContext(0, "inner").db.bind(executor))

    ctx.db.into("accounts").update_where(
        {"status": "used"},
        where=lambda query: query.where("account_id", "=", "A001"),
    )
    ctx.db.into("accounts").delete_where(
        where=lambda query: query.where(["or", ["status", "=", "expired"], ["amount", ">", 100]]),
    )

    assert executor.described == []
    assert executor.plans == [
        {
            "kind": "update_records",
            "resource": "accounts",
            "fields": {"status": "used"},
            "where": [{"field": "account_id", "op": "eq", "value": "A001"}],
        },
        {
            "kind": "delete_records",
            "resource": "accounts",
            "where": [
                {
                    "kind": "group",
                    "operator": "or",
                    "conditions": [
                        {"field": "status", "op": "eq", "value": "expired"},
                        {"field": "amount", "op": "gt", "value": 100},
                    ],
                }
            ],
        },
    ]


def test_task_context_db_writer_where_callable_must_add_conditions():
    executor = _FakeDbExecutor()
    ctx = TaskContext(env_id=1, task_name="demo", db=TaskContext(0, "inner").db.bind(executor))

    with pytest.raises(ValueError, match="where callable must add at least one condition"):
        ctx.db.into("accounts").delete_where(where=lambda query: query)


def test_task_context_db_delete_where_accepts_record_key_value():
    executor = _FakeDbExecutor()
    ctx = TaskContext(env_id=1, task_name="demo", db=TaskContext(0, "inner").db.bind(executor))

    ctx.db.into("accounts").delete_where(where="A001")
    ctx.db.batch().delete_where("accounts", where="A002").execute()

    assert executor.described == ["accounts", "accounts"]
    assert executor.plans == [
        {
            "kind": "delete_records",
            "resource": "accounts",
            "where": [{"field": "account_id", "op": "eq", "value": "A001"}],
        },
        {
            "kind": "batch",
            "operations": [
                {
                    "kind": "delete_records",
                    "resource": "accounts",
                    "where": [{"field": "account_id", "op": "eq", "value": "A002"}],
                }
            ],
        },
    ]


def test_task_context_db_supports_batch_write_plan():
    executor = _FakeDbExecutor()
    ctx = TaskContext(env_id=1, task_name="demo", db=TaskContext(0, "inner").db.bind(executor))

    ctx.db.batch().add("accounts", [{"status": "new"}]).upsert(
        "accounts",
        [{"account_id": "A001", "status": "ready"}],
    ).update_where(
        "accounts",
        {"status": "used"},
        where=lambda query: query.where("account_id", "=", "A001"),
    ).delete_where(
        "accounts",
        where=["status", "=", "expired"],
    ).audit(
        "account_events",
        {"entity_key": "A001", "event_type": "status_changed"},
    ).execute()

    assert executor.plans == [
        {
            "kind": "batch",
            "operations": [
                {
                    "kind": "add_records",
                    "resource": "accounts",
                    "records": [{"status": "new"}],
                },
                {
                    "kind": "upsert_records",
                    "resource": "accounts",
                    "records": [{"account_id": "A001", "status": "ready"}],
                },
                {
                    "kind": "update_records",
                    "resource": "accounts",
                    "fields": {"status": "used"},
                    "where": [{"field": "account_id", "op": "eq", "value": "A001"}],
                },
                {
                    "kind": "delete_records",
                    "resource": "accounts",
                    "where": [{"field": "status", "op": "eq", "value": "expired"}],
                },
                {
                    "kind": "append_audit_event",
                    "dataset": "account_events",
                    "event": {"entity_key": "A001", "event_type": "status_changed"},
                },
            ],
        }
    ]


def test_task_context_db_supports_audit_event_plan():
    executor = _FakeDbExecutor()
    ctx = TaskContext(env_id=1, task_name="demo", db=TaskContext(0, "inner").db.bind(executor))

    ctx.db.audit("account_events").append(
        entity_key="13800138000",
        event_type="status_changed",
        previous_status="active",
        next_status="blocked",
        result="success",
        reason="risk_control",
        payload={"operator": "system"},
    )
    ctx.db.audit("account_events").query(
        entity_key="13800138000",
        event_type="status_changed",
        run_id="run-1",
        start_at=100,
        end_at=200,
        limit=20,
        order="asc",
    )

    assert executor.plans == [
        {
            "kind": "append_audit_event",
            "dataset": "account_events",
            "event": {
                "entity_key": "13800138000",
                "event_type": "status_changed",
                "previous_status": "active",
                "next_status": "blocked",
                "result": "success",
                "reason": "risk_control",
                "payload": {"operator": "system"},
            },
        },
        {
            "kind": "query_audit_events",
            "dataset": "account_events",
            "entity_key": "13800138000",
            "event_type": "status_changed",
            "run_id": "run-1",
            "start_at": 100,
            "end_at": 200,
            "limit": 20,
            "offset": 0,
            "order": "asc",
        },
    ]

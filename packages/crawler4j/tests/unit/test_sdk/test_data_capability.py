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
        .where("status", "eq", "done")
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
            "where": [{"field": "status", "op": "eq", "value": "done"}],
            "group_by": ["account_id"],
            "order_by": [{"field": "total_amount", "direction": "desc"}],
            "limit": 20,
            "offset": 0,
        }
    ]


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


def test_task_context_db_supports_named_query_and_replace_plan():
    executor = _FakeDbExecutor()
    ctx = TaskContext(env_id=1, task_name="demo", db=TaskContext(0, "inner").db.bind(executor))

    ctx.db.named("top_accounts").bind(start_date="2026-04-01").execute()
    ctx.db.into("accounts").replace([{"account_id": "A001", "status": "ready"}])

    assert executor.plans == [
        {
            "kind": "named_query",
            "query_id": "top_accounts",
            "params": {"start_date": "2026-04-01"},
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

    ctx.db.into("accounts").upsert([{"account_id": "A001", "status": "ready"}])
    ctx.db.into("accounts").update_where({"status": "used"}, where={"account_id": "A001"})
    ctx.db.into("accounts").delete_where("status", "eq", "expired")

    assert executor.plans == [
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


def test_task_context_db_supports_batch_write_plan():
    executor = _FakeDbExecutor()
    ctx = TaskContext(env_id=1, task_name="demo", db=TaskContext(0, "inner").db.bind(executor))

    ctx.db.batch().upsert("accounts", [{"account_id": "A001", "status": "ready"}]).audit(
        "account_events",
        {"entity_key": "A001", "event_type": "status_changed"},
    ).execute()

    assert executor.plans == [
        {
            "kind": "batch",
            "operations": [
                {
                    "kind": "upsert_records",
                    "resource": "accounts",
                    "records": [{"account_id": "A001", "status": "ready"}],
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

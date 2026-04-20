"""SDK tools 导出与契约测试。"""

import crawler4j_sdk
import pytest
from crawler4j_sdk import TaskContext, ToolSpec, ToolsCapability


class _FakeTools:
    def __init__(self, available_tools: set[str] | None = None):
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.available_tools = available_tools or {
            "db.list_records",
            "db.append_event",
            "db.query_events",
            "captcha.match_slider",
            "env.set_proxy",
            "env.bind_resource_pool",
            "env.mark_resource_pool_eligible",
            "env.mark_resource_pool_ineligible",
            "env.remove_resource_pool",
            "env.replace_resource_pool_snapshot",
        }

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in self.available_tools

    def list_tools(self) -> list[ToolSpec]:
        specs = [
            ToolSpec(name="captcha.match_slider", description="识别滑块验证码缺口位置"),
            ToolSpec(name="db.append_event", description="追加模块审计事件"),
            ToolSpec(name="db.list_records", description="读取模块数据集"),
            ToolSpec(name="db.query_events", description="查询模块审计事件"),
            ToolSpec(name="env.bind_resource_pool", description="登记环境资源池资格", is_async=True),
            ToolSpec(name="env.mark_resource_pool_eligible", description="标记环境可接单", is_async=True),
            ToolSpec(name="env.mark_resource_pool_ineligible", description="标记环境不可接单", is_async=True),
            ToolSpec(name="env.remove_resource_pool", description="移除环境资源池资格", is_async=True),
            ToolSpec(name="env.replace_resource_pool_snapshot", description="重建环境资源池资格快照", is_async=True),
            ToolSpec(name="env.set_proxy", description="为当前环境设置代理", is_async=True),
        ]
        return [spec for spec in specs if spec.name in self.available_tools]

    def call(self, tool_name: str, /, **kwargs):
        self.calls.append((tool_name, kwargs))
        return {"tool_name": tool_name, "kwargs": kwargs}


def test_sdk_exports_expected_stable_surface():
    fake_tools = _FakeTools()
    expected_exports = {
        "BBox",
        "ClickCaptchaDebugInfo",
        "ClickCaptchaMatchResult",
        "ClickCaptchaOrderedTarget",
        "EnvAction",
        "EnvCandidate",
        "EnvSelectorInfo",
        "ImageInput",
        "ModuleAssembler",
        "Point",
        "SliderCaptchaDebugInfo",
        "SliderCaptchaMatchResult",
        "TaskContext",
        "TaskFlow",
        "TaskResult",
        "TaskSignal",
        "TaskSignalAction",
        "TaskScript",
        "ToolSpec",
        "ToolsCapability",
        "env_selector",
        "bind_resource_pool",
        "mark_resource_pool_eligible",
        "mark_resource_pool_ineligible",
        "remove_resource_pool",
        "replace_resource_pool_snapshot",
    }

    assert isinstance(fake_tools, ToolsCapability)
    assert set(crawler4j_sdk.__all__) == expected_exports

    ctx = TaskContext(env_id=1, task_name="demo", tools=fake_tools)
    assert ctx.tools is fake_tools


def test_tools_capability_calls_core_extensions():
    fake_tools = _FakeTools()

    assert fake_tools.has_tool("db.list_records") is True
    assert fake_tools.has_tool("db.append_event") is True
    specs = fake_tools.list_tools()
    assert [tool.name for tool in specs] == [
        "captcha.match_slider",
        "db.append_event",
        "db.list_records",
        "db.query_events",
        "env.bind_resource_pool",
        "env.mark_resource_pool_eligible",
        "env.mark_resource_pool_ineligible",
        "env.remove_resource_pool",
        "env.replace_resource_pool_snapshot",
        "env.set_proxy",
    ]
    assert {tool.name: tool.is_async for tool in specs} == {
        "captcha.match_slider": False,
        "db.append_event": False,
        "db.list_records": False,
        "db.query_events": False,
        "env.bind_resource_pool": True,
        "env.mark_resource_pool_eligible": True,
        "env.mark_resource_pool_ineligible": True,
        "env.remove_resource_pool": True,
        "env.replace_resource_pool_snapshot": True,
        "env.set_proxy": True,
    }

    ctx = TaskContext(env_id=1, task_name="demo", tools=fake_tools)
    result = ctx.tools.call("db.list_records", dataset="orders")

    assert result == {"tool_name": "db.list_records", "kwargs": {"dataset": "orders"}}
    assert fake_tools.calls == [("db.list_records", {"dataset": "orders"})]


def test_tools_capability_preserves_audit_event_kwargs():
    fake_tools = _FakeTools()
    ctx = TaskContext(env_id=1, task_name="demo", tools=fake_tools)

    append_result = ctx.tools.call(
        "db.append_event",
        dataset="account_events",
        event_type="status_changed",
        entity_key="13800000001",
        previous_status="active",
        next_status="blocked",
        result="failed",
        reason="risk_control",
        payload={"operator": "system"},
        created_at=200,
    )
    query_result = ctx.tools.call(
        "db.query_events",
        dataset="account_events",
        entity_key="13800000001",
        event_type="status_changed",
        run_id="run-001",
        start_at=100,
        end_at=300,
        limit=20,
        offset=5,
        order="desc",
    )

    assert append_result["kwargs"] == {
        "dataset": "account_events",
        "event_type": "status_changed",
        "entity_key": "13800000001",
        "previous_status": "active",
        "next_status": "blocked",
        "result": "failed",
        "reason": "risk_control",
        "payload": {"operator": "system"},
        "created_at": 200,
    }
    assert query_result["kwargs"] == {
        "dataset": "account_events",
        "entity_key": "13800000001",
        "event_type": "status_changed",
        "run_id": "run-001",
        "start_at": 100,
        "end_at": 300,
        "limit": 20,
        "offset": 5,
        "order": "desc",
    }


@pytest.mark.asyncio
async def test_sdk_resource_pool_helpers_route_to_core_env_tools():
    fake_tools = _FakeTools()
    ctx = TaskContext(env_id=11, task_name="demo", tools=fake_tools)

    await crawler4j_sdk.bind_resource_pool(ctx, pool_name="bound_account_ready")
    await crawler4j_sdk.mark_resource_pool_eligible(ctx, pool_name="bound_account_ready")
    await crawler4j_sdk.mark_resource_pool_ineligible(
        ctx,
        pool_name="bound_account_ready",
        reason="blacklisted",
    )
    await crawler4j_sdk.remove_resource_pool(ctx, pool_name="bound_account_ready")
    await crawler4j_sdk.replace_resource_pool_snapshot(
        ctx,
        pool_name="bound_account_ready",
        entries=[{"env_id": 11, "eligible": True}],
    )

    assert fake_tools.calls == [
        (
            "env.bind_resource_pool",
            {
                "env_id": 11,
                "pool_name": "bound_account_ready",
                "eligible": True,
                "reason": "",
                "exclusive": True,
            },
        ),
        (
            "env.mark_resource_pool_eligible",
            {
                "env_id": 11,
                "pool_name": "bound_account_ready",
                "reason": "",
            },
        ),
        (
            "env.mark_resource_pool_ineligible",
            {
                "env_id": 11,
                "pool_name": "bound_account_ready",
                "reason": "blacklisted",
            },
        ),
        (
            "env.remove_resource_pool",
            {
                "env_id": 11,
                "pool_name": "bound_account_ready",
            },
        ),
        (
            "env.replace_resource_pool_snapshot",
            {
                "pool_name": "bound_account_ready",
                "entries": [{"env_id": 11, "eligible": True}],
            },
        ),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper", "tool_name", "kwargs"),
    [
        (
            crawler4j_sdk.bind_resource_pool,
            "env.bind_resource_pool",
            {"pool_name": "bound_account_ready"},
        ),
        (
            crawler4j_sdk.mark_resource_pool_eligible,
            "env.mark_resource_pool_eligible",
            {"pool_name": "bound_account_ready"},
        ),
        (
            crawler4j_sdk.mark_resource_pool_ineligible,
            "env.mark_resource_pool_ineligible",
            {"pool_name": "bound_account_ready", "reason": "blacklisted"},
        ),
        (
            crawler4j_sdk.remove_resource_pool,
            "env.remove_resource_pool",
            {"pool_name": "bound_account_ready"},
        ),
        (
            crawler4j_sdk.replace_resource_pool_snapshot,
            "env.replace_resource_pool_snapshot",
            {"pool_name": "bound_account_ready", "entries": []},
        ),
    ],
)
async def test_sdk_resource_pool_helpers_raise_clear_error_when_capability_missing(
    helper,
    tool_name: str,
    kwargs: dict[str, object],
):
    fake_tools = _FakeTools(
        available_tools={
            "db.list_records",
            "db.append_event",
            "db.query_events",
            "captcha.match_slider",
            "env.set_proxy",
        }
    )
    ctx = TaskContext(env_id=11, task_name="demo", tools=fake_tools)

    with pytest.raises(RuntimeError) as exc_info:
        await helper(ctx, **kwargs)

    message = str(exc_info.value)
    assert tool_name in message
    assert "ctx.tools.has_tool" in message
    assert fake_tools.calls == []

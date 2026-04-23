import sys
from types import SimpleNamespace
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

import src.core.atm.runtime_capabilities as runtime_capabilities
from src.core.atm.runtime_capabilities import (
    ClickCaptchaMatchResult,
    ClickCaptchaOrderedTarget,
    HostedUIDeclarationBuffer,
    RUNTIME_SURFACE_HOSTED_UI_DECLARE,
    RUNTIME_SURFACE_HOSTED_UI_READONLY,
    SliderCaptchaMatchResult,
    build_runtime_capabilities,
)
from src.core.rem.ip_pool import IPEntry, IPPool


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


class _FakeKV:
    def __init__(self):
        self._store: dict[str, object] = {}

    def get(self, key: str):
        return self._store.get(key)

    def set(self, key: str, value, ttl: int | None = None):  # noqa: ARG002
        self._store[key] = value
        return True

    def exists(self, key: str) -> bool:
        return key in self._store

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None


def _sync_managed_dataset(module_root, *, module_name: str, resource_id: str) -> None:
    from src.core.mms.data_contract import normalize_manifest_data
    from src.core.persistence import get_module_data_store

    manifest_data = normalize_manifest_data(
        {
            "resources": [
                {
                    "id": resource_id,
                    "storage_mode": "managed_dataset",
                }
            ],
            "views": [],
            "queries": [],
            "seeds": [],
        }
    )
    get_module_data_store().sync_manifest_data(module_name, module_root, manifest_data)


def test_runtime_tools_register_expected_surface():
    caps = build_runtime_capabilities("demo_module")

    assert caps.tools.has_tool("db.list_records") is True
    assert caps.tools.has_tool("db.get_record") is True
    assert caps.tools.has_tool("db.replace_records") is True
    assert caps.tools.has_tool("db.run_query") is True
    assert caps.tools.has_tool("db.query_view") is True
    assert caps.tools.has_tool("db.append_event") is True
    assert caps.tools.has_tool("db.query_events") is True
    assert caps.tools.has_tool("db.acquire_lock") is True
    assert caps.tools.has_tool("db.release_lock") is True
    assert caps.tools.has_tool("db.is_locked") is True
    assert caps.tools.has_tool("db.get_state") is True
    assert caps.tools.has_tool("db.set_state") is True
    assert caps.tools.has_tool("db.exists_state") is True
    assert caps.tools.has_tool("ip_pool.pick_proxy") is True
    assert caps.tools.has_tool("env.set_proxy") is True
    assert caps.tools.has_tool("env.bind_resource_pool") is True
    assert caps.tools.has_tool("env.mark_resource_pool_eligible") is True
    assert caps.tools.has_tool("env.mark_resource_pool_ineligible") is True
    assert caps.tools.has_tool("env.remove_resource_pool") is True
    assert caps.tools.has_tool("env.replace_resource_pool_snapshot") is True
    assert caps.tools.has_tool("ui.declare_page") is True
    assert caps.tools.has_tool("ui.get_page") is True
    assert caps.tools.has_tool("ui.declare_data_table") is False
    assert caps.tools.has_tool("ui.get_data_table") is False
    assert caps.tools.has_tool("captcha.match_slider") is True
    assert caps.tools.has_tool("captcha.match_click_targets") is True

    specs = caps.tools.list_tools()
    tool_names = [spec.name for spec in specs]
    assert tool_names == sorted(tool_names)
    assert {spec.name: spec.is_async for spec in specs}["env.bind_resource_pool"] is True
    assert {spec.name: spec.is_async for spec in specs}["env.mark_resource_pool_eligible"] is True
    assert {spec.name: spec.is_async for spec in specs}["env.mark_resource_pool_ineligible"] is True
    assert {spec.name: spec.is_async for spec in specs}["env.remove_resource_pool"] is True
    assert {spec.name: spec.is_async for spec in specs}["env.replace_resource_pool_snapshot"] is True
    assert {spec.name: spec.is_async for spec in specs}["env.set_proxy"] is True
    assert {spec.name: spec.is_async for spec in specs}["db.append_event"] is False
    assert {spec.name: spec.is_async for spec in specs}["db.get_record"] is False
    assert {spec.name: spec.is_async for spec in specs}["db.list_records"] is False
    assert {spec.name: spec.is_async for spec in specs}["db.run_query"] is False


def test_runtime_tools_register_hosted_ui_declare_surface():
    caps = build_runtime_capabilities("demo_module", surface=RUNTIME_SURFACE_HOSTED_UI_DECLARE)

    assert [spec.name for spec in caps.tools.list_tools()] == ["ui.declare_page"]
    assert caps.tools.has_tool("ui.declare_page") is True
    assert caps.tools.has_tool("ui.get_page") is False
    assert caps.tools.has_tool("db.list_records") is False

    with pytest.raises(KeyError, match=r"Unknown core tool: ui.get_page"):
        caps.tools.call("ui.get_page", page_id="dashboard")


def test_runtime_tools_hosted_ui_declare_surface_does_not_persist_page_schema():
    from src.core.persistence import get_module_data_store

    store = get_module_data_store()
    legacy_page = {
        "type": "Page",
        "title": "旧看板",
        "load_handler": "load_dashboard_page",
        "children": [],
    }
    assert store.write_page_schema("demo_module", "dashboard", legacy_page) is True

    caps = build_runtime_capabilities("demo_module", surface=RUNTIME_SURFACE_HOSTED_UI_DECLARE)

    with pytest.raises(RuntimeError, match="必须使用声明缓冲区"):
        caps.tools.call(
            "ui.declare_page",
            page_id="dashboard",
            schema={
                "type": "Page",
                "title": "新看板",
                "load_handler": "load_dashboard_page",
                "children": [],
            },
        )

    assert store.read_page_schema("demo_module", "dashboard") == legacy_page


def test_runtime_tools_register_hosted_ui_readonly_surface():
    caps = build_runtime_capabilities("demo_module", surface=RUNTIME_SURFACE_HOSTED_UI_READONLY)

    assert [spec.name for spec in caps.tools.list_tools()] == [
        "db.get_record",
        "db.list_records",
        "db.query_events",
        "db.query_view",
        "db.run_query",
        "ui.get_page",
    ]
    assert caps.tools.has_tool("ui.get_page") is True
    assert caps.tools.has_tool("db.list_records") is True
    assert caps.tools.has_tool("ui.declare_page") is False
    assert caps.tools.has_tool("db.set_state") is False
    assert caps.tools.has_tool("db.append_event") is False

    with pytest.raises(KeyError, match=r"Unknown core tool: db.set_state"):
        caps.tools.call("db.set_state", key="cursor", value=1)


def test_runtime_tools_hosted_ui_readonly_surface_does_not_read_persisted_page_schema():
    from src.core.persistence import get_module_data_store

    store = get_module_data_store()
    assert store.write_page_schema(
        "demo_module",
        "dashboard",
        {
            "type": "Page",
            "title": "旧看板",
            "load_handler": "load_dashboard_page",
            "children": [],
        },
    ) is True

    caps = build_runtime_capabilities("demo_module", surface=RUNTIME_SURFACE_HOSTED_UI_READONLY)

    with pytest.raises(RuntimeError, match="必须使用本轮声明的页面 schema"):
        caps.tools.call("ui.get_page", page_id="dashboard")


def test_db_tools_get_record_and_list_delegate_to_store(monkeypatch):
    get_calls: list[dict[str, object]] = []
    list_calls: list[dict[str, object]] = []

    class _FakeDataStore:
        def get_record(self, module_name: str, resource_id: str, key: object):
            get_calls.append(
                {
                    "module_name": module_name,
                    "resource_id": resource_id,
                    "key": key,
                }
            )
            return {"id": key, "phone": "13800138000"}

        def list_records(self, module_name: str, resource_id: str, **kwargs):
            list_calls.append(
                {
                    "module_name": module_name,
                    "resource_id": resource_id,
                    **kwargs,
                }
            )
            return [{"id": "u1"}]

    monkeypatch.setattr("src.core.atm.runtime_capabilities.get_module_data_store", lambda: _FakeDataStore())

    caps = build_runtime_capabilities("demo_module")
    record = caps.tools.call("db.get_record", resource="account_records", key="u1")
    rows = caps.tools.call(
        "db.list_records",
        resource="account_records",
        filters={"phone": "13800138000"},
        sort=[{"field": "phone", "direction": "asc"}],
        limit=5,
        offset=1,
    )

    assert record == {"id": "u1", "phone": "13800138000"}
    assert rows == [{"id": "u1"}]
    assert get_calls == [
        {
            "module_name": "demo_module",
            "resource_id": "account_records",
            "key": "u1",
        }
    ]
    assert list_calls == [
        {
            "module_name": "demo_module",
            "resource_id": "account_records",
            "filters": {"phone": "13800138000"},
            "sort": [{"field": "phone", "direction": "asc"}],
            "limit": 5,
            "offset": 1,
        }
    ]


def test_db_tools_run_query_and_query_view_delegate_to_store(monkeypatch):
    run_query_calls: list[dict[str, object]] = []
    query_calls: list[dict[str, object]] = []

    class _FakeDataStore:
        def run_registered_query(self, module_name: str, **kwargs):
            run_query_calls.append(
                {
                    "module_name": module_name,
                    **kwargs,
                }
            )
            return [{"entry_id": "row-1"}]

        def query_db_view(self, module_name: str, view_id: str, **kwargs):
            query_calls.append(
                {
                    "module_name": module_name,
                    "view_id": view_id,
                    **kwargs,
                }
            )
            return {"rows": [{"execution_date": "2026-04-23"}], "total": 1, "limit": 20, "offset": 0}

    monkeypatch.setattr("src.core.atm.runtime_capabilities.get_module_data_store", lambda: _FakeDataStore())
    monkeypatch.setattr(
        "src.core.atm.runtime_capabilities.load_sql_file",
        lambda module_root, relative_path, expected_prefix: "SELECT entry_id FROM {{resource:billing_entries}} WHERE entry_id = :entry_id",
    )
    monkeypatch.setattr(
        "src.core.atm.runtime_capabilities.validate_resource_sql",
        lambda sql, *, source_resource_ids, owner_label: None,
    )

    fake_module = SimpleNamespace(
        path=Path("/tmp/demo_module"),
        manifest=SimpleNamespace(
            data={
                "queries": [
                    {
                        "query_id": "get_billing_entry_by_id",
                        "source_resource_ids": ["billing_entries"],
                        "sql_file": "data/sql/queries/get_billing_entry_by_id.sql",
                        "params": [{"name": "entry_id", "type": "text", "required": True}],
                        "columns": [{"name": "entry_id", "type": "text", "nullable": False}],
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        "src.core.mms.registry.get_module_registry",
        lambda: SimpleNamespace(get_module=lambda module_name: fake_module if module_name == "demo_module" else None),
    )

    caps = build_runtime_capabilities("demo_module")
    queried_rows = caps.tools.call(
        "db.run_query",
        query_id="get_billing_entry_by_id",
        params={"entry_id": "row-1"},
    )
    queried_view = caps.tools.call(
        "db.query_view",
        view_id="billing_stats",
        filters={"execution_date": "2026-04-23"},
        sort=[{"field": "execution_date", "direction": "desc"}],
        limit=20,
        offset=0,
    )

    assert queried_rows == [{"entry_id": "row-1"}]
    assert queried_view["total"] == 1
    assert run_query_calls == [
        {
            "module_name": "demo_module",
            "source_resource_ids": ["billing_entries"],
            "sql_template": "SELECT entry_id FROM {{resource:billing_entries}} WHERE entry_id = :entry_id",
            "columns": [{"name": "entry_id", "type": "text", "nullable": False}],
            "params": {"entry_id": "row-1"},
        }
    ]
    assert query_calls == [
        {
            "module_name": "demo_module",
            "view_id": "billing_stats",
            "filters": {"execution_date": "2026-04-23"},
            "sort": [{"field": "execution_date", "direction": "desc"}],
            "limit": 20,
            "offset": 0,
        }
    ]


def test_db_tools_reject_undeclared_resources():
    caps = build_runtime_capabilities("demo_module")

    with pytest.raises(ValueError, match="未注册的数据资源: accounts"):
        caps.tools.call("db.list_records", resource="accounts")

    with pytest.raises(ValueError, match="未注册的数据资源: accounts"):
        caps.tools.call("db.get_record", resource="accounts", key="u1")

    with pytest.raises(ValueError, match="未注册的数据资源: accounts"):
        caps.tools.call("db.replace_records", resource="accounts", records=[{"id": "u1"}])


@pytest.mark.parametrize(
    ("params", "expected_message"),
    [
        ({}, "query 参数缺失: entry_id"),
        ({"entry_id": "row-1", "extra": 1}, "query 参数未注册: extra"),
    ],
)
def test_db_tools_run_query_rejects_invalid_params(
    monkeypatch,
    params: dict[str, object],
    expected_message: str,
):
    monkeypatch.setattr(
        "src.core.atm.runtime_capabilities.get_module_data_store",
        lambda: SimpleNamespace(run_registered_query=lambda *args, **kwargs: []),
    )
    monkeypatch.setattr(
        "src.core.atm.runtime_capabilities.load_sql_file",
        lambda module_root, relative_path, expected_prefix: "SELECT entry_id FROM {{resource:billing_entries}} WHERE entry_id = :entry_id",
    )
    monkeypatch.setattr(
        "src.core.atm.runtime_capabilities.validate_resource_sql",
        lambda sql, *, source_resource_ids, owner_label: None,
    )
    fake_module = SimpleNamespace(
        path=Path("/tmp/demo_module"),
        manifest=SimpleNamespace(
            data={
                "queries": [
                    {
                        "query_id": "get_billing_entry_by_id",
                        "source_resource_ids": ["billing_entries"],
                        "sql_file": "data/sql/queries/get_billing_entry_by_id.sql",
                        "params": [{"name": "entry_id", "type": "text", "required": True}],
                        "columns": [{"name": "entry_id", "type": "text", "nullable": False}],
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(
        "src.core.mms.registry.get_module_registry",
        lambda: SimpleNamespace(get_module=lambda module_name: fake_module if module_name == "demo_module" else None),
    )

    caps = build_runtime_capabilities("demo_module")

    with pytest.raises(ValueError, match=expected_message):
        caps.tools.call(
            "db.run_query",
            query_id="get_billing_entry_by_id",
            params=params,
        )


@pytest.mark.parametrize(
    "tool_name",
    [
        "db.replace_records",
        "db.append_event",
        "db.set_state",
        "db.acquire_lock",
        "db.release_lock",
    ],
)
def test_runtime_tools_hide_side_effect_db_tools_during_ui_declaration(tool_name: str):
    buffer = HostedUIDeclarationBuffer()
    caps = build_runtime_capabilities("demo_module", ui_declaration_buffer=buffer)

    assert caps.tools.has_tool(tool_name) is False
    assert tool_name not in {spec.name for spec in caps.tools.list_tools()}

    with pytest.raises(RuntimeError, match=rf"declare_ui 不允许调用 {tool_name}"):
        caps.tools.call(tool_name)

    buffer.seal()

    assert caps.tools.has_tool(tool_name) is True
    assert tool_name in {spec.name for spec in caps.tools.list_tools()}


def test_db_tools_records_and_lock_are_generic(temp_data_dir, monkeypatch):
    fake_kv = _FakeKV()
    monkeypatch.setattr("src.core.atm.runtime_capabilities.get_kv_store", lambda: fake_kv)
    _sync_managed_dataset(temp_data_dir, module_name="demo_module", resource_id="accounts")

    caps = build_runtime_capabilities("demo_module")
    assert caps.tools.call(
        "db.replace_records",
        resource="accounts",
        records=[
            {"id": "u1", "phone_number": "13800000001", "country_code": "86"},
            {"id": "u2", "phone_number": "13800000002", "country_code": "86"},
        ],
    )
    records = caps.tools.call("db.list_records", resource="accounts")
    assert len(records) == 2

    first = caps.tools.call(
        "db.acquire_lock",
        scope="accounts",
        key="13800000001",
        ttl=60,
        owner={"task_id": "t1", "job_id": "j1"},
    )
    second = caps.tools.call(
        "db.acquire_lock",
        scope="accounts",
        key="13800000001",
        ttl=60,
        owner={"task_id": "t2", "job_id": "j1"},
    )
    third = caps.tools.call("db.release_lock", scope="accounts", key="13800000001")

    assert first is True
    assert second is False
    assert third is True


def test_db_tools_replace_records_rejects_invalid_records(temp_data_dir):
    _sync_managed_dataset(temp_data_dir, module_name="demo_module", resource_id="accounts")
    caps = build_runtime_capabilities("demo_module")

    with pytest.raises(ValueError, match=r"resource records\[1\] must be an object"):
        caps.tools.call(
            "db.replace_records",
            resource="accounts",
            records=[
                {"id": "u1", "phone_number": "13800000001"},
                "broken-record",
            ],
        )

    assert caps.tools.call("db.list_records", resource="accounts") == []


def test_db_tools_append_and_query_events(temp_data_dir, monkeypatch):
    fake_kv = _FakeKV()
    monkeypatch.setattr("src.core.atm.runtime_capabilities.get_kv_store", lambda: fake_kv)
    _sync_managed_dataset(temp_data_dir, module_name="demo_module", resource_id="account_events")

    caps = build_runtime_capabilities("demo_module")
    first = caps.tools.call(
        "db.append_event",
        dataset="account_events",
        event_type="created",
        entity_key="13800000001",
        next_status="active",
        payload={"source": "import"},
        created_at=100,
    )
    second = caps.tools.call(
        "db.append_event",
        dataset="account_events",
        event_type="status_changed",
        entity_key="13800000001",
        previous_status="active",
        next_status="blocked",
        result="success",
        reason="risk_control",
        payload={"operator": "system"},
        created_at=200,
    )

    events = caps.tools.call("db.query_events", dataset="account_events")
    created_only = caps.tools.call(
        "db.query_events",
        dataset="account_events",
        entity_key="13800000001",
        event_type="created",
    )
    records = caps.tools.call("db.list_records", resource="account_events")

    assert first is True
    assert second is True
    assert [item["event_type"] for item in events] == ["status_changed", "created"]
    assert created_only[0]["payload"] == {"source": "import"}
    assert records == []


def test_db_tools_state_roundtrip(monkeypatch):
    fake_kv = _FakeKV()
    monkeypatch.setattr("src.core.atm.runtime_capabilities.get_kv_store", lambda: fake_kv)

    caps = build_runtime_capabilities("demo_module")

    assert caps.tools.call("db.set_state", key="demo_module:cursor", value={"page": 2}, ttl=60) is True
    assert caps.tools.call("db.get_state", key="demo_module:cursor") == {"page": 2}
    assert caps.tools.call("db.exists_state", key="demo_module:cursor") is True


def test_ip_pool_tool_picks_proxy_by_criteria(monkeypatch):
    pool = IPPool(id="p1", name="pool-1")
    pool.entries = [
        IPEntry(
            id="ip-low", pool_id="p1", address="1.1.1.1", protocol="http", port=8001, safety_score=70, bound_count=0
        ),
        IPEntry(
            id="ip-best", pool_id="p1", address="2.2.2.2", protocol="http", port=8002, safety_score=99, bound_count=0
        ),
        IPEntry(
            id="ip-busy", pool_id="p1", address="3.3.3.3", protocol="http", port=8003, safety_score=95, bound_count=5
        ),
    ]
    fake_manager = SimpleNamespace(
        get_pool=lambda pool_id: pool if pool_id == "p1" else None, list_pools=lambda: [pool]
    )
    monkeypatch.setattr("src.core.atm.runtime_capabilities.get_ip_pool_manager", lambda: fake_manager)

    caps = build_runtime_capabilities("demo_module")
    selected = caps.tools.call(
        "ip_pool.pick_proxy",
        criteria={
            "pool_id": "p1",
            "protocol": "http",
            "min_safety_score": 90,
            "max_bound_count": 2,
        },
    )

    assert selected is not None
    assert selected["id"] == "ip-best"
    assert selected["proxy_url"].startswith("http://")


@pytest.mark.asyncio
async def test_env_tool_delegates_to_environment_manager(monkeypatch):
    calls: list[tuple[int, str | None, str | None]] = []

    async def _update_env(env_id: int, *, proxy_value: str | None = None, proxy_pool_id: str | None = None):
        calls.append((env_id, proxy_value, proxy_pool_id))
        return True

    fake_manager = SimpleNamespace(update_env=_update_env)
    monkeypatch.setattr("src.core.atm.runtime_capabilities.get_environment_manager", lambda: fake_manager)

    caps = build_runtime_capabilities("demo_module")
    ok = await caps.tools.call("env.set_proxy", env_id=12, proxy_value="http://1.1.1.1:8001", proxy_pool_id=None)

    assert ok is True
    assert calls == [(12, "http://1.1.1.1:8001", None)]


@pytest.mark.asyncio
async def test_env_resource_pool_tools_manage_metadata_cards(monkeypatch):
    store: dict[tuple[int, str, str], object] = {
        (13, "scheduler.resource_pool", "demo_module:bound_account_ready"): {
            "module_name": "demo_module",
            "pool_name": "bound_account_ready",
            "eligible": True,
            "reason": "",
            "exclusive": True,
            "updated_at": 1,
        }
    }

    class _FakeManager:
        async def update_env(self, env_id: int, *, proxy_value: str | None = None, proxy_pool_id: str | None = None):
            return True

        async def set_metadata(self, env_id: int, namespace: str, key: str, value, value_type: str = "string"):
            store[(env_id, namespace, key)] = value
            return True

        async def get_metadata(self, env_id: int, namespace: str, key: str):
            return store.get((env_id, namespace, key))

        async def delete_metadata(self, env_id: int, namespace: str, key: str | None = None):
            removed = 0
            for entry_key in list(store):
                same_env = entry_key[0] == env_id
                same_namespace = entry_key[1] == namespace
                same_key = key is None or entry_key[2] == key
                if same_env and same_namespace and same_key:
                    store.pop(entry_key, None)
                    removed += 1
            return removed

        async def list_envs(self):
            return [SimpleNamespace(id=11), SimpleNamespace(id=12), SimpleNamespace(id=13)]

    monkeypatch.setattr("src.core.atm.runtime_capabilities.get_environment_manager", lambda: _FakeManager())

    caps = build_runtime_capabilities("demo_module")
    await caps.tools.call(
        "env.bind_resource_pool",
        env_id=11,
        pool_name="bound_account_ready",
        eligible=True,
        reason="",
        exclusive=True,
    )
    await caps.tools.call(
        "env.mark_resource_pool_ineligible",
        env_id=11,
        pool_name="bound_account_ready",
        reason="blacklisted",
    )
    await caps.tools.call(
        "env.replace_resource_pool_snapshot",
        pool_name="bound_account_ready",
        entries=[
            {"env_id": 11, "eligible": True, "reason": "", "exclusive": True},
            {"env_id": 12, "eligible": False, "reason": "manual_disabled", "exclusive": True},
        ],
    )
    await caps.tools.call(
        "env.remove_resource_pool",
        env_id=12,
        pool_name="bound_account_ready",
    )

    card_11 = store[(11, "scheduler.resource_pool", "demo_module:bound_account_ready")]
    assert card_11["module_name"] == "demo_module"
    assert card_11["pool_name"] == "bound_account_ready"
    assert card_11["eligible"] is True
    assert (12, "scheduler.resource_pool", "demo_module:bound_account_ready") not in store
    assert (13, "scheduler.resource_pool", "demo_module:bound_account_ready") not in store


def test_ui_tools_persist_page_meta(monkeypatch):
    caps = build_runtime_capabilities("demo_module")
    assert caps.tools.call(
        "ui.declare_page",
        page_id="dashboard",
        schema={
            "type": "Page",
            "load_handler": "load_dashboard_page",
            "children": [
                {"type": "Text", "style": "title", "binding": "title"},
                {
                    "type": "Button",
                    "label": "打开详情页",
                    "action": {
                        "type": "open_page",
                        "page_id": "details",
                        "params": {
                            "account_id": {"binding": "selected_account.id"},
                        },
                    },
                },
                {
                    "type": "DataTable",
                    "table_id": "stats",
                    "title": "统计明细",
                    "columns": [{"key": "name", "label": "名称"}],
                    "data_source": {"type": "binding", "binding": "rows"},
                    "row_action": {
                        "type": "open_page",
                        "page_id": "details",
                        "params": {
                            "account_id": {"binding": "id"},
                        },
                    },
                },
            ],
        },
    )

    page = caps.tools.call("ui.get_page", page_id="dashboard")
    assert page["load_handler"] == "load_dashboard_page"
    assert page["children"][0] == {
        "type": "Text",
        "style": "title",
        "binding": "title",
    }
    assert page["children"][1]["action"] == {
        "type": "open_page",
        "page_id": "details",
        "params": {"account_id": {"binding": "selected_account.id"}},
    }
    assert page["children"][2]["table_id"] == "stats"
    assert page["children"][2]["data_source"] == {"type": "binding", "binding": "rows"}
    assert page["children"][2]["row_action"] == {
        "type": "open_page",
        "page_id": "details",
        "params": {"account_id": {"binding": "id"}},
    }


def test_ui_tools_persist_navigation_params_with_page_ids():
    caps = build_runtime_capabilities("demo_module")

    assert caps.tools.call(
        "ui.declare_page",
        page_id="dashboard",
        schema={
            "type": "Page",
            "load_handler": "load_dashboard_page",
            "children": [
                {
                    "type": "Button",
                    "label": "打开详情",
                    "action": {
                        "type": "open_page",
                        "page_id": "account_details",
                        "params": {
                            "phone": {"binding": "selected.phone"},
                            "source": {"value": "dashboard"},
                        },
                    },
                },
                {
                    "type": "DataTable",
                    "table_id": "accounts",
                    "columns": [{"key": "phone", "label": "手机号"}],
                    "data_source": {"type": "binding", "binding": "rows"},
                    "row_action": {
                        "type": "open_page",
                        "page_id": "account_details",
                        "params": {
                            "phone": {"binding": "phone"},
                        },
                    },
                },
            ],
        },
    )

    page = caps.tools.call("ui.get_page", page_id="dashboard")

    assert page["children"][0]["action"] == {
        "type": "open_page",
        "page_id": "account_details",
        "params": {
            "phone": {"binding": "selected.phone"},
            "source": {"value": "dashboard"},
        },
    }
    assert page["children"][1]["row_action"] == {
        "type": "open_page",
        "page_id": "account_details",
        "params": {
            "phone": {"binding": "phone"},
        },
    }
    assert page["children"][1]["table_id"] == "accounts"
    assert page["children"][1]["data_source"] == {"type": "binding", "binding": "rows"}


def test_ui_tools_delegate_normalization_to_sdk(monkeypatch):
    page_calls: list[tuple[str, dict[str, object]]] = []

    def fake_normalize_page_schema(page_id: str, schema: dict[str, object]) -> dict[str, object]:
        page_calls.append((page_id, dict(schema)))
        return {"type": "Page", "title": f"normalized:{page_id}", "children": []}

    monkeypatch.setattr(runtime_capabilities, "sdk_normalize_page_schema", fake_normalize_page_schema)

    caps = build_runtime_capabilities("demo_module")
    assert caps.tools.call(
        "ui.declare_page",
        page_id="dashboard",
        schema={"type": "Page", "children": []},
    )

    assert page_calls == [("dashboard", {"type": "Page", "children": []})]
    assert caps.tools.call("ui.get_page", page_id="dashboard") == {
        "type": "Page",
        "title": "normalized:dashboard",
        "children": [],
    }


def test_ui_tools_reject_unmanaged_schema_fields():
    caps = build_runtime_capabilities("demo_module")

    with pytest.raises(ValueError):
        caps.tools.call(
            "ui.declare_page",
            page_id="Dashboard",
            schema={"type": "Page", "children": []},
        )

    with pytest.raises(ValueError):
        caps.tools.call(
            "ui.declare_page",
            page_id="dashboard",
            schema={"type": "Section", "children": []},
        )

    with pytest.raises(ValueError):
        caps.tools.call(
            "ui.declare_page",
            page_id="dashboard",
            schema={
                "type": "Page",
                "children": [
                    {
                        "type": "Button",
                        "label": "打开",
                        "action": {"type": "open_page", "page_id": "InvalidPage"},
                    }
                ],
            },
        )

    with pytest.raises(ValueError):
        caps.tools.call(
            "ui.declare_page",
            page_id="dashboard",
            schema={
                "type": "Page",
                "load_handler": "load_dashboard_page",
                "children": [
                    {
                        "type": "DataTable",
                        "title": "统计明细",
                        "rows": [{"id": "1"}],
                        "row_action": {
                            "type": "open_page",
                            "page_id": "accounts",
                            "params": {"account_id": {"binding": ""}},
                        },
                    }
                ],
            },
        )


def test_captcha_tool_matches_slider_via_sinanz(monkeypatch):
    calls: list[dict[str, object]] = []

    def _fake_solve_slider(**kwargs):
        calls.append(kwargs)
        return SliderCaptchaMatchResult(
            target_center=(135, 48),
            target_bbox=(100, 16, 170, 80),
            puzzle_piece_offset=(18, 0),
        )

    monkeypatch.setattr("src.core.atm.runtime_capabilities._solve_slider_with_sinanz", _fake_solve_slider)

    caps = build_runtime_capabilities("demo_module")
    result = caps.tools.call(
        "captcha.match_slider",
        background_image=b"background",
        puzzle_piece_image=b"piece",
        puzzle_piece_start_bbox=(0, 0, 40, 40),
        device="cpu",
        return_debug=True,
    )

    assert result.target_center == (135, 48)
    assert calls == [
        {
            "background_image": b"background",
            "puzzle_piece_image": b"piece",
            "puzzle_piece_start_bbox": (0, 0, 40, 40),
            "device": "cpu",
            "return_debug": True,
        }
    ]


def test_captcha_tool_matches_click_targets_via_sinanz(monkeypatch):
    calls: list[dict[str, object]] = []

    def _fake_solve_click(**kwargs):
        calls.append(kwargs)
        return ClickCaptchaMatchResult(
            ordered_target_centers=[(15, 20), (80, 65)],
            ordered_targets=[
                ClickCaptchaOrderedTarget(
                    query_order=1, center=(15, 20), class_id=0, class_name="target_1", score=0.97
                ),
                ClickCaptchaOrderedTarget(
                    query_order=2, center=(80, 65), class_id=1, class_name="target_2", score=0.93
                ),
            ],
        )

    monkeypatch.setattr("src.core.atm.runtime_capabilities._solve_click_with_sinanz", _fake_solve_click)

    caps = build_runtime_capabilities("demo_module")
    result = caps.tools.call(
        "captcha.match_click_targets",
        query_icons_image=b"query",
        background_image=b"background",
        device="cuda",
        return_debug=False,
    )

    assert result.ordered_target_centers == [(15, 20), (80, 65)]
    assert calls == [
        {
            "query_icons_image": b"query",
            "background_image": b"background",
            "device": "cuda",
            "return_debug": False,
        }
    ]


def test_captcha_resource_root_prefers_bundled_resources(tmp_path, monkeypatch):
    bundled_resources = tmp_path / "resources"
    bundled_resources.mkdir()
    monkeypatch.setattr(
        runtime_capabilities,
        "get_resource_path",
        lambda relative_path: str((tmp_path / relative_path).resolve()),
    )
    runtime_capabilities._resolve_captcha_resource_root.cache_clear()
    runtime_capabilities._resolve_captcha_models_root.cache_clear()

    try:
        assert runtime_capabilities._resolve_captcha_resource_root() == bundled_resources
    finally:
        runtime_capabilities._resolve_captcha_resource_root.cache_clear()
        runtime_capabilities._resolve_captcha_models_root.cache_clear()


def test_captcha_models_root_prefers_resources_models_subdir(tmp_path, monkeypatch):
    bundled_models = tmp_path / "resources" / "models"
    bundled_models.mkdir(parents=True)
    monkeypatch.setattr(
        runtime_capabilities,
        "get_resource_path",
        lambda relative_path: str((tmp_path / relative_path).resolve()),
    )
    runtime_capabilities._resolve_captcha_resource_root.cache_clear()
    runtime_capabilities._resolve_captcha_models_root.cache_clear()

    try:
        assert runtime_capabilities._resolve_captcha_models_root() == bundled_models
    finally:
        runtime_capabilities._resolve_captcha_resource_root.cache_clear()
        runtime_capabilities._resolve_captcha_models_root.cache_clear()


def test_solve_slider_with_sinanz_passes_resolved_asset_root(tmp_path, monkeypatch):
    calls: list[dict[str, object]] = []

    class _FakeSolver:
        def __init__(self, *, device: str, asset_root: Path | None):
            calls.append({"device": device, "asset_root": asset_root})

        def sn_match_slider(
            self, background_image, puzzle_piece_image, *, puzzle_piece_start_bbox=None, return_debug=False
        ):
            calls.append(
                {
                    "background_image": background_image,
                    "puzzle_piece_image": puzzle_piece_image,
                    "puzzle_piece_start_bbox": puzzle_piece_start_bbox,
                    "return_debug": return_debug,
                }
            )
            return SimpleNamespace(
                target_center=(135, 48),
                target_bbox=(100, 16, 170, 80),
                puzzle_piece_offset=(18, 0),
                debug=None,
            )

    monkeypatch.setattr(runtime_capabilities, "_resolve_captcha_models_root", lambda: tmp_path)
    monkeypatch.setitem(sys.modules, "sinanz", SimpleNamespace(CaptchaSolver=_FakeSolver))

    result = runtime_capabilities._solve_slider_with_sinanz(
        background_image=b"background",
        puzzle_piece_image=b"piece",
        puzzle_piece_start_bbox=(0, 0, 40, 40),
        device="cpu",
        return_debug=True,
    )

    assert result.target_center == (135, 48)
    assert calls == [
        {"device": "cpu", "asset_root": tmp_path},
        {
            "background_image": b"background",
            "puzzle_piece_image": b"piece",
            "puzzle_piece_start_bbox": (0, 0, 40, 40),
            "return_debug": True,
        },
    ]


def test_solve_click_with_sinanz_passes_resolved_asset_root(tmp_path, monkeypatch):
    calls: list[dict[str, object]] = []

    def _fake_solve_click_targets(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            ordered_target_centers=[(15, 20)],
            ordered_targets=[
                SimpleNamespace(query_order=1, center=(15, 20), class_id=0, class_name="target_1", score=0.97),
            ],
            missing_query_orders=[],
            ambiguous_query_orders=[],
            debug=None,
        )

    monkeypatch.setattr(runtime_capabilities, "_resolve_captcha_resource_root", lambda: tmp_path)
    monkeypatch.setitem(
        sys.modules, "sinanz_group1_service", SimpleNamespace(solve_click_targets=_fake_solve_click_targets)
    )

    result = runtime_capabilities._solve_click_with_sinanz(
        query_icons_image=b"query",
        background_image=b"background",
        device="cuda",
        return_debug=False,
    )

    assert result.ordered_target_centers == [(15, 20)]
    assert calls == [
        {
            "query_icons_image": b"query",
            "background_image": b"background",
            "device": "cuda",
            "asset_root": tmp_path,
            "return_debug": False,
        }
    ]

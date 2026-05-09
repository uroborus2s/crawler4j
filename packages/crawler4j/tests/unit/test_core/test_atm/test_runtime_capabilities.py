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
    RUNTIME_SURFACE_ENV_CLEANUP_CANDIDATES,
    RUNTIME_SURFACE_ENV_CANDIDATES,
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


def _sync_managed_dataset(module_root, *, module_name: str, resource_id: str) -> None:
    from src.core.mms.data_contract import normalize_manifest_data
    from src.core.persistence import get_module_data_store

    manifest_data = normalize_manifest_data(
        {
            "resources": [
                {
                    "id": resource_id,
                    "storage_mode": "managed_dataset",
                    "schema": {
                        "version": 1,
                        "columns": [
                            {"name": "id", "type": "text", "required": True},
                            {"name": "phone", "type": "text"},
                            {"name": "tier", "type": "text"},
                        ],
                    },
                }
            ],
            "views": [],
            "seeds": [],
        }
    )
    get_module_data_store().sync_manifest_data(module_name, module_root, manifest_data)


def _sync_custom_accounts(module_root, *, module_name: str, resource_id: str = "accounts") -> None:
    from src.core.mms.data_contract import normalize_manifest_data
    from src.core.persistence import get_module_data_store

    manifest_data = normalize_manifest_data(
        {
            "resources": [
                {
                    "id": resource_id,
                    "storage_mode": "custom_table",
                    "record_key_field": "id",
                    "schema": {
                        "version": 1,
                        "columns": [
                            {"name": "id", "type": "text", "required": True},
                            {"name": "status", "type": "text"},
                        ],
                    },
                }
            ],
            "views": [],
            "seeds": [],
        }
    )
    get_module_data_store().sync_manifest_data(module_name, module_root, manifest_data)


def _sync_custom_auto_increment_accounts(module_root, *, module_name: str, resource_id: str = "accounts") -> None:
    from src.core.mms.data_contract import normalize_manifest_data
    from src.core.persistence import get_module_data_store

    manifest_data = normalize_manifest_data(
        {
            "resources": [
                {
                    "id": resource_id,
                    "storage_mode": "custom_table",
                    "record_key_field": "id",
                    "schema": {
                        "version": 1,
                        "columns": [
                            {"name": "id", "type": "int", "auto_increment": True},
                            {"name": "status", "type": "text"},
                        ],
                    },
                }
            ],
            "views": [],
            "seeds": [],
        }
    )
    get_module_data_store().sync_manifest_data(module_name, module_root, manifest_data)


def test_runtime_tools_register_expected_surface():
    caps = build_runtime_capabilities("demo_module")

    assert caps.tools.has_tool("ip_pool.pick_proxy") is True
    assert caps.tools.has_tool("env.set_proxy") is True
    assert caps.tools.has_tool("env.bind_resource_pool") is False
    assert caps.tools.has_tool("env.mark_resource_pool_eligible") is False
    assert caps.tools.has_tool("env.mark_resource_pool_ineligible") is False
    assert caps.tools.has_tool("env.remove_resource_pool") is False
    assert caps.tools.has_tool("env.replace_resource_pool_snapshot") is False
    assert caps.tools.has_tool("ui.declare_page") is False
    assert caps.tools.has_tool("ui.get_page") is False
    assert caps.tools.has_tool("ui.declare_data_table") is False
    assert caps.tools.has_tool("ui.get_data_table") is False
    assert caps.tools.has_tool("captcha.match_slider") is True
    assert caps.tools.has_tool("captcha.match_click_targets") is True

    specs = caps.tools.list_tools()
    tool_names = [spec.name for spec in specs]
    assert tool_names == sorted(tool_names)
    assert not any(name.startswith("db.") for name in tool_names)
    assert {spec.name: spec.is_async for spec in specs}["env.set_proxy"] is True


def test_runtime_tools_register_hosted_ui_declare_surface():
    caps = build_runtime_capabilities("demo_module", surface=RUNTIME_SURFACE_HOSTED_UI_DECLARE)

    assert [spec.name for spec in caps.tools.list_tools()] == ["ui.declare_page"]
    assert caps.tools.has_tool("ui.declare_page") is True
    assert caps.tools.has_tool("ui.get_page") is False
    assert not any(spec.name.startswith("db.") for spec in caps.tools.list_tools())

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

    assert [spec.name for spec in caps.tools.list_tools()] == ["ui.get_page"]
    assert caps.tools.has_tool("ui.get_page") is True
    assert caps.tools.has_tool("ui.declare_page") is False
    assert not any(spec.name.startswith("db.") for spec in caps.tools.list_tools())

    with pytest.raises(KeyError, match=r"Unknown core tool: ui.unknown"):
        caps.tools.call("ui.unknown", key="cursor", value=1)


def test_runtime_tools_register_env_candidates_surface_as_readonly_toolless(temp_data_dir):
    _sync_managed_dataset(temp_data_dir, module_name="demo_module", resource_id="accounts")

    caps = build_runtime_capabilities("demo_module", surface=RUNTIME_SURFACE_ENV_CANDIDATES)

    assert caps.tools.list_tools() == []
    assert caps.db.from_("accounts").limit(10).execute() == []
    with pytest.raises(RuntimeError, match="不允许写入"):
        caps.db.into("accounts").replace([])


def test_runtime_tools_register_env_cleanup_candidates_surface_as_readonly_toolless(temp_data_dir):
    _sync_managed_dataset(temp_data_dir, module_name="demo_module", resource_id="accounts")

    caps = build_runtime_capabilities("demo_module", surface=RUNTIME_SURFACE_ENV_CLEANUP_CANDIDATES)

    assert caps.tools.list_tools() == []
    assert caps.db.from_("accounts").limit(10).execute() == []
    with pytest.raises(RuntimeError, match="不允许写入"):
        caps.db.into("accounts").replace([])


def test_runtime_tools_hosted_ui_readonly_surface_does_not_read_persisted_page_schema():
    from src.core.persistence import get_module_data_store

    store = get_module_data_store()
    assert (
        store.write_page_schema(
            "demo_module",
            "dashboard",
            {
                "type": "Page",
                "title": "旧看板",
                "load_handler": "load_dashboard_page",
                "children": [],
            },
        )
        is True
    )

    caps = build_runtime_capabilities("demo_module", surface=RUNTIME_SURFACE_HOSTED_UI_READONLY)

    with pytest.raises(RuntimeError, match="必须使用本轮声明的页面 schema"):
        caps.tools.call("ui.get_page", page_id="dashboard")


def test_runtime_ctx_db_replaces_public_db_tools(temp_data_dir):
    _sync_managed_dataset(temp_data_dir, module_name="demo_module", resource_id="accounts")
    caps = build_runtime_capabilities("demo_module")

    assert not any(spec.name.startswith("db.") for spec in caps.tools.list_tools())
    assert (
        caps.db.into("accounts").replace(
            [
                {"id": "u1", "run_status": "占用中", "record_status": "active"},
                {"id": "u2", "run_status": "空闲", "record_status": "blocked"},
            ]
        )
        is True
    )

    all_rows = caps.db.from_("accounts").limit(10).execute()
    assert all({"run_status", "record_status", "created_at", "updated_at"} <= set(row) for row in all_rows)
    assert all(isinstance(row["created_at"], int) for row in all_rows)
    assert all(isinstance(row["updated_at"], int) for row in all_rows)
    assert all_rows[0]["run_status"] == "占用中"
    assert all_rows[0]["record_status"] == "active"

    rows = caps.db.from_("accounts").select("id").where(["id", "=", "u2"]).limit(10).execute()

    assert rows == [{"id": "u2"}]


def test_runtime_ctx_db_managed_dataset_where_can_use_physical_and_schema_fields(temp_data_dir):
    _sync_managed_dataset(temp_data_dir, module_name="demo_module", resource_id="accounts")
    caps = build_runtime_capabilities("demo_module")
    from src.core.persistence import get_module_data_store

    assert (
        caps.db.into("accounts").replace(
            [
                {"id": "u1", "phone": "13800138000", "tier": "vip"},
                {"id": "u2", "phone": "13900139000", "tier": "standard"},
            ]
        )
        is True
    )

    expected = get_module_data_store().query_resource_records(
        "demo_module",
        "accounts",
        select=["id", "tier"],
        where=["tier", "=", "standard"],
        limit=10,
        offset=0,
    )
    assert expected == [{"id": "u2", "tier": "standard"}]

    assert (caps.db.from_("accounts").select(["id", "tier"]).where(["tier", "=", "standard"]).execute()) == expected
    with pytest.raises(ValueError, match="query select field not found: unseen_flag"):
        caps.db.from_("accounts").select(["id", "unseen_flag"]).where(["unseen_flag", "=", "yes"]).execute()
    with pytest.raises(ValueError, match="query select field not found: unseen_flag"):
        get_module_data_store().query_resource_records(
            "demo_module",
            "accounts",
            select=["id", "unseen_flag"],
            where=["unseen_flag", "=", "yes"],
            limit=100,
            offset=0,
        )

    rows = (
        caps.db.from_("accounts")
        .select(["record_key", "id"])
        .where(["record_key", "=", "u2"])
        .where(["id", "=", "u2"])
        .execute()
    )

    assert rows == [{"record_key": "u2", "id": "u2"}]

    all_rows = caps.db.from_("accounts").select("*").order_by("phone", "desc").execute()
    assert [row["id"] for row in all_rows] == ["u2", "u1"]
    assert {
        "id",
        "phone",
        "record_index",
        "record_key",
        "run_status",
        "record_status",
        "created_at",
        "updated_at",
    } <= set(all_rows[0])


def test_runtime_ctx_db_managed_dataset_count_returns_filtered_row_total(temp_data_dir):
    _sync_managed_dataset(temp_data_dir, module_name="demo_module", resource_id="accounts")
    caps = build_runtime_capabilities("demo_module")

    assert (
        caps.db.into("accounts").replace(
            [
                {"id": "u1", "phone": "13800138000", "tier": "vip"},
                {"id": "u2", "phone": "13900139000", "tier": "standard", "run_status": "占用中"},
                {"id": "u3", "phone": "13700137000", "tier": "standard", "run_status": "占用中"},
            ]
        )
        is True
    )

    rows = caps.db.from_("accounts").where(["tier", "=", "standard"]).count(alias="total").execute()
    occupied_rows = caps.db.from_("accounts").where(["run_status", "=", "占用中"]).count(alias="occupied_total").execute()

    assert rows == [{"total": 2}]
    assert occupied_rows == [{"occupied_total": 2}]


def test_runtime_ctx_db_supports_upsert_update_delete_and_batch(temp_data_dir):
    _sync_custom_accounts(temp_data_dir, module_name="demo_module")
    caps = build_runtime_capabilities("demo_module")

    assert (
        caps.db.into("accounts").upsert(
            [
                {"id": "u1", "status": "new"},
                {"id": "u2", "status": "expired"},
            ]
        )
        is True
    )
    assert (
        caps.db.into("accounts").update_where(
            {"status": "ready"},
            where=["id", "=", "u1"],
        )
        == 1
    )
    assert caps.db.into("accounts").delete_where(where=["status", "=", "expired"]) == 1

    results = (
        caps.db.batch()
        .upsert("accounts", [{"id": "u3", "status": "ready"}])
        .audit(
            "account_events",
            {"entity_key": "u3", "event_type": "created", "created_at": 100},
        )
        .execute()
    )

    assert results[0] is True
    assert isinstance(results[1], str)
    assert caps.db.from_("accounts").order_by("id").execute() == [
        {"id": "u1", "status": "ready"},
        {"id": "u3", "status": "ready"},
    ]
    assert caps.db.audit("account_events").query(entity_key="u3") == [
        {
            "id": results[1],
            "module_name": "demo_module",
            "dataset_name": "account_events",
            "entity_key": "u3",
            "event_type": "created",
            "run_id": None,
            "previous_status": None,
            "next_status": None,
            "result": None,
            "reason": None,
            "payload": {},
            "created_at": 100,
        }
    ]


def test_runtime_ctx_db_update_delete_accept_query_builder_callable_where(temp_data_dir):
    _sync_custom_accounts(temp_data_dir, module_name="demo_module")
    caps = build_runtime_capabilities("demo_module")

    assert (
        caps.db.into("accounts").upsert(
            [
                {"id": "u1", "status": "new"},
                {"id": "u2", "status": "expired"},
                {"id": "u3", "status": "reserved"},
            ]
        )
        is True
    )
    assert (
        caps.db.into("accounts").update_where(
            {"status": "ready"},
            where=lambda query: query.where("id", "=", "u1"),
        )
        == 1
    )
    assert (
        caps.db.into("accounts").delete_where(
            where=lambda query: query.where(["or", ["status", "=", "expired"], ["status", "=", "reserved"]]),
        )
        == 2
    )
    assert caps.db.from_("accounts").order_by("id").execute() == [{"id": "u1", "status": "ready"}]


def test_runtime_ctx_db_add_supports_custom_table_auto_increment_ids(temp_data_dir):
    _sync_custom_auto_increment_accounts(temp_data_dir, module_name="demo_module")
    caps = build_runtime_capabilities("demo_module")

    inserted_ids = caps.db.into("accounts").add([{"status": "new"}, {"status": "ready"}])

    assert inserted_ids == [1, 2]
    assert caps.db.from_("accounts").order_by("id").execute() == [
        {"id": 1, "status": "new"},
        {"id": 2, "status": "ready"},
    ]


def test_runtime_ctx_db_managed_dataset_supports_incremental_writes(temp_data_dir):
    _sync_managed_dataset(temp_data_dir, module_name="demo_module", resource_id="accounts")
    caps = build_runtime_capabilities("demo_module")

    assert (
        caps.db.into("accounts").replace(
            [
                {"id": "u1", "phone": "13800138000"},
                {"id": "u2", "phone": "13900139000"},
            ]
        )
        is True
    )
    assert (
        caps.db.into("accounts").upsert(
            [
                {"id": "u2", "phone": "13999999999"},
                {"id": "u3", "phone": "13700137000"},
            ]
        )
        is True
    )
    assert caps.db.into("accounts").update_where({"phone": "13600136000"}, where=["id", "=", "u1"]) == 1
    assert caps.db.into("accounts").delete_where(where=["phone", "=", "13700137000"]) == 1

    assert caps.db.from_("accounts").select(["id", "phone", "record_index"]).order_by("record_index").execute() == [
        {"id": "u1", "phone": "13600136000", "record_index": 0},
        {"id": "u2", "phone": "13999999999", "record_index": 1},
    ]


def test_runtime_ctx_db_managed_dataset_rejects_reserved_update_fields(temp_data_dir):
    _sync_managed_dataset(temp_data_dir, module_name="demo_module", resource_id="accounts")
    caps = build_runtime_capabilities("demo_module")
    caps.db.into("accounts").replace([{"id": "u1", "phone": "13800138000"}])

    with pytest.raises(ValueError, match="reserved host fields"):
        caps.db.into("accounts").update_where({"updated_at": 1}, where=["id", "=", "u1"])


def test_runtime_ctx_db_audit_uses_independent_audit_table(temp_data_dir):
    from src.core.persistence import DATA_DB, get_connection

    caps = build_runtime_capabilities("demo_module")

    event_id = caps.db.audit("account_events").append(
        entity_key="13800138000",
        event_type="status_changed",
        previous_status="active",
        next_status="blocked",
        result="success",
        reason="risk_control",
        payload={"operator": "system"},
        created_at=200,
    )
    events = caps.db.audit("account_events").query(entity_key="13800138000")

    assert events == [
        {
            "id": event_id,
            "module_name": "demo_module",
            "dataset_name": "account_events",
            "entity_key": "13800138000",
            "event_type": "status_changed",
            "run_id": None,
            "previous_status": "active",
            "next_status": "blocked",
            "result": "success",
            "reason": "risk_control",
            "payload": {"operator": "system"},
            "created_at": 200,
        }
    ]
    with get_connection(DATA_DB) as conn:
        dataset_rows = conn.execute(
            "SELECT COUNT(*) AS count FROM module_datasets WHERE module_name = ?",
            ("demo_module",),
        ).fetchone()
    assert dataset_rows["count"] == 0


def test_runtime_ctx_db_rejects_complex_query_on_managed_dataset(temp_data_dir):
    _sync_managed_dataset(temp_data_dir, module_name="demo_module", resource_id="accounts")
    caps = build_runtime_capabilities("demo_module")

    with pytest.raises(ValueError, match="managed_dataset\\(snapshot\\).*join"):
        caps.db.from_("accounts").join("profiles", on={"id": "id"}).execute()


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
    monkeypatch.setattr("src.core.atm.runtime_capabilities._get_ip_pool_manager", lambda: fake_manager)

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
    monkeypatch.setattr("src.core.rem.manager.get_environment_manager", lambda: fake_manager)

    caps = build_runtime_capabilities("demo_module")
    ok = await caps.tools.call("env.set_proxy", env_id=12, proxy_value="http://1.1.1.1:8001", proxy_pool_id=None)

    assert ok is True
    assert calls == [(12, "http://1.1.1.1:8001", None)]


@pytest.mark.parametrize(
    "tool_name",
    [
        "env.bind_resource_pool",
        "env.mark_resource_pool_eligible",
        "env.mark_resource_pool_ineligible",
        "env.remove_resource_pool",
        "env.replace_resource_pool_snapshot",
    ],
)
def test_env_resource_pool_tools_are_removed(tool_name):
    caps = build_runtime_capabilities("demo_module")

    with pytest.raises(KeyError, match="Unknown core tool"):
        caps.tools.call(tool_name)


def test_full_surface_rejects_legacy_hosted_ui_tools():
    caps = build_runtime_capabilities("demo_module")

    assert caps.tools.has_tool("ui.declare_page") is False
    assert caps.tools.has_tool("ui.get_page") is False

    with pytest.raises(KeyError, match=r"Unknown core tool: ui.declare_page"):
        caps.tools.call("ui.declare_page", page_id="dashboard", schema={"type": "Page", "children": []})
    with pytest.raises(KeyError, match=r"Unknown core tool: ui.get_page"):
        caps.tools.call("ui.get_page", page_id="dashboard")


def test_ui_tools_stage_page_meta_in_declare_buffer(monkeypatch):
    buffer = HostedUIDeclarationBuffer()
    caps = build_runtime_capabilities(
        "demo_module",
        surface=RUNTIME_SURFACE_HOSTED_UI_DECLARE,
        ui_declaration_buffer=buffer,
    )
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

    readonly_caps = build_runtime_capabilities(
        "demo_module",
        surface=RUNTIME_SURFACE_HOSTED_UI_READONLY,
        declared_page_schemas=buffer.page_schemas,
    )
    page = readonly_caps.tools.call("ui.get_page", page_id="dashboard")
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


def test_ui_tools_stage_navigation_params_with_page_ids():
    buffer = HostedUIDeclarationBuffer()
    caps = build_runtime_capabilities(
        "demo_module",
        surface=RUNTIME_SURFACE_HOSTED_UI_DECLARE,
        ui_declaration_buffer=buffer,
    )

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

    readonly_caps = build_runtime_capabilities(
        "demo_module",
        surface=RUNTIME_SURFACE_HOSTED_UI_READONLY,
        declared_page_schemas=buffer.page_schemas,
    )
    page = readonly_caps.tools.call("ui.get_page", page_id="dashboard")

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

    buffer = HostedUIDeclarationBuffer()
    caps = build_runtime_capabilities(
        "demo_module",
        surface=RUNTIME_SURFACE_HOSTED_UI_DECLARE,
        ui_declaration_buffer=buffer,
    )
    assert caps.tools.call(
        "ui.declare_page",
        page_id="dashboard",
        schema={"type": "Page", "children": []},
    )

    assert page_calls == [("dashboard", {"type": "Page", "children": []})]
    assert buffer.page_schemas["dashboard"] == {
        "type": "Page",
        "title": "normalized:dashboard",
        "children": [],
    }


def test_ui_tools_reject_unmanaged_schema_fields():
    buffer = HostedUIDeclarationBuffer()
    caps = build_runtime_capabilities(
        "demo_module",
        surface=RUNTIME_SURFACE_HOSTED_UI_DECLARE,
        ui_declaration_buffer=buffer,
    )

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

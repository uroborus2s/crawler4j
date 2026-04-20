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


def test_runtime_tools_register_expected_surface():
    caps = build_runtime_capabilities("demo_module")

    assert caps.tools.has_tool("db.list_records") is True
    assert caps.tools.has_tool("db.replace_records") is True
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
    assert caps.tools.has_tool("ui.declare_data_table") is True
    assert caps.tools.has_tool("ui.get_data_table") is True
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
    assert {spec.name: spec.is_async for spec in specs}["db.list_records"] is False


def test_db_tools_records_and_lock_are_generic(monkeypatch):
    fake_kv = _FakeKV()
    monkeypatch.setattr("src.core.atm.runtime_capabilities.get_kv_store", lambda: fake_kv)

    caps = build_runtime_capabilities("demo_module")
    assert caps.tools.call(
        "db.replace_records",
        dataset="accounts",
        records=[
            {"id": "u1", "phone_number": "13800000001", "country_code": "86"},
            {"id": "u2", "phone_number": "13800000002", "country_code": "86"},
        ],
    )
    records = caps.tools.call("db.list_records", dataset="accounts")
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


def test_db_tools_append_and_query_events(monkeypatch):
    fake_kv = _FakeKV()
    monkeypatch.setattr("src.core.atm.runtime_capabilities.get_kv_store", lambda: fake_kv)

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
    records = caps.tools.call("db.list_records", dataset="account_events")

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


def test_ui_tools_persist_data_table_meta(monkeypatch):
    caps = build_runtime_capabilities("demo_module")
    assert caps.tools.call(
        "ui.declare_data_table",
        view_id="accounts",
        schema={
            "title": "示例账号",
            "dataset": "accounts",
            "columns": [{"key": "phone", "label": "手机号"}],
        },
    )

    meta = caps.tools.call("ui.get_data_table", view_id="accounts")
    assert meta["title"] == "示例账号"
    assert meta["dataset"] == "accounts"
    assert meta["columns"] == [{"key": "phone", "label": "手机号"}]


def test_ui_tools_reject_unmanaged_schema_fields():
    caps = build_runtime_capabilities("demo_module")

    with pytest.raises(ValueError):
        caps.tools.call(
            "ui.declare_data_table",
            view_id="accounts",
            schema={"title": "示例账号", "dataset": "other_dataset"},
        )

    with pytest.raises(ValueError):
        caps.tools.call(
            "ui.declare_data_table",
            view_id="Accounts",
            schema={"title": "示例账号"},
        )

    with pytest.raises(ValueError):
        caps.tools.call(
            "ui.declare_data_table",
            view_id="accounts",
            schema={"title": "示例账号", "unknown": True},
        )


def test_ui_tools_reject_lock_key_with_business_occupancy_column():
    caps = build_runtime_capabilities("demo_module")

    with pytest.raises(ValueError, match="lock_key"):
        caps.tools.call(
            "ui.declare_data_table",
            view_id="accounts",
            schema={
                "title": "示例账号",
                "dataset": "accounts",
                "lock_key": "phone",
                "columns": [
                    {"key": "phone", "label": "手机号"},
                    {"key": "occupied_label", "label": "占用中"},
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


def test_captcha_asset_root_prefers_bundled_resources(tmp_path, monkeypatch):
    bundled_resources = tmp_path / "resources"
    bundled_resources.mkdir()
    monkeypatch.setattr(
        runtime_capabilities,
        "get_resource_path",
        lambda relative_path: str((tmp_path / relative_path).resolve()),
    )
    runtime_capabilities._resolve_captcha_asset_root.cache_clear()

    try:
        assert runtime_capabilities._resolve_captcha_asset_root() == bundled_resources
    finally:
        runtime_capabilities._resolve_captcha_asset_root.cache_clear()


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

    monkeypatch.setattr(runtime_capabilities, "_resolve_captcha_asset_root", lambda: tmp_path)
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

    monkeypatch.setattr(runtime_capabilities, "_resolve_captcha_asset_root", lambda: tmp_path)
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

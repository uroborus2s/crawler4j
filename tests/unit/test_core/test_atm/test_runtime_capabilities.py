from types import SimpleNamespace

import pytest

from src.core.atm.runtime_capabilities import build_runtime_capabilities
from src.core.rem.ip_pool import IPEntry, IPPool


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


def test_db_capability_records_and_lock_are_generic(monkeypatch):
    fake_kv = _FakeKV()
    monkeypatch.setattr("src.core.atm.runtime_capabilities.get_kv_store", lambda: fake_kv)

    caps = build_runtime_capabilities("ctrip")
    assert caps.db.replace_records(
        "accounts",
        [
            {"id": "u1", "phone_number": "13800000001", "country_code": "86"},
            {"id": "u2", "phone_number": "13800000002", "country_code": "86"},
        ]
    )
    records = caps.db.list_records("accounts")
    assert len(records) == 2

    first = caps.db.acquire_lock("accounts", "13800000001", ttl=60, owner={"task_id": "t1", "job_id": "j1"})
    second = caps.db.acquire_lock("accounts", "13800000001", ttl=60, owner={"task_id": "t2", "job_id": "j1"})
    third = caps.db.release_lock("accounts", "13800000001")

    assert first is True
    assert second is False
    assert third is True


def test_ip_pool_capability_picks_proxy_by_criteria(monkeypatch):
    pool = IPPool(id="p1", name="pool-1")
    pool.entries = [
        IPEntry(id="ip-low", pool_id="p1", address="1.1.1.1", protocol="http", port=8001, safety_score=70, bound_count=0),
        IPEntry(id="ip-best", pool_id="p1", address="2.2.2.2", protocol="http", port=8002, safety_score=99, bound_count=0),
        IPEntry(id="ip-busy", pool_id="p1", address="3.3.3.3", protocol="http", port=8003, safety_score=95, bound_count=5),
    ]
    fake_manager = SimpleNamespace(get_pool=lambda pool_id: pool if pool_id == "p1" else None, list_pools=lambda: [pool])
    monkeypatch.setattr("src.core.atm.runtime_capabilities.get_ip_pool_manager", lambda: fake_manager)

    caps = build_runtime_capabilities("ctrip")
    selected = caps.ip_pool.pick_proxy(
        {
            "pool_id": "p1",
            "protocol": "http",
            "min_safety_score": 90,
            "max_bound_count": 2,
        }
    )

    assert selected is not None
    assert selected["id"] == "ip-best"
    assert selected["proxy_url"].startswith("http://")


@pytest.mark.asyncio
async def test_env_ops_capability_delegates_to_environment_manager(monkeypatch):
    calls: list[tuple[int, str | None, str | None]] = []

    async def _update_env(env_id: int, *, proxy_value: str | None = None, proxy_pool_id: str | None = None):
        calls.append((env_id, proxy_value, proxy_pool_id))
        return True

    fake_manager = SimpleNamespace(update_env=_update_env)
    monkeypatch.setattr("src.core.atm.runtime_capabilities.get_environment_manager", lambda: fake_manager)

    caps = build_runtime_capabilities("ctrip")
    ok = await caps.env_ops.set_proxy(12, proxy_value="http://1.1.1.1:8001", proxy_pool_id=None)

    assert ok is True
    assert calls == [(12, "http://1.1.1.1:8001", None)]


def test_ui_capability_persists_data_table_meta(monkeypatch):
    fake_kv = _FakeKV()
    monkeypatch.setattr("src.core.atm.runtime_capabilities.get_kv_store", lambda: fake_kv)

    caps = build_runtime_capabilities("ctrip")
    assert caps.ui.declare_data_table("accounts", {"title": "携程账号", "dataset": "accounts"})

    meta = caps.ui.get_data_table("accounts")
    assert meta["title"] == "携程账号"
    assert meta["dataset"] == "accounts"

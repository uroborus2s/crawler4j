"""SDK 数据能力导出与契约测试。"""

import pytest

import crawler4j_sdk
from crawler4j_sdk import DatabaseCapability, TaskContext


class _FakeDB:
    def __init__(self):
        self._records: dict[str, list[dict[str, object]]] = {}
        self._state: dict[str, object] = {}
        self._locks: set[str] = set()

    def list_records(self, dataset: str) -> list[dict[str, object]]:
        return list(self._records.get(dataset, []))

    def replace_records(self, dataset: str, records: list[dict[str, object]]) -> bool:
        self._records[dataset] = list(records)
        return True

    def acquire_lock(self, scope: str, key: str, *, ttl: int, owner=None) -> bool:  # noqa: ARG002
        lock_key = f"{scope}:{key}"
        if lock_key in self._locks:
            return False
        self._locks.add(lock_key)
        return True

    def release_lock(self, scope: str, key: str) -> bool:
        lock_key = f"{scope}:{key}"
        if lock_key not in self._locks:
            return False
        self._locks.remove(lock_key)
        return True

    def is_locked(self, scope: str, key: str) -> bool:
        return f"{scope}:{key}" in self._locks

    def get_state(self, key: str):
        return self._state.get(key)

    def set_state(self, key: str, value, ttl: int | None = None) -> bool:  # noqa: ARG002
        self._state[key] = value
        return True

    def exists_state(self, key: str) -> bool:
        return key in self._state


def test_sdk_exports_database_capability_without_legacy_dataservice():
    fake_db = _FakeDB()

    assert isinstance(fake_db, DatabaseCapability)
    assert hasattr(crawler4j_sdk, "DatabaseCapability")
    assert not hasattr(crawler4j_sdk, "DataService")

    ctx = TaskContext(env_id=1, task_name="demo", db=fake_db)
    assert ctx.db is fake_db


def test_importing_removed_dataservice_raises_import_error():
    with pytest.raises(ImportError):
        exec("from crawler4j_sdk import DataService", {})


def test_database_capability_supports_records_state_and_lock_roundtrip():
    fake_db = _FakeDB()

    assert fake_db.replace_records("orders", [{"id": "o-1"}]) is True
    assert fake_db.list_records("orders") == [{"id": "o-1"}]

    assert fake_db.set_state("demo:cursor", {"page": 2}, ttl=60) is True
    assert fake_db.get_state("demo:cursor") == {"page": 2}
    assert fake_db.exists_state("demo:cursor") is True

    assert fake_db.acquire_lock("orders", "sync", ttl=30) is True
    assert fake_db.is_locked("orders", "sync") is True
    assert fake_db.acquire_lock("orders", "sync", ttl=30) is False
    assert fake_db.release_lock("orders", "sync") is True

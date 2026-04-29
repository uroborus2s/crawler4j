import pytest

from src.core.persistence.database import init_database
from src.core.rem.ip_pool import IPEntry, IPPool, IPPoolManager, IPStrategy


@pytest.mark.asyncio
async def test_persist_entry_updates_edited_proxy_fields(monkeypatch, tmp_path):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    init_database()

    manager = IPPoolManager()
    pool = IPPool(id="pool-1", name="主池", strategy=IPStrategy.LEAST_BOUND)
    manager.add_pool(pool)

    entry = IPEntry(
        id="entry-1",
        pool_id=pool.id,
        address="1.1.1.1",
        protocol="http",
        port=8080,
        username="old-user",
        password="old-pass",
    )
    pool.add_entry(entry)
    manager._persist_entry(entry)

    entry.address = "2.2.2.2"
    entry.protocol = "socks5"
    entry.port = 1080
    entry.username = "new-user"
    entry.password = "new-pass"
    manager._persist_entry(entry)

    reloaded = IPPoolManager()
    await reloaded.startup()

    loaded_pool = reloaded.get_pool(pool.id)
    assert loaded_pool is not None
    loaded_entry = loaded_pool.get_entry(entry.id)
    assert loaded_entry is not None
    assert loaded_entry.address == "2.2.2.2"
    assert loaded_entry.protocol == "socks5"
    assert loaded_entry.port == 1080
    assert loaded_entry.username == "new-user"
    assert loaded_entry.password == "new-pass"


@pytest.mark.asyncio
async def test_ip_binding_updates_bound_count_without_binding_table(monkeypatch, tmp_path):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    init_database()

    from src.core.persistence.database import STATE_DB, get_connection

    with get_connection(STATE_DB) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'env_ip_bindings'"
        ).fetchone()
    assert table is None

    manager = IPPoolManager()
    pool = IPPool(id="pool-1", name="主池", strategy=IPStrategy.LEAST_BOUND)
    manager.add_pool(pool)
    entry = IPEntry(id="entry-1", pool_id=pool.id, address="1.1.1.1", protocol="http", port=8080)
    pool.add_entry(entry)
    manager._persist_entry(entry)

    bound = await manager.bind_ip(101, pool.id)

    assert bound is entry
    assert entry.bound_count == 1
    with get_connection(STATE_DB) as conn:
        stored_count = conn.execute(
            "SELECT bound_count FROM ip_entries WHERE id = ?",
            (entry.id,),
        ).fetchone()["bound_count"]
    assert stored_count == 1

    assert await manager.unbind_ip(101) is True
    assert entry.bound_count == 0
    with get_connection(STATE_DB) as conn:
        stored_count = conn.execute(
            "SELECT bound_count FROM ip_entries WHERE id = ?",
            (entry.id,),
        ).fetchone()["bound_count"]
    assert stored_count == 0

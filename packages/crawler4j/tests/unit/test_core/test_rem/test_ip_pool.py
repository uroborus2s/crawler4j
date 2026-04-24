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

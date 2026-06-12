import pytest

from src.core.persistence.database import STATE_DB, get_connection, init_database
from src.core.rem.ip_pool import IPEntry, IPEntryStatus, IPPool, IPPoolManager, IPStrategy


def test_least_recently_used_strategy_prefers_never_used_then_oldest():
    pool = IPPool(id="pool-1", name="主池", strategy=IPStrategy.LEAST_RECENTLY_USED)
    never_used = IPEntry(
        id="entry-never",
        pool_id=pool.id,
        address="1.1.1.1",
        protocol="http",
        port=8080,
        bound_count=9,
        created_at=300,
        last_used_at=None,
    )
    oldest = IPEntry(
        id="entry-oldest",
        pool_id=pool.id,
        address="2.2.2.2",
        protocol="http",
        port=8080,
        bound_count=3,
        created_at=200,
        last_used_at=100,
    )
    newest = IPEntry(
        id="entry-newest",
        pool_id=pool.id,
        address="3.3.3.3",
        protocol="http",
        port=8080,
        bound_count=0,
        created_at=100,
        last_used_at=200,
    )
    pool.entries = [newest, oldest, never_used]

    assert pool.select_ip() is never_used
    assert pool.select_ip(exclude_ids={never_used.id}) is oldest


def test_select_ip_skips_disabled_entries():
    pool = IPPool(id="pool-1", name="主池", strategy=IPStrategy.LEAST_RECENTLY_USED)
    disabled = IPEntry(
        id="entry-disabled",
        pool_id=pool.id,
        address="1.1.1.1",
        protocol="http",
        port=8080,
        bound_count=0,
        created_at=100,
        last_used_at=None,
        status=IPEntryStatus.DISABLED,
    )
    available = IPEntry(
        id="entry-available",
        pool_id=pool.id,
        address="2.2.2.2",
        protocol="http",
        port=8080,
        bound_count=5,
        created_at=200,
        last_used_at=100,
        status=IPEntryStatus.AVAILABLE,
    )
    pool.entries = [disabled, available]

    assert pool.select_ip() is available
    assert pool.select_ip(exclude_ids={available.id}) is None


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
async def test_persist_entry_round_trips_status(monkeypatch, tmp_path):
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
        status=IPEntryStatus.DISABLED,
    )
    pool.add_entry(entry)
    manager._persist_entry(entry)

    reloaded = IPPoolManager()
    await reloaded.startup()

    loaded_pool = reloaded.get_pool(pool.id)
    assert loaded_pool is not None
    loaded_entry = loaded_pool.get_entry(entry.id)
    assert loaded_entry is not None
    assert loaded_entry.status == IPEntryStatus.DISABLED


@pytest.mark.asyncio
async def test_bind_ip_marks_last_used_and_updated_at(monkeypatch, tmp_path):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    init_database()

    now = 1_800_000_000
    monkeypatch.setattr("src.core.rem.ip_pool.time.time", lambda: now)

    manager = IPPoolManager()
    pool = IPPool(id="pool-1", name="主池", strategy=IPStrategy.LEAST_RECENTLY_USED)
    manager.add_pool(pool)
    entry = IPEntry(
        id="entry-1",
        pool_id=pool.id,
        address="1.1.1.1",
        protocol="http",
        port=8080,
        created_at=1_700_000_000,
        updated_at=1_700_000_000,
        last_used_at=None,
    )
    pool.add_entry(entry)
    manager._persist_entry(entry)

    bound = await manager.bind_ip(101, pool.id)

    assert bound is entry
    assert entry.bound_count == 1
    assert entry.last_used_at == now
    assert entry.updated_at == now
    with get_connection(STATE_DB) as conn:
        stored = conn.execute(
            "SELECT bound_count, last_used_at, updated_at FROM ip_entries WHERE id = ?",
            (entry.id,),
        ).fetchone()
    assert dict(stored) == {
        "bound_count": 1,
        "last_used_at": now,
        "updated_at": now,
    }


def test_init_database_migrates_legacy_ip_entries_time_columns(monkeypatch, tmp_path):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    with get_connection(STATE_DB) as conn:
        conn.executescript(
            """
            CREATE TABLE ip_pools (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                strategy TEXT DEFAULT 'least_bound',
                config_json TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            );
            CREATE TABLE ip_entries (
                id TEXT PRIMARY KEY,
                pool_id TEXT NOT NULL REFERENCES ip_pools(id) ON DELETE CASCADE,
                address TEXT NOT NULL,
                protocol TEXT NOT NULL,
                port INTEGER NOT NULL,
                username TEXT,
                password TEXT,
                bound_count INTEGER DEFAULT 0,
                safety_score INTEGER DEFAULT 100,
                expires_at INTEGER,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            );
            INSERT INTO ip_pools (id, name, provider, strategy)
            VALUES ('pool-1', '主池', 'local', 'least_bound');
            INSERT INTO ip_entries (
                id, pool_id, address, protocol, port, bound_count, created_at
            )
            VALUES ('entry-1', 'pool-1', '1.1.1.1', 'http', 8080, 2, 1700000000);
            """
        )

    init_database()

    with get_connection(STATE_DB) as conn:
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(ip_entries)").fetchall()}
        stored = conn.execute(
            "SELECT bound_count, created_at, updated_at, last_used_at, status FROM ip_entries WHERE id = ?",
            ("entry-1",),
        ).fetchone()
    assert {"updated_at", "last_used_at", "status"} <= columns
    assert stored["bound_count"] == 2
    assert stored["created_at"] == 1_700_000_000
    assert stored["updated_at"] is not None
    assert stored["last_used_at"] is None
    assert stored["status"] == IPEntryStatus.AVAILABLE.value


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


@pytest.mark.asyncio
async def test_bind_ip_keeps_existing_binding_when_no_available_candidate(monkeypatch, tmp_path):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    init_database()

    manager = IPPoolManager()
    pool = IPPool(id="pool-1", name="主池", strategy=IPStrategy.LEAST_RECENTLY_USED)
    manager.add_pool(pool)
    entry = IPEntry(
        id="entry-1",
        pool_id=pool.id,
        address="1.1.1.1",
        protocol="http",
        port=8080,
        bound_count=1,
        status=IPEntryStatus.DISABLED,
    )
    pool.add_entry(entry)
    manager._persist_entry(entry)
    manager._env_bindings[101] = entry.id

    bound = await manager.bind_ip(101, pool.id)

    assert bound is None
    assert manager.get_bound_ip(101) is entry
    assert entry.bound_count == 1
    with get_connection(STATE_DB) as conn:
        stored = conn.execute(
            "SELECT bound_count, status FROM ip_entries WHERE id = ?",
            (entry.id,),
        ).fetchone()
    assert dict(stored) == {
        "bound_count": 1,
        "status": IPEntryStatus.DISABLED.value,
    }


def test_set_entry_status_updates_memory_and_database(monkeypatch, tmp_path):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    init_database()

    manager = IPPoolManager()
    pool = IPPool(id="pool-1", name="主池", strategy=IPStrategy.LEAST_BOUND)
    manager.add_pool(pool)
    entry = IPEntry(id="entry-1", pool_id=pool.id, address="1.1.1.1", protocol="http", port=8080)
    pool.add_entry(entry)
    manager._persist_entry(entry)

    assert manager.set_entry_status(entry.id, IPEntryStatus.DISABLED) is True

    assert entry.status == IPEntryStatus.DISABLED
    with get_connection(STATE_DB) as conn:
        stored_status = conn.execute(
            "SELECT status FROM ip_entries WHERE id = ?",
            (entry.id,),
        ).fetchone()["status"]
    assert stored_status == IPEntryStatus.DISABLED.value

import sqlite3
from unittest.mock import patch


def _create_legacy_state_db_with_obsolete_provider_columns(db_path):
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE environments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            kind TEXT NOT NULL,
            provider TEXT NOT NULL,
            status TEXT NOT NULL,
            external_id TEXT,
            lease_id TEXT,
            task_run_id TEXT,
            last_used_at INTEGER,
            daily_usage_count INTEGER DEFAULT 0,
            daily_usage_date TEXT,
            proxy_config_json TEXT,
            provider_env_id TEXT,
            provider_env_name TEXT,
            provider_group TEXT,
            provider_proxy TEXT,
            provider_raw_meta TEXT,
            imported_at INTEGER,
            capabilities TEXT,
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            updated_at INTEGER DEFAULT (strftime('%s', 'now'))
        );
        INSERT INTO environments (
            name, kind, provider, status, external_id,
            provider_env_id, provider_env_name, provider_group,
            provider_proxy, provider_raw_meta, imported_at, capabilities
        )
        VALUES
            ('same-name', 'browser', 'virtualbrowser', 'ready', 'vb-101', 'vb-101', 'same-name', 'g1', '{}', '{}', 1, '{}'),
            ('same-name', 'browser', 'virtualbrowser', 'ready', 'vb-202', 'vb-202', 'same-name', 'g2', '{}', '{}', 2, '{}'),
            ('same-id-different-name', 'browser', 'virtualbrowser', 'ready', 'vb-101', 'vb-101', 'same-id-different-name', 'g3', '{}', '{}', 3, '{}'),
            ('same-name', 'browser', 'bitbrowser', 'ready', 'vb-101', 'vb-101', 'same-name', 'g4', '{}', '{}', 4, '{}');
        """
    )
    conn.commit()
    conn.close()


def test_init_database_removes_provider_import_columns_and_indexes_provider_name(tmp_path):
    _create_legacy_state_db_with_obsolete_provider_columns(tmp_path / "state.db")

    with patch("src.utils.paths.get_app_data_dir", return_value=tmp_path):
        from src.core.persistence.database import STATE_DB, get_connection, init_database

        init_database()

        with get_connection(STATE_DB) as conn:
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(environments)").fetchall()
            }
            duplicate_rows = conn.execute(
                """
                SELECT id, provider, name, external_id
                FROM environments
                WHERE provider = 'virtualbrowser'
                ORDER BY id
                """
            ).fetchall()
            other_provider = conn.execute(
                """
                SELECT name
                FROM environments
                WHERE provider = 'bitbrowser'
                """
            ).fetchone()
            index_info = conn.execute("PRAGMA index_info(idx_env_provider_name)").fetchall()

    assert {
        "provider_env_id",
        "provider_env_name",
        "provider_group",
        "provider_proxy",
        "provider_raw_meta",
        "imported_at",
    }.isdisjoint(columns)
    assert [row["name"] for row in duplicate_rows] == [
        "same-name",
        None,
        "same-id-different-name",
    ]
    assert [row["external_id"] for row in duplicate_rows] == ["vb-101", "vb-202", "vb-101"]
    assert other_provider["name"] == "same-name"
    assert [row["name"] for row in index_info] == ["provider", "name"]


def test_environment_uniqueness_uses_provider_and_name(tmp_path):
    with patch("src.utils.paths.get_app_data_dir", return_value=tmp_path):
        from src.core.persistence.database import STATE_DB, get_connection, init_database

        init_database()

        with get_connection(STATE_DB) as conn:
            conn.execute(
                """
                INSERT INTO environments (name, kind, provider, status, external_id, capabilities)
                VALUES ('same-name', 'browser', 'virtualbrowser', 'ready', 'vb-101', '{}')
                """
            )
            conn.execute(
                """
                INSERT INTO environments (name, kind, provider, status, external_id, capabilities)
                VALUES ('same-name', 'browser', 'bitbrowser', 'ready', 'bb-101', '{}')
                """
            )
            try:
                conn.execute(
                    """
                    INSERT INTO environments (name, kind, provider, status, external_id, capabilities)
                    VALUES ('same-name', 'browser', 'virtualbrowser', 'ready', 'vb-202', '{}')
                    """
                )
            except sqlite3.IntegrityError:
                duplicate_rejected = True
            else:
                duplicate_rejected = False

    assert duplicate_rejected is True

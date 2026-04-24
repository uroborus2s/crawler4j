import sqlite3
from unittest.mock import patch


def _create_legacy_state_db_with_duplicate_names_and_external_ids(db_path):
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
            capabilities TEXT,
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            updated_at INTEGER DEFAULT (strftime('%s', 'now'))
        );
        INSERT INTO environments (name, kind, provider, status, external_id, capabilities)
        VALUES
            ('same-name', 'browser', 'virtualbrowser', 'ready', 'vb-101', '{}'),
            ('same-name', 'browser', 'virtualbrowser', 'ready', 'vb-202', '{}'),
            ('same-id-different-name', 'browser', 'virtualbrowser', 'ready', 'vb-101', '{}'),
            ('same-name', 'browser', 'bitbrowser', 'ready', 'vb-101', '{}');
        """
    )
    conn.commit()
    conn.close()


def test_init_database_deduplicates_legacy_environment_provider_names(tmp_path):
    _create_legacy_state_db_with_duplicate_names_and_external_ids(tmp_path / "state.db")

    with patch("src.utils.paths.get_app_data_dir", return_value=tmp_path):
        from src.core.persistence.database import STATE_DB, get_connection, init_database

        init_database()

        with get_connection(STATE_DB) as conn:
            duplicate_rows = conn.execute(
                """
                SELECT id, provider, name, external_id, provider_env_id, provider_env_name
                FROM environments
                WHERE provider = 'virtualbrowser'
                ORDER BY id
                """
            ).fetchall()
            other_provider = conn.execute(
                """
                SELECT provider_env_name
                FROM environments
                WHERE provider = 'bitbrowser'
                """
            ).fetchone()
            index_info = conn.execute("PRAGMA index_info(idx_env_provider_source_key)").fetchall()

    assert [row["provider_env_id"] for row in duplicate_rows] == ["vb-101", "vb-202", "vb-101"]
    assert [row["provider_env_name"] for row in duplicate_rows] == [
        "same-name",
        None,
        "same-id-different-name",
    ]
    assert other_provider["provider_env_name"] == "same-name"
    assert [row["name"] for row in index_info] == ["provider", "provider_env_name"]

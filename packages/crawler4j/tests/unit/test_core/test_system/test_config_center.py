from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path: Path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


def test_config_center_reads_defaults_and_persists_typed_values():
    from src.core.system.config_center import get_config_center

    config = get_config_center()

    assert config.get("browser.virtualbrowser.port") == 9002
    assert config.get("atm.default_execution_timeout_seconds") == 600
    assert config.get("atm.env_recycle_timeout_seconds") == 60
    with pytest.raises(KeyError):
        config.registry.get_item("system.autostart")
    with pytest.raises(KeyError):
        config.registry.get_item("system.minimize_on_start")

    config.set("browser.virtualbrowser.port", 9100)
    config.set("network.proxy_mode", "manual")

    assert config.get("browser.virtualbrowser.port") == 9100
    assert config.get("network.proxy_mode") == "manual"

    from src.core.persistence.database import CONFIG_DB, get_connection

    with get_connection(CONFIG_DB) as conn:
        rows = conn.execute(
            """
            SELECT namespace, scope_type, scope_name, key_path, value_json, value_type
            FROM config_entries
            ORDER BY namespace, key_path
            """
        ).fetchall()

    assert {
        (row["namespace"], row["scope_type"], row["scope_name"], row["key_path"], row["value_type"])
        for row in rows
    } >= {
        ("browser.virtualbrowser", "global", "", "port", "int"),
        ("network", "global", "", "proxy_mode", "string"),
    }


def test_config_center_validates_ranges_and_choices():
    from src.core.system.config_center import ConfigValidationError, get_config_center

    config = get_config_center()

    with pytest.raises(ConfigValidationError):
        config.set("atm.env_recycle_timeout_seconds", 0)

    with pytest.raises(ConfigValidationError):
        config.set("network.proxy_mode", "bad-mode")


def test_config_center_emits_change_events(qtbot):
    from src.core.system.config_center import get_config_center

    config = get_config_center()
    observed: list[tuple[str, object, str]] = []
    config.config_changed.connect(lambda key, value, effect: observed.append((key, value, effect)))

    config.set("logging.level", "DEBUG")

    assert observed == [("logging.level", "DEBUG", "immediate")]


def test_init_database_migrates_legacy_settings_table_to_config_entries(tmp_path: Path):
    from src.core.persistence.database import CONFIG_DB, get_connection, get_db_path, init_database

    db_path = get_db_path(CONFIG_DB)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    import sqlite3

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at INTEGER)")
        conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("browser.virtualbrowser.port", "9102", 1),
        )
        conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("mms.github.repo_token.owner__repo", '{"ciphertext":"encrypted"}', 2),
        )
        conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("system.autostart", "true", 3),
        )
        conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            ("system.minimize_on_start", "true", 4),
        )
        conn.commit()

    init_database()

    with get_connection(CONFIG_DB) as conn:
        settings_row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'settings'"
        ).fetchone()
        rows = conn.execute(
            """
            SELECT namespace, key_path, value_json
            FROM config_entries
            ORDER BY namespace, key_path
            """
        ).fetchall()

    assert settings_row is None
    assert [(row["namespace"], row["key_path"], row["value_json"]) for row in rows] == [
        ("browser.virtualbrowser", "port", "9102"),
        ("mms.github", "repo_token.owner__repo", '{"ciphertext":"encrypted"}'),
    ]

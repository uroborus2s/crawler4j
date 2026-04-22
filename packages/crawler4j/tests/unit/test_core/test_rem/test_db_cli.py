from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_db_cli_module():
    repo_root = Path(__file__).resolve().parents[6]
    module_path = repo_root / "scripts" / "db_cli.py"
    spec = importlib.util.spec_from_file_location("test_db_cli_module", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reset_database_deletes_all_workspace_databases(monkeypatch, tmp_path):
    db_cli = _load_db_cli_module()

    from src.core.persistence import database as database_module

    db_paths = {
        "config.db": tmp_path / "config.db",
        "state.db": tmp_path / "state.db",
        "data.db": tmp_path / "data.db",
    }
    for path in db_paths.values():
        path.write_text("placeholder", encoding="utf-8")

    monkeypatch.setattr(database_module, "get_db_path", lambda db_name: db_paths[db_name])

    initialized = {"called": False}

    def _fake_init_database() -> None:
        initialized["called"] = True

    monkeypatch.setattr(database_module, "init_database", _fake_init_database)

    db_cli.reset_database()

    assert initialized["called"] is True
    assert all(not path.exists() for path in db_paths.values())

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.mms.models import ModuleStatus
from src.core.mms.registry import ModuleRegistry
from src.core.mms.scanner import ModuleScanner


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        stack.enter_context(patch("src.core.mms.registry.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


class _FakeDevLinkStore:
    def list_links(self) -> list[object]:
        return []

    def delete_link(self, module_name: str) -> bool:  # noqa: ARG002
        return False


def _write_module(root: Path, name: str = "demo_module") -> Path:
    module_dir = root / name
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "module.yaml").write_text(
        "name: {name}\n"
        "version: 1.0.0\n"
        "upgrade_source:\n"
        "  type: github_release\n"
        "  repo: example/{name}\n".format(name=name),
        encoding="utf-8",
    )
    (module_dir / "__init__.py").write_text("VALUE = 'demo'\n", encoding="utf-8")
    return module_dir


def test_settings_store_reads_writes_and_exports_module_and_workflow_settings(temp_data_dir):
    from src.core.mms.settings_store import ModuleSettingsStore

    store = ModuleSettingsStore()

    store.write_module_settings("demo_module", {"api_key": "secret", "enabled": True})
    store.write_workflow_settings("demo_module", "login", {"headless": False})
    store.write_workflow_settings("demo_module", "search", {"limit": 10})

    assert store.read_module_settings("demo_module") == {"api_key": "secret", "enabled": True}
    assert store.read_workflow_settings("demo_module", "login") == {"headless": False}
    assert store.read_workflow_settings("demo_module", "search") == {"limit": 10}
    assert store.export_module_settings("demo_module") == {
        "module": {"api_key": "secret", "enabled": True},
        "workflows": {
            "login": {"headless": False},
            "search": {"limit": 10},
        },
    }


def test_settings_store_returns_empty_module_settings_without_persisted_record(temp_data_dir):
    from src.core.mms.settings_store import ModuleSettingsStore

    store = ModuleSettingsStore()

    assert store.read_module_settings("demo_module") == {}


def test_settings_store_persists_flattened_entries_in_module_config_table(temp_data_dir):
    from src.core.mms.settings_store import ModuleSettingsStore
    from src.core.persistence.database import CONFIG_DB, get_connection

    store = ModuleSettingsStore()
    store.write_module_settings(
        "demo_module",
        {
            "auth": {"login_url": "https://example.com", "headless": False},
            "accounts": [{"id": "u1"}],
        },
    )

    with get_connection(CONFIG_DB) as conn:
        rows = conn.execute(
            """
            SELECT scope_type, scope_name, key_path, value_json
            FROM module_config_entries
            WHERE module_name = ?
            ORDER BY scope_type, scope_name, key_path
            """,
            ("demo_module",),
        ).fetchall()

    assert [(row["scope_type"], row["scope_name"], row["key_path"], row["value_json"]) for row in rows] == [
        ("module", "", "accounts", '[{"id": "u1"}]'),
        ("module", "", "auth.headless", "false"),
        ("module", "", "auth.login_url", '"https://example.com"'),
    ]


def test_settings_store_initializes_defaults_once_and_marks_module(temp_data_dir):
    from src.core.mms.settings_store import ModuleSettingsStore

    store = ModuleSettingsStore()

    changed = store.ensure_config_defaults_initialized(
        "demo_module",
        {"base_url": "https://example.com", "retry": 3},
        {"default": {"headless": False}},
    )

    assert changed is True
    assert store.export_module_settings("demo_module") == {
        "module": {"base_url": "https://example.com", "retry": 3},
        "workflows": {"default": {"headless": False}},
    }
    assert store.is_config_defaults_initialized("demo_module") is True

    changed = store.ensure_config_defaults_initialized(
        "demo_module",
        {"base_url": "https://changed.example.com"},
        {"default": {"headless": True}},
    )

    assert changed is False
    assert store.export_module_settings("demo_module") == {
        "module": {"base_url": "https://example.com", "retry": 3},
        "workflows": {"default": {"headless": False}},
    }


def test_settings_store_marks_existing_settings_as_initialized_without_overwriting(temp_data_dir):
    from src.core.mms.settings_store import ModuleSettingsStore

    store = ModuleSettingsStore()
    store.write_module_settings("demo_module", {"base_url": "https://custom.example.com"})
    store.write_workflow_settings("demo_module", "default", {"headless": True})

    changed = store.ensure_config_defaults_initialized(
        "demo_module",
        {"base_url": "https://default.example.com", "retry": 3},
        {"default": {"headless": False}},
    )

    assert changed is False
    assert store.export_module_settings("demo_module") == {
        "module": {"base_url": "https://custom.example.com"},
        "workflows": {"default": {"headless": True}},
    }
    assert store.is_config_defaults_initialized("demo_module") is True


def test_settings_store_ignores_legacy_configs_rows(temp_data_dir):
    from src.core.mms.settings_store import ModuleSettingsStore
    from src.core.persistence.database import CONFIG_DB, get_connection

    with get_connection(CONFIG_DB) as conn:
        conn.execute(
            """
            INSERT INTO configs (key, value, created_at, updated_at)
            VALUES (?, ?, 1, 1)
            """,
            (
                "mms:module_settings:demo_module",
                '{"auth": {"login_url": "https://legacy.example.com"}}',
            ),
        )
        conn.execute(
            """
            INSERT INTO configs (key, value, created_at, updated_at)
            VALUES (?, ?, 1, 1)
            """,
            (
                "mms:workflow_settings:demo_module:login",
                '{"auth": {"headless": true}}',
            ),
        )
        conn.execute(
            """
            INSERT INTO configs (key, value, created_at, updated_at)
            VALUES (?, ?, 1, 1)
            """,
            (
                "mms:module_status:demo_module",
                '"disabled"',
            ),
        )

    store = ModuleSettingsStore()

    assert store.read_module_settings("demo_module") == {}
    assert store.read_workflow_settings("demo_module", "login") == {}
    assert store.build_task_config("demo_module", "login") == {}
    assert store.get_module_status("demo_module") is None


def test_registry_persists_module_status_across_reload(temp_data_dir):
    from src.core.mms.settings_store import ModuleSettingsStore
    from src.core.persistence.database import CONFIG_DB, get_connection

    scan_root = temp_data_dir / "scan_root"
    _write_module(scan_root)
    store = ModuleSettingsStore()

    registry = ModuleRegistry(
        scanner=ModuleScanner(scan_paths=[scan_root]),
        dev_link_store=_FakeDevLinkStore(),
        settings_store=store,
    )

    assert registry.get_module("demo_module").status == ModuleStatus.ENABLED
    assert registry.disable_module("demo_module") is True

    reloaded = ModuleRegistry(
        scanner=ModuleScanner(scan_paths=[scan_root]),
        dev_link_store=_FakeDevLinkStore(),
        settings_store=store,
    )
    assert reloaded.get_module("demo_module").status == ModuleStatus.DISABLED

    with get_connection(CONFIG_DB) as conn:
        rows = conn.execute(
            """
            SELECT scope_type, key_path, value_json
            FROM module_config_entries
            WHERE module_name = ?
            ORDER BY scope_type, key_path
            """,
            ("demo_module",),
        ).fetchall()

    assert [(row["scope_type"], row["key_path"], row["value_json"]) for row in rows] == [
        ("config_defaults_init", "initialized", "true"),
        ("module_status", "status", '"disabled"'),
    ]

    assert reloaded.enable_module("demo_module") is True
    enabled_again = ModuleRegistry(
        scanner=ModuleScanner(scan_paths=[scan_root]),
        dev_link_store=_FakeDevLinkStore(),
        settings_store=store,
    )
    assert enabled_again.get_module("demo_module").status == ModuleStatus.ENABLED


def test_registry_initializes_manifest_config_defaults_only_on_first_load(temp_data_dir):
    from src.core.mms.settings_store import ModuleSettingsStore

    scan_root = temp_data_dir / "scan_root"
    module_dir = _write_module(scan_root)
    (module_dir / "module.yaml").write_text(
        """
name: demo_module
version: 1.0.0
upgrade_source:
  type: github_release
  repo: example/demo_module
workflows:
  - name: default
config_defaults:
  module:
    base_url: https://example.com
    retry: 3
  workflows:
    default:
      headless: false
""".strip(),
        encoding="utf-8",
    )

    store = ModuleSettingsStore()
    registry = ModuleRegistry(
        scanner=ModuleScanner(scan_paths=[scan_root]),
        dev_link_store=_FakeDevLinkStore(),
        settings_store=store,
    )

    registry.get_module("demo_module")
    assert store.export_module_settings("demo_module") == {
        "module": {"base_url": "https://example.com", "retry": 3},
        "workflows": {"default": {"headless": False}},
    }

    (module_dir / "module.yaml").write_text(
        """
name: demo_module
version: 1.0.1
upgrade_source:
  type: github_release
  repo: example/demo_module
workflows:
  - name: default
config_defaults:
  module:
    base_url: https://changed.example.com
    retry: 5
  workflows:
    default:
      headless: true
""".strip(),
        encoding="utf-8",
    )

    registry.refresh()
    assert store.export_module_settings("demo_module") == {
        "module": {"base_url": "https://example.com", "retry": 3},
        "workflows": {"default": {"headless": False}},
    }


def test_uninstall_clears_settings_by_default_and_can_keep_them(temp_data_dir):
    from src.core.mms.settings_store import ModuleSettingsStore
    from src.core.persistence.module_data_store import ModuleDataStore

    scan_root = temp_data_dir / "scan_root"
    _write_module(scan_root)
    store = ModuleSettingsStore()
    data_store = ModuleDataStore()
    store.write_module_settings("demo_module", {"api_key": "secret"})
    store.write_workflow_settings("demo_module", "login", {"headless": False})
    data_store.write_dataset("demo_module", "accounts", [{"id": "u1"}])
    data_store.write_data_table_schema("demo_module", "accounts", {"title": "账号管理", "dataset": "accounts"})

    registry = ModuleRegistry(
        scanner=ModuleScanner(scan_paths=[scan_root]),
        dev_link_store=_FakeDevLinkStore(),
        settings_store=store,
    )
    assert registry.uninstall("demo_module") is True
    assert store.export_module_settings("demo_module") == {"module": {}, "workflows": {}}
    assert data_store.read_dataset("demo_module", "accounts") == []
    assert data_store.read_data_table_schema("demo_module", "accounts") == {}

    _write_module(scan_root)
    store.write_module_settings("demo_module", {"api_key": "secret"})
    store.write_workflow_settings("demo_module", "login", {"headless": False})
    data_store.write_dataset("demo_module", "accounts", [{"id": "u2"}])
    data_store.write_data_table_schema("demo_module", "accounts", {"title": "账号管理", "dataset": "accounts"})
    registry = ModuleRegistry(
        scanner=ModuleScanner(scan_paths=[scan_root]),
        dev_link_store=_FakeDevLinkStore(),
        settings_store=store,
    )

    assert registry.uninstall("demo_module", keep_settings=True) is True
    assert store.export_module_settings("demo_module") == {
        "module": {"api_key": "secret"},
        "workflows": {"login": {"headless": False}},
    }
    assert data_store.read_dataset("demo_module", "accounts") == []
    assert data_store.read_data_table_schema("demo_module", "accounts") == {}

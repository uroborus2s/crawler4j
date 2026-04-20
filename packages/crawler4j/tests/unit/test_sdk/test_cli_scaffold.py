"""CLI scaffold tests for the refactored crawler4j SDK command tree."""

from __future__ import annotations

import builtins
import importlib
import sys
import tomllib
from argparse import Namespace
from pathlib import Path

import pytest
import yaml

from crawler4j_sdk._version import get_compatible_dependency_spec
from crawler4j_sdk.cli import commands


def _import_generated_package(package_root: Path):
    package_name = package_root.name
    parent = str(package_root.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    stale = [name for name in sys.modules if name == package_name or name.startswith(f"{package_name}.")]
    for name in stale:
        sys.modules.pop(name, None)

    return importlib.import_module(package_name)


def _read_manifest(module_root: Path) -> dict:
    with (module_root / "module.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture
def module_root(tmp_path: Path) -> Path:
    target = tmp_path / "demo_model"
    args = Namespace(
        name="demo_model",
        repo="demo/demo_model",
        output=str(target),
        display_name=None,
        description=None,
        version="0.1.0",
        workflow_name="main_workflow",
        workflow_display_name=None,
        workflow_description=None,
        python_version="3.12",
        no_git=True,
        no_install=True,
        force=False,
    )
    assert commands.cmd_module_init(args) == 0
    return target


def test_module_init_creates_complete_project(module_root: Path):
    assert (module_root / "__init__.py").exists()
    assert (module_root / "module_runtime.py").exists()
    assert (module_root / "module.yaml").exists()
    assert (module_root / "pyproject.toml").exists()
    assert (module_root / "README.md").exists()
    assert (module_root / ".gitignore").exists()
    assert (module_root / ".python-version").exists()
    assert (module_root / "tasks" / "example_task.py").exists()
    assert (module_root / "workflows" / "main_workflow.py").exists()
    assert (module_root / "ui" / "__init__.py").exists()
    assert not (module_root / "data").exists()

    manifest = _read_manifest(module_root)
    assert manifest["name"] == "demo_model"
    assert manifest["version"] == "0.1.0"
    assert manifest["upgrade_source"] == {
        "type": "github_release",
        "repo": "demo/demo_model",
        "allow_prerelease": False,
    }
    assert manifest["config_defaults"] == {"module": {}, "workflows": {}}
    assert manifest["workflows"] == [
        {
            "name": "main_workflow",
            "display_name": "Main Workflow",
            "description": "Main Workflow 工作流",
        }
    ]
    assert "ui_extension" not in manifest


def test_module_init_generates_importable_package(module_root: Path):
    module = _import_generated_package(module_root)

    assert hasattr(module, "run")
    assert hasattr(module, "prepare_env")
    assert hasattr(module, "select_env")
    assert hasattr(module, "declare_ui")
    assert "example_task" in module.assembler.task_scripts
    assert "main_workflow" in module.assembler.workflows
    assert [selector.name for selector in module.assembler.list_env_selectors()] == [
        "random_ready",
        "return_none",
    ]


def test_generated_pyproject_uses_sdk_dependency_range(module_root: Path):
    with (module_root / "pyproject.toml").open("rb") as fh:
        pyproject = tomllib.load(fh)

    assert get_compatible_dependency_spec() == "crawler4j-sdk>=0.3.0,<0.4.0"
    assert get_compatible_dependency_spec() in pyproject["project"]["dependencies"]
    assert "scripts" not in pyproject["project"]


def test_module_set_commands_update_manifest_and_runtime(module_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(module_root)

    assert commands.cmd_workflow_create(
        Namespace(name="repair_orders", display_name=None, description=None, force=False)
    ) == 0
    assert commands.cmd_module_set_repo(Namespace(repo="demo/release_repo")) == 0
    assert commands.cmd_module_set_version(Namespace(version="0.2.0")) == 0
    assert commands.cmd_module_set_default_workflow(Namespace(workflow="repair_orders")) == 0

    manifest = _read_manifest(module_root)
    assert manifest["upgrade_source"]["repo"] == "demo/release_repo"
    assert manifest["version"] == "0.2.0"
    runtime_text = (module_root / "module_runtime.py").read_text(encoding="utf-8")
    assert 'DEFAULT_WORKFLOW = "repair_orders"' in runtime_text


def test_resource_commands_create_files_and_update_manifest(
    module_root: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(module_root)

    assert commands.cmd_task_create(Namespace(name="extra_task", force=False)) == 0
    assert commands.cmd_workflow_create(
        Namespace(name="repair_orders", display_name=None, description=None, force=False)
    ) == 0
    assert commands.cmd_page_create(
        Namespace(name="dashboard", display_name=None, description=None, force=False)
    ) == 0
    assert commands.cmd_data_table_create(Namespace(view_id="accounts", label=None, icon=None)) == 0
    assert commands.cmd_env_selector_create(
        Namespace(name="pick_ready", display_name=None, description=None)
    ) == 0

    assert (module_root / "tasks" / "extra_task.py").exists()
    assert (module_root / "workflows" / "repair_orders.py").exists()
    assert (module_root / "ui" / "dashboard.py").exists()

    ui_init = (module_root / "ui" / "__init__.py").read_text(encoding="utf-8")
    assert "from .dashboard import DashboardPage" in ui_init

    manifest = _read_manifest(module_root)
    assert [item["name"] for item in manifest["workflows"]] == ["main_workflow", "repair_orders"]
    assert manifest["ui_extension"]["type"] == "micro_app"
    assert manifest["ui_extension"]["entry"] == "ui:DashboardPage"
    assert manifest["ui_extension"]["detail_menu"] == [
        {
            "id": "accounts",
            "label": "Accounts",
            "icon": "📋",
            "entry": "core:data_table:accounts",
        }
    ]

    runtime_text = (module_root / "module_runtime.py").read_text(encoding="utf-8")
    assert "_declare_accounts_table" in runtime_text
    assert "_declare_accounts_table(context)" in runtime_text
    assert 'name="pick_ready"' in runtime_text


def test_page_scaffold_stays_importable_without_pyqt6(module_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(module_root)
    assert commands.cmd_page_create(
        Namespace(name="dashboard", display_name=None, description=None, force=False)
    ) == 0

    generated_page = (module_root / "ui" / "dashboard.py").read_text(encoding="utf-8")
    assert "except ModuleNotFoundError as exc" in generated_page
    assert "PyQt6 is required to instantiate code pages" in generated_page

    manifest = _read_manifest(module_root)
    package_name = module_root.name
    stale = [name for name in sys.modules if name == package_name or name.startswith(f"{package_name}.")]
    for name in stale:
        sys.modules.pop(name, None)

    real_import = builtins.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "PyQt6.QtWidgets":
            raise ModuleNotFoundError("No module named 'PyQt6'")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    assert commands.collect_full_errors(module_root, manifest) == []


def test_task_create_refuses_to_clobber_existing_files(module_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(module_root)

    assert commands.cmd_task_create(Namespace(name="sync_orders", force=False)) == 0
    assert commands.cmd_task_create(Namespace(name="sync_orders", force=False)) == 1
    assert commands.cmd_task_create(Namespace(name="sync_orders", force=True)) == 0


def test_config_commands_update_manifest_and_lint(module_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(module_root)

    module_defaults = tmp_path / "module_defaults.yaml"
    workflow_defaults = tmp_path / "workflow_defaults.yaml"
    module_defaults.write_text("base_url: https://example.com\nenabled: true\n", encoding="utf-8")
    workflow_defaults.write_text("limit: 20\n", encoding="utf-8")

    assert commands.cmd_config_set_module(Namespace(file=str(module_defaults))) == 0
    assert commands.cmd_config_set_workflow(
        Namespace(workflow="main_workflow", file=str(workflow_defaults))
    ) == 0
    assert commands.cmd_config_lint(Namespace()) == 0

    manifest = _read_manifest(module_root)
    assert manifest["config_defaults"]["module"] == {
        "base_url": "https://example.com",
        "enabled": True,
    }
    assert manifest["config_defaults"]["workflows"]["main_workflow"] == {"limit": 20}


def test_check_full_passes_for_fresh_scaffold(module_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(module_root)
    assert commands.cmd_check_full(Namespace()) == 0


def test_check_rejects_missing_module_runtime(module_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(module_root)
    (module_root / "module_runtime.py").unlink()

    assert commands.cmd_check_structure(Namespace()) == 1


def test_check_rejects_undeclared_workflow_defaults(module_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(module_root)
    manifest = _read_manifest(module_root)
    manifest["config_defaults"]["workflows"]["missing_workflow"] = {"limit": 1}
    (module_root / "module.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    assert commands.cmd_check_release(Namespace()) == 1


def test_check_rejects_unregistered_workflow_file(module_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(module_root)
    (module_root / "workflows" / "rogue.py").write_text("# rogue workflow\n", encoding="utf-8")

    assert commands.cmd_check_structure(Namespace()) == 1


def test_check_full_reports_module_runtime_import_error(
    module_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.chdir(module_root)
    (module_root / "module_runtime.py").write_text(
        "from missing_runtime_dependency import nope\n",
        encoding="utf-8",
    )

    assert commands.cmd_check_full(Namespace()) == 1

    captured = capsys.readouterr()
    assert "module_runtime.py 无法导入" in captured.out


def test_check_full_reports_ui_import_error(
    module_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.chdir(module_root)
    assert commands.cmd_page_create(
        Namespace(name="dashboard", display_name=None, description=None, force=False)
    ) == 0
    (module_root / "ui" / "__init__.py").write_text(
        "from missing_ui_dependency import BrokenPage\n",
        encoding="utf-8",
    )

    assert commands.cmd_check_full(Namespace()) == 1

    captured = capsys.readouterr()
    assert "ui 包无法导入" in captured.out


def test_check_full_rejects_lock_key_business_occupancy_conflict(
    module_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.chdir(module_root)
    runtime_path = module_root / "module_runtime.py"
    runtime_text = runtime_path.read_text(encoding="utf-8")
    runtime_path.write_text(
        runtime_text.replace(
            "# SDK-DATA-TABLES\n    return None",
            """context.tools.call(
        "ui.declare_data_table",
        view_id="accounts",
        schema={
            "title": "账号管理",
            "dataset": "accounts",
            "lock_key": "phone",
            "columns": [
                {"key": "phone", "label": "手机号"},
                {"key": "occupied_label", "label": "占用中"},
            ],
        },
    )
    return None""",
        ),
        encoding="utf-8",
    )

    assert commands.cmd_check_full(Namespace()) == 1

    captured = capsys.readouterr()
    assert "误用 lock_key" in captured.out


def test_check_full_rejects_audit_event_writes_in_declare_ui(
    module_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.chdir(module_root)
    runtime_path = module_root / "module_runtime.py"
    runtime_text = runtime_path.read_text(encoding="utf-8")
    runtime_path.write_text(
        runtime_text.replace(
            "# SDK-DATA-TABLES\n    return None",
            """context.tools.call(
        "db.append_event",
        dataset="account_events",
        event_type="declare_ui_checked",
        entity_key="demo-account",
        payload={"source": "sdk_check"},
        created_at=1,
    )
    context.tools.call(
        "db.query_events",
        dataset="account_events",
        entity_key="demo-account",
        limit=10,
    )
    return None""",
        ),
        encoding="utf-8",
    )

    assert commands.cmd_check_full(Namespace()) == 1

    captured = capsys.readouterr()
    assert "declare_ui 不允许调用 db.append_event" in captured.out


def test_check_full_rejects_audit_event_writes_in_declare_ui_after_list_tools_discovery(
    module_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.chdir(module_root)
    runtime_path = module_root / "module_runtime.py"
    runtime_text = runtime_path.read_text(encoding="utf-8")
    runtime_path.write_text(
        runtime_text.replace(
            "# SDK-DATA-TABLES\n    return None",
            """tool_names = {spec.name for spec in context.tools.list_tools()}
    if "db.append_event" in tool_names:
        context.tools.call(
            "db.append_event",
            dataset="account_events",
            event_type="declare_ui_checked",
            entity_key="demo-account",
            reason="sdk_check",
            created_at=1,
        )
    return None""",
        ),
        encoding="utf-8",
    )

    assert commands.cmd_check_full(Namespace()) == 1

    captured = capsys.readouterr()
    assert "declare_ui 不允许调用 db.append_event" in captured.out


def test_check_full_accepts_audit_event_queries_in_declare_ui(
    module_root: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(module_root)
    runtime_path = module_root / "module_runtime.py"
    runtime_text = runtime_path.read_text(encoding="utf-8")
    runtime_path.write_text(
        runtime_text.replace(
            "# SDK-DATA-TABLES\n    return None",
            """context.tools.call(
        "db.query_events",
        dataset="account_events",
        entity_key="demo-account",
        limit=10,
    )
    return None""",
        ),
        encoding="utf-8",
    )

    assert commands.cmd_check_full(Namespace()) == 0


def test_package_build_and_verify(module_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(module_root)

    build_result = commands.cmd_package_build(Namespace(output=None))
    assert build_result == 0

    archive = module_root / "dist" / "demo_model-0.1.0.zip"
    assert archive.exists()
    assert commands.cmd_package_verify(Namespace(archive=str(archive))) == 0


@pytest.mark.parametrize(
    "argv",
    [
        ["crawler4j", "init-model", "demo_model"],
        ["crawler4j", "add", "task_name"],
        ["crawler4j", "new", "task_name"],
        ["crawler4j", "list"],
        ["crawler4j", "add-workflow", "sync_orders"],
        ["crawler4j", "add-ui", "dashboard"],
        ["crawler4j", "add-data-table", "accounts"],
        ["crawler4j", "add-data", "legacy_data"],
    ],
)
def test_legacy_command_name_is_rejected(monkeypatch: pytest.MonkeyPatch, argv: list[str]):
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as exc_info:
        commands.main()

    assert exc_info.value.code == 2

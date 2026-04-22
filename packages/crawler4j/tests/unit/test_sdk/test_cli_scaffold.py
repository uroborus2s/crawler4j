"""CLI scaffold tests for the refactored crawler4j SDK command tree."""

from __future__ import annotations

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


def _read_pyproject(module_root: Path) -> dict:
    with (module_root / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


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
    assert not (module_root / "data").exists()
    assert not (module_root / "ui").exists()

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
    assert _read_pyproject(module_root)["project"]["version"] == manifest["version"]

    runtime_text = (module_root / "module_runtime.py").read_text(encoding="utf-8")
    assert "该 Hook 会在 ATM 执行环境动作前触发" in runtime_text
    assert 'context.runtime["env_action"]' in runtime_text

    readme_text = (module_root / "README.md").read_text(encoding="utf-8")
    assert "`on_cleanup` 会在 ATM 执行计划中的环境动作前调用" in readme_text


def test_archive_members_excludes_nested_egg_info_contents(tmp_path: Path):
    module_root = tmp_path / "demo_model"
    module_root.mkdir()
    nested_package = module_root / "nested"
    nested_package.mkdir()
    egg_info = nested_package / "demo_model.egg-info"
    egg_info.mkdir()
    (module_root / ".idea").mkdir()
    (module_root / ".vscode").mkdir()

    keep_file = module_root / "module.yaml"
    keep_file.write_text("name: demo_model\nversion: 0.1.0\n", encoding="utf-8")
    ignored_mac_file = module_root / ".DS_Store"
    ignored_mac_file.write_text("junk", encoding="utf-8")
    ignored_file = egg_info / "PKG-INFO"
    ignored_file.write_text("metadata", encoding="utf-8")
    ignored_idea_file = module_root / ".idea" / "workspace.xml"
    ignored_idea_file.write_text("<xml />", encoding="utf-8")
    ignored_vscode_file = module_root / ".vscode" / "settings.json"
    ignored_vscode_file.write_text("{}", encoding="utf-8")

    members = commands._archive_members(module_root)
    archived_paths = {arcname for _, arcname in members}

    assert "demo_model/module.yaml" in archived_paths
    assert "demo_model/.DS_Store" not in archived_paths
    assert "demo_model/.idea/workspace.xml" not in archived_paths
    assert "demo_model/.vscode/settings.json" not in archived_paths
    assert "demo_model/nested/demo_model.egg-info/PKG-INFO" not in archived_paths


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
    pyproject = _read_pyproject(module_root)

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
    assert _read_pyproject(module_root)["project"]["version"] == "0.2.0"
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
    assert not (module_root / "ui").exists()

    manifest = _read_manifest(module_root)
    assert [item["name"] for item in manifest["workflows"]] == ["main_workflow", "repair_orders"]
    assert manifest["ui_extension"]["pages"] == [
        {
            "id": "dashboard",
            "label": "Dashboard",
            "icon": "📄",
            "entry": "core:page:dashboard",
        },
        {
            "id": "accounts",
            "label": "Accounts",
            "icon": "📋",
            "entry": "core:data_table:accounts",
        }
    ]

    runtime_text = (module_root / "module_runtime.py").read_text(encoding="utf-8")
    assert "_declare_dashboard_page" in runtime_text
    assert "build_dashboard_page_schema" in runtime_text
    assert "load_dashboard_page" in runtime_text
    assert '_declare_dashboard_page(context)' in runtime_text
    assert "_declare_accounts_table" in runtime_text
    assert "_declare_accounts_table(context)" in runtime_text
    assert 'name="pick_ready"' in runtime_text


def test_page_create_generates_hosted_page_runtime_skeleton(
    module_root: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(module_root)
    assert commands.cmd_page_create(
        Namespace(name="dashboard", display_name=None, description=None, force=False)
    ) == 0

    runtime_text = (module_root / "module_runtime.py").read_text(encoding="utf-8")
    assert '"ui.declare_page"' in runtime_text
    assert "build_dashboard_page_schema" in runtime_text
    assert "load_dashboard_page" in runtime_text
    assert "PyQt6" not in runtime_text

    package_name = module_root.name
    stale = [name for name in sys.modules if name == package_name or name.startswith(f"{package_name}.")]
    for name in stale:
        sys.modules.pop(name, None)

    parent = str(module_root.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    module_runtime = importlib.import_module(f"{module_root.name}.module_runtime")
    payload = module_runtime.load_dashboard_page(None, "dashboard")
    assert payload["summary"] == "Dashboard 页面已由 hosted page V1 加载。"
    assert payload["updated_at"] == "待接入真实数据"


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


def test_check_release_rejects_pyproject_version_drift(module_root: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(module_root)
    pyproject_path = module_root / "pyproject.toml"
    pyproject_path.write_text(
        pyproject_path.read_text(encoding="utf-8").replace('version = "0.1.0"', 'version = "9.9.9"'),
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


def test_check_full_reports_missing_page_load_handler(
    module_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.chdir(module_root)
    assert commands.cmd_page_create(
        Namespace(name="dashboard", display_name=None, description=None, force=False)
    ) == 0
    runtime_path = module_root / "module_runtime.py"
    runtime_path.write_text(
        runtime_path.read_text(encoding="utf-8").replace(
            '"load_handler": "load_dashboard_page"',
            '"load_handler": "missing_dashboard_page_loader"',
        ),
        encoding="utf-8",
    )

    assert commands.cmd_check_full(Namespace()) == 1

    captured = capsys.readouterr()
    assert "宿主页 dashboard 的 load_handler 未在 module_runtime.py 中定义" in captured.out


def test_check_full_rejects_invalid_hosted_page_schema(
    module_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.chdir(module_root)
    assert commands.cmd_page_create(
        Namespace(name="dashboard", display_name=None, description=None, force=False)
    ) == 0
    runtime_path = module_root / "module_runtime.py"
    runtime_path.write_text(
        runtime_path.read_text(encoding="utf-8").replace(
            '"action": {"type": "reload"}',
            '"action": {"type": "open_page", "entry": "ui:LegacyPage"}',
        ),
        encoding="utf-8",
    )

    assert commands.cmd_check_full(Namespace()) == 1

    captured = capsys.readouterr()
    assert "schema 无效" in captured.out
    assert "core:page:<page_id> 或 core:data_table:<view_id>" in captured.out


def test_check_full_rejects_invalid_managed_data_table_schema(
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
            "columns": [
                {"key": "status", "label": "状态", "type": "select"},
            ],
        },
    )
    return None""",
        ),
        encoding="utf-8",
    )
    manifest = _read_manifest(module_root)
    manifest["ui_extension"] = {
        "pages": [
            {
                "id": "accounts",
                "label": "Accounts",
                "icon": "📋",
                "entry": "core:data_table:accounts",
            }
        ]
    }
    (module_root / "module.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    assert commands.cmd_check_full(Namespace()) == 1

    captured = capsys.readouterr()
    assert "schema 无效" in captured.out
    assert "select 列必须提供非空 options 数组" in captured.out


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
    assert "lock_key 只用于 Core 临时锁" in captured.out


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


def test_page_create_inserts_call_without_sdk_sentinel(
    module_root: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(module_root)
    runtime_path = module_root / "module_runtime.py"
    runtime_path.write_text(
        runtime_path.read_text(encoding="utf-8").replace("    # SDK-DATA-TABLES\n", ""),
        encoding="utf-8",
    )

    assert commands.cmd_page_create(
        Namespace(name="dashboard", display_name=None, description=None, force=False)
    ) == 0

    runtime_text = runtime_path.read_text(encoding="utf-8")
    assert "    _declare_dashboard_page(context)\n    return None" in runtime_text
    assert _read_manifest(module_root)["ui_extension"]["pages"][0]["id"] == "dashboard"


def test_data_table_create_inserts_call_without_sdk_sentinel(
    module_root: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(module_root)
    runtime_path = module_root / "module_runtime.py"
    runtime_path.write_text(
        runtime_path.read_text(encoding="utf-8").replace("    # SDK-DATA-TABLES\n", ""),
        encoding="utf-8",
    )

    assert commands.cmd_data_table_create(Namespace(view_id="accounts", label=None, icon=None)) == 0

    runtime_text = runtime_path.read_text(encoding="utf-8")
    assert "    _declare_accounts_table(context)\n    return None" in runtime_text
    assert _read_manifest(module_root)["ui_extension"]["pages"][0]["id"] == "accounts"


def test_page_create_does_not_mutate_manifest_when_declare_ui_is_missing(
    module_root: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(module_root)
    runtime_path = module_root / "module_runtime.py"
    runtime_path.write_text(
        runtime_path.read_text(encoding="utf-8").replace("def declare_ui(context: TaskContext):", "def missing_ui(context: TaskContext):"),
        encoding="utf-8",
    )

    assert commands.cmd_page_create(
        Namespace(name="dashboard", display_name=None, description=None, force=False)
    ) == 1
    assert "ui_extension" not in _read_manifest(module_root)


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

"""CLI scaffold tests for the core-native-v2 module protocol."""

from __future__ import annotations

import importlib
import json
import sys
import tomllib
import zipfile
from argparse import Namespace
from pathlib import Path

import pytest
import yaml

from crawler4j_contracts import CRAWLER4J_META_ATTR
from crawler4j_sdk._version import (
    get_compatible_contracts_dependency_spec,
    get_compatible_sdk_dependency_spec,
)
from crawler4j_sdk.cli import commands


def _import_generated_package(package_root: Path, *, package_name: str | None = None):
    import_name = package_name or package_root.name
    parent = str(package_root.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    stale = [name for name in sys.modules if name == import_name or name.startswith(f"{import_name}.")]
    for name in stale:
        sys.modules.pop(name, None)

    return importlib.import_module(import_name)


def _import_module_child(
    package_root: Path,
    subpackage: str,
    name: str,
    *,
    package_name: str | None = None,
):
    import_name = package_name or package_root.name
    _import_generated_package(package_root, package_name=import_name)
    return importlib.import_module(f"{import_name}.{subpackage}.{name}")


def _read_manifest(module_root: Path) -> dict:
    with (module_root / "module.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _write_manifest(module_root: Path, manifest: dict) -> None:
    with (module_root / "module.yaml").open("w", encoding="utf-8") as fh:
        yaml.safe_dump(manifest, fh, allow_unicode=True, sort_keys=False)


def _read_pyproject(module_root: Path) -> dict:
    with (module_root / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def _read_lock(module_root: Path) -> dict:
    return json.loads((module_root / ".crawler4j" / "manifest.lock.json").read_text(encoding="utf-8"))


def _lock_declaration_keys(module_root: Path) -> set[tuple[str, str]]:
    return {(str(item["kind"]), str(item["name"])) for item in _read_lock(module_root).get("declarations", [])}


def _init_module(tmp_path: Path, *, module_name: str = "demo_model", output_name: str | None = None) -> Path:
    target = tmp_path / (output_name or module_name)
    args = Namespace(
        name=module_name,
        repo=f"demo/{module_name}",
        output=str(target),
        display_name=None,
        description=None,
        version="0.1.0",
        workflow_name="main_workflow",
        workflow_display_name=None,
        workflow_description=None,
        python_version="3.12",
        runtime_api="core-native-v2",
        no_git=True,
        no_install=True,
        force=False,
    )
    assert commands.cmd_module_init(args) == 0
    return target


def test_module_init_parser_supports_interactive_and_full_argument_modes():
    parser = commands.build_parser()

    interactive_args = parser.parse_args(["module", "init"])
    assert interactive_args.name is None
    assert interactive_args.repo is None
    assert interactive_args.runtime_api == "core-native-v2"

    full_args = parser.parse_args(
        [
            "module",
            "init",
            "hotel_demo",
            "--repo",
            "your-org/hotel_demo",
            "--runtime-api",
            "core-native-v2",
            "--no-git",
            "--no-install",
        ]
    )
    assert full_args.name == "hotel_demo"
    assert full_args.repo == "your-org/hotel_demo"
    assert full_args.no_git is True
    assert full_args.no_install is True


def test_module_init_prompts_for_missing_required_values_and_uses_defaults(
    tmp_path: Path,
    monkeypatch,
):
    answers = iter(["hotel_demo", "your-org/hotel_demo"])
    prompts: list[str] = []

    def fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return next(answers)

    target = tmp_path / "hotel_demo"
    monkeypatch.setattr("builtins.input", fake_input)

    args = Namespace(
        name=None,
        repo=None,
        output=str(target),
        display_name=None,
        description=None,
        version=None,
        workflow_name=None,
        workflow_display_name=None,
        workflow_description=None,
        python_version=None,
        runtime_api=None,
        no_git=True,
        no_install=True,
        force=False,
    )

    assert commands.cmd_module_init(args) == 0

    assert len(prompts) == 2
    manifest = _read_manifest(target)
    assert manifest["name"] == "hotel_demo"
    assert manifest["runtime_api"] == "core-native-v2"
    assert manifest["version"] == commands.DEFAULT_MODULE_VERSION
    assert manifest["upgrade_source"]["repo"] == "your-org/hotel_demo"
    assert (target / "workflows" / "main_workflow.py").exists()
    assert (target / ".python-version").read_text(encoding="utf-8").strip() == commands.DEFAULT_PYTHON_VERSION


def test_module_init_reports_missing_required_prompt_input(tmp_path: Path, monkeypatch, capsys):
    def fake_input(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)
    args = Namespace(
        name=None,
        repo=None,
        output=str(tmp_path / "hotel_demo"),
        display_name=None,
        description=None,
        version=None,
        workflow_name=None,
        workflow_display_name=None,
        workflow_description=None,
        python_version=None,
        runtime_api=None,
        no_git=True,
        no_install=True,
        force=False,
    )

    assert commands.cmd_module_init(args) == 1
    assert "缺少必填参数" in capsys.readouterr().out


def test_module_init_creates_core_native_v2_project(tmp_path: Path):
    module_root = _init_module(tmp_path)

    assert (module_root / "__init__.py").exists()
    assert (module_root / "module.yaml").exists()
    assert (module_root / "pyproject.toml").exists()
    assert (module_root / "README.md").exists()
    assert (module_root / ".gitignore").exists()
    assert (module_root / ".python-version").exists()
    assert (module_root / ".crawler4j" / "manifest.lock.json").exists()
    for dirname in ("interfaces", "objects", "workflows", "tasks", "data", "pages", "tests"):
        assert (module_root / dirname / "__init__.py").exists()

    assert (module_root / "interfaces" / "labor.py").exists()
    assert (module_root / "objects" / "api_labor.py").exists()
    assert (module_root / "workflows" / "main_workflow.py").exists()
    assert (module_root / "tasks" / "example_action.py").exists()
    assert (module_root / "data" / "accounts.py").exists()
    assert (module_root / "data" / "get_account_by_id.py").exists()
    assert not (module_root / "module_runtime.py").exists()
    assert not (module_root / "hooks").exists()
    assert not (module_root / "env_selectors").exists()
    assert not (module_root / "data" / "sql").exists()
    assert not (module_root / "data" / "seeds").exists()

    manifest = _read_manifest(module_root)
    assert manifest["name"] == "demo_model"
    assert manifest["runtime_api"] == "core-native-v2"
    assert "ui_extension" not in manifest
    assert manifest["config_defaults"] == {"module": {}}
    for legacy_key in ("default_workflow", "workflows", "data", "objects", "interfaces", "tasks"):
        assert legacy_key not in manifest

    pyproject = _read_pyproject(module_root)
    assert pyproject["project"]["dependencies"] == [get_compatible_contracts_dependency_spec()]
    assert pyproject["dependency-groups"]["dev"] == [
        get_compatible_sdk_dependency_spec(),
        "pytest>=9.0.2",
        "pytest-asyncio>=1.3.0",
    ]

    task_text = (module_root / "tasks" / "example_action.py").read_text(encoding="utf-8")
    assert "@page_action(" in task_text
    assert "TaskSpec" not in task_text
    workflow_text = (module_root / "workflows" / "main_workflow.py").read_text(encoding="utf-8")
    assert "@workflow(" in workflow_text
    assert "WorkflowSpec" not in workflow_text

    assert _lock_declaration_keys(module_root) == {
        ("component", "api_labor"),
        ("data_query", "get_account_by_id"),
        ("data_table", "accounts"),
        ("interface", "labor"),
        ("page_action", "example_action"),
        ("workflow", "main_workflow"),
    }
    assert commands.collect_full_errors(module_root, manifest, require_manifest_lock=True) == []


def test_generated_package_is_importable_without_runtime_shim(tmp_path: Path):
    module_root = _init_module(tmp_path)

    module = _import_generated_package(module_root)
    interface_module = _import_module_child(module_root, "interfaces", "labor")
    component_module = _import_module_child(module_root, "objects", "api_labor")
    workflow_module = _import_module_child(module_root, "workflows", "main_workflow")
    action_module = _import_module_child(module_root, "tasks", "example_action")
    data_table_module = _import_module_child(module_root, "data", "accounts")
    data_query_module = _import_module_child(module_root, "data", "get_account_by_id")

    assert hasattr(module, "run") is False
    assert hasattr(module, "declare_ui") is False
    assert getattr(interface_module.Labor, CRAWLER4J_META_ATTR).kind == "interface"
    assert getattr(component_module.ApiLabor, CRAWLER4J_META_ATTR).kind == "component"
    assert getattr(workflow_module.MainWorkflow, CRAWLER4J_META_ATTR).kind == "workflow"
    assert getattr(action_module.example_action, CRAWLER4J_META_ATTR).kind == "page_action"
    assert getattr(data_table_module.Accounts, CRAWLER4J_META_ATTR).kind == "data_table"
    assert getattr(data_query_module.get_account_by_id, CRAWLER4J_META_ATTR).kind == "data_query"


def test_module_repair_init_rewrites_root_package_file(tmp_path: Path, monkeypatch):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)
    init_path = module_root / "__init__.py"
    init_path.write_text(
        '"""旧入口。"""\n\ndef run():\n    return None\n',
        encoding="utf-8",
    )

    assert commands.cmd_module_repair_init(Namespace()) == 0

    root_text = init_path.read_text(encoding="utf-8")
    assert "Demo Model 模块包" in root_text
    assert "Core 会直接扫描" in root_text
    assert "模块根包不再承载运行时装配逻辑" in root_text
    assert "def run" not in root_text


def test_page_create_registers_menu_page_and_supports_grouped_non_menu_page(
    tmp_path: Path,
    monkeypatch,
):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)

    assert (
        commands.cmd_page_create(
            Namespace(
                name="dashboard",
                display_name="Dashboard",
                description="Dashboard 页面",
                group=None,
                no_menu=False,
                force=False,
            )
        )
        == 0
    )
    assert (
        commands.cmd_page_create(
            Namespace(
                name="account_detail",
                display_name=None,
                description=None,
                group="account",
                no_menu=True,
                force=False,
            )
        )
        == 0
    )

    manifest = _read_manifest(module_root)
    assert "ui_extension" not in manifest
    dashboard_path = module_root / "pages" / "dashboard.py"
    detail_path = module_root / "pages" / "account" / "detail.py"
    assert dashboard_path.exists()
    assert detail_path.exists()
    dashboard_text = dashboard_path.read_text(encoding="utf-8")
    detail_text = detail_path.read_text(encoding="utf-8")
    assert "from crawler4j_contracts import TaskContext, page" in dashboard_text
    assert "@page(" in dashboard_text
    assert 'name="dashboard"' in dashboard_text
    assert "menu=True" in dashboard_text
    assert 'name="account_detail"' in detail_text
    assert "menu=False" in detail_text
    assert commands.collect_full_errors(module_root, manifest) == []


def test_check_full_rejects_removed_manifest_ui_extension(tmp_path: Path, monkeypatch):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)
    manifest = _read_manifest(module_root)
    manifest["ui_extension"] = {"pages": [{"id": "dashboard", "label": "Dashboard", "icon": "📄"}]}
    _write_manifest(module_root, manifest)

    errors = commands.collect_full_errors(module_root, _read_manifest(module_root))

    assert any("module.yaml 不再允许声明 ui_extension" in error for error in errors)


def test_check_full_rejects_legacy_v1_manifest_sections(tmp_path: Path, monkeypatch, capsys):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)
    manifest = _read_manifest(module_root)
    manifest["default_workflow"] = "main_workflow"
    manifest["workflows"] = [{"name": "main_workflow", "parameters": [{"name": "legacy_param"}]}]
    manifest["data"] = {"resources": []}
    manifest["objects"] = []
    manifest["interfaces"] = []
    manifest["tasks"] = []
    _write_manifest(module_root, manifest)

    errors = commands.collect_full_errors(module_root, _read_manifest(module_root))

    assert any("V2_MANIFEST_LEGACY_DEFAULT_WORKFLOW" in error for error in errors)
    assert any("V2_MANIFEST_LEGACY_WORKFLOWS" in error for error in errors)
    assert any("V2_MANIFEST_LEGACY_WORKFLOW_PARAMETERS" in error for error in errors)
    assert any("V2_MANIFEST_LEGACY_DATA" in error for error in errors)
    assert any("V2_MANIFEST_LEGACY_OBJECTS" in error for error in errors)
    assert any("V2_MANIFEST_LEGACY_INTERFACES" in error for error in errors)
    assert any("V2_MANIFEST_LEGACY_TASKS" in error for error in errors)

    assert commands.cmd_check_full(Namespace()) == 1
    output = capsys.readouterr().out
    assert "full 校验失败" in output
    assert "V2_MANIFEST_LEGACY_WORKFLOW_PARAMETERS" in output


def test_cli_creates_v2_declarations_and_refreshes_manifest_lock(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)

    assert (
        commands.cmd_interface_create(Namespace(name="account_store", display_name=None, description=None, force=False))
        == 0
    )
    assert (
        commands.cmd_component_create(
            Namespace(
                name="sqlite_account_store",
                implements="account_store",
                display_name=None,
                description=None,
                force=False,
            )
        )
        == 0
    )
    assert (
        commands.cmd_workflow_create(Namespace(name="sync_accounts", display_name=None, description=None, force=False))
        == 0
    )
    assert commands.cmd_task_create(Namespace(name="open_home_page", force=False)) == 0
    assert (
        commands.cmd_data_table_create(Namespace(name="orders", display_name=None, description=None, force=False)) == 0
    )
    assert (
        commands.cmd_data_query_create(
            Namespace(name="get_order_by_id", source="orders", display_name=None, description=None, force=False)
        )
        == 0
    )
    assert commands.cmd_manifest_lock(Namespace()) == 0

    assert commands.cmd_interface_list(Namespace()) == 0
    assert commands.cmd_component_list(Namespace()) == 0
    assert commands.cmd_workflow_list(Namespace()) == 0
    assert commands.cmd_task_list(Namespace()) == 0
    assert commands.cmd_data_list(Namespace()) == 0
    output = capsys.readouterr().out
    assert "account_store" in output
    assert "sqlite_account_store" in output
    assert "sync_accounts" in output
    assert "open_home_page" in output
    assert "orders" in output
    assert "get_order_by_id" in output

    assert ("interface", "account_store") in _lock_declaration_keys(module_root)
    assert ("component", "sqlite_account_store") in _lock_declaration_keys(module_root)
    assert ("workflow", "sync_accounts") in _lock_declaration_keys(module_root)
    assert ("page_action", "open_home_page") in _lock_declaration_keys(module_root)
    assert ("data_table", "orders") in _lock_declaration_keys(module_root)
    assert ("data_query", "get_order_by_id") in _lock_declaration_keys(module_root)
    assert commands.collect_full_errors(module_root, _read_manifest(module_root), require_manifest_lock=True) == []


def test_component_and_query_create_require_declared_targets(tmp_path: Path, monkeypatch, capsys):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)

    assert (
        commands.cmd_component_create(
            Namespace(
                name="ghost_component",
                implements="ghost",
                display_name=None,
                description=None,
                force=False,
            )
        )
        == 1
    )
    assert "未找到接口声明: ghost" in capsys.readouterr().out

    assert (
        commands.cmd_data_query_create(
            Namespace(name="missing_query", source="missing_table", display_name=None, description=None, force=False)
        )
        == 1
    )
    assert "未找到数据表声明: missing_table" in capsys.readouterr().out


def test_manifest_lock_stale_state_blocks_check_and_package_until_refreshed(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)
    assert (
        commands.cmd_data_table_create(Namespace(name="new_accounts", display_name=None, description=None, force=False))
        == 0
    )

    errors = commands.collect_full_errors(module_root, _read_manifest(module_root), require_manifest_lock=True)

    assert any("manifest lock 已过期" in error for error in errors)
    assert commands.cmd_check_full(Namespace()) == 1
    assert "manifest lock 已过期" in capsys.readouterr().out
    assert commands.cmd_package_build(Namespace(output=None)) == 1
    assert "manifest lock 已过期" in capsys.readouterr().out

    assert commands.cmd_manifest_lock(Namespace()) == 0
    assert commands.cmd_check_full(Namespace()) == 0
    assert commands.cmd_package_build(Namespace(output=None)) == 0
    assert ("data_table", "new_accounts") in _lock_declaration_keys(module_root)


def test_build_parser_registers_v2_commands():
    parser = commands.build_parser()

    interface_args = parser.parse_args(["interface", "create", "labor"])
    component_args = parser.parse_args(["component", "create", "api_labor", "--implements", "labor"])
    action_args = parser.parse_args(["page-action", "create", "open_home_page"])
    table_args = parser.parse_args(["data", "table", "create", "accounts"])
    query_args = parser.parse_args(["data", "query", "create", "get_account_by_id", "--source", "accounts"])
    lock_args = parser.parse_args(["manifest", "lock"])

    assert interface_args.func is commands.cmd_interface_create
    assert component_args.func is commands.cmd_component_create
    assert action_args.func is commands.cmd_task_create
    assert table_args.func is commands.cmd_data_table_create
    assert query_args.func is commands.cmd_data_query_create
    assert query_args.source == "accounts"
    assert lock_args.func is commands.cmd_manifest_lock


def test_build_parser_rejects_removed_v1_commands():
    parser = commands.build_parser()

    removed_commands = [
        ["task", "create", "open_home_page"],
        ["data", "resource", "create", "accounts"],
        ["data", "view", "create", "account_stats", "--source", "accounts"],
        ["data", "seed", "create", "accounts_seed", "--resource", "accounts"],
        ["env-selector", "create", "random_ready"],
        ["hook", "create", "before_run"],
        ["module", "set", "default-workflow", "main_workflow"],
    ]
    for argv in removed_commands:
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(argv)
        assert exc_info.value.code == 2


def test_archive_members_keep_v2_files_and_manifest_lock_without_runtime_shim(tmp_path: Path):
    module_root = _init_module(tmp_path)
    (module_root / ".idea").mkdir()
    (module_root / ".idea" / "workspace.xml").write_text("<xml />", encoding="utf-8")

    members = commands._archive_members(module_root, "demo_model")
    archived_paths = {arcname for _, arcname in members}

    assert "demo_model/module.yaml" in archived_paths
    assert "demo_model/.crawler4j/manifest.lock.json" in archived_paths
    assert "demo_model/interfaces/labor.py" in archived_paths
    assert "demo_model/objects/api_labor.py" in archived_paths
    assert "demo_model/tasks/example_action.py" in archived_paths
    assert "demo_model/workflows/main_workflow.py" in archived_paths
    assert "demo_model/data/accounts.py" in archived_paths
    assert "demo_model/data/get_account_by_id.py" in archived_paths
    assert "demo_model/module_runtime.py" not in archived_paths
    assert "demo_model/hooks/__init__.py" not in archived_paths
    assert "demo_model/env_selectors/__init__.py" not in archived_paths
    assert "demo_model/.idea/workspace.xml" not in archived_paths


def test_archive_members_rejects_symlinked_module_files(tmp_path: Path):
    module_root = _init_module(tmp_path)
    link_path = module_root / "data" / "linked_accounts.py"
    try:
        link_path.symlink_to(module_root / "data" / "accounts.py")
    except OSError:
        pytest.skip("filesystem does not support symlinks")

    with pytest.raises(commands.CLIError, match="符号链接"):
        commands._archive_members(module_root, "demo_model")


def test_package_verify_rejects_zip_path_traversal(tmp_path: Path, capsys):
    archive_path = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("../module.yaml", "name: evil\nruntime_api: core-native-v2\n")

    assert commands.cmd_package_verify(Namespace(archive=str(archive_path))) == 1
    assert "非法路径" in capsys.readouterr().out


def test_package_verify_rejects_stale_lock_inside_zip(tmp_path: Path, monkeypatch):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)
    assert commands.cmd_package_build(Namespace(output=None)) == 0
    archive_path = module_root / "dist" / "demo_model-0.1.0.zip"

    with zipfile.ZipFile(archive_path, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "demo_model/data/unlocked_table.py",
            "from crawler4j_contracts import data_table\n\n"
            '@data_table(name="unlocked_table", schema=[{"name": "id", "type": "string"}])\n'
            "class UnlockedTable:\n"
            "    pass\n",
        )

    assert commands.cmd_package_verify(Namespace(archive=str(archive_path))) == 1

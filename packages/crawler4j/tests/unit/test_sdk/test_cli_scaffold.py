"""CLI scaffold tests for the core-native-v1 module protocol."""

from __future__ import annotations

import importlib
import shutil
import sys
import tomllib
from argparse import Namespace
from pathlib import Path

import yaml

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
        no_git=True,
        no_install=True,
        force=False,
    )
    assert commands.cmd_module_init(args) == 0
    return target


def test_module_init_creates_core_native_project(tmp_path: Path):
    module_root = _init_module(tmp_path)

    assert (module_root / "__init__.py").exists()
    assert (module_root / "module.yaml").exists()
    assert (module_root / "pyproject.toml").exists()
    assert (module_root / "README.md").exists()
    assert (module_root / ".gitignore").exists()
    assert (module_root / ".python-version").exists()
    assert (module_root / "tasks" / "example_task.py").exists()
    assert (module_root / "workflows" / "main_workflow.py").exists()
    assert (module_root / "pages" / "__init__.py").exists()
    assert (module_root / "hooks" / "__init__.py").exists()
    assert (module_root / "env_selectors" / "__init__.py").exists()
    assert (module_root / "hooks" / "on_cleanup.py").exists()
    assert (module_root / "env_selectors" / "return_none.py").exists()
    assert (module_root / "env_selectors" / "random_ready.py").exists()
    assert (module_root / "data" / "sql" / "views").is_dir()
    assert (module_root / "data" / "sql" / "queries").is_dir()
    assert (module_root / "data" / "seeds").is_dir()
    assert not (module_root / "module_runtime.py").exists()

    manifest = _read_manifest(module_root)
    assert manifest["name"] == "demo_model"
    assert manifest["runtime_api"] == "core-native-v1"
    assert manifest["default_workflow"] == "main_workflow"
    assert manifest["workflows"] == [
        {
            "name": "main_workflow",
            "display_name": "Main Workflow",
            "description": "Main Workflow 工作流",
        }
    ]
    assert manifest["ui_extension"] == {"pages": []}
    assert manifest["data"] == {
        "resources": [],
        "views": [],
        "queries": [],
        "seeds": [],
    }

    pyproject = _read_pyproject(module_root)
    assert pyproject["project"]["dependencies"] == [get_compatible_contracts_dependency_spec()]
    assert pyproject["dependency-groups"]["dev"] == [
        get_compatible_sdk_dependency_spec(),
        "pytest>=9.0.2",
        "pytest-asyncio>=1.3.0",
    ]

    root_text = (module_root / "__init__.py").read_text(encoding="utf-8")
    assert "Core 会直接扫描" in root_text
    assert "运行时装配逻辑" in root_text

    task_text = (module_root / "tasks" / "example_task.py").read_text(encoding="utf-8")
    assert "TASK = TaskSpec(" in task_text
    assert "async def execute(ctx: TaskContext)" in task_text

    workflow_text = (module_root / "workflows" / "main_workflow.py").read_text(encoding="utf-8")
    assert "WORKFLOW = WorkflowSpec(" in workflow_text
    assert "async def run(ctx: TaskContext)" in workflow_text

    page_init_text = (module_root / "pages" / "__init__.py").read_text(encoding="utf-8")
    assert "Hosted UI 页面集合" in page_init_text

    selector_text = (module_root / "env_selectors" / "random_ready.py").read_text(encoding="utf-8")
    assert "SELECTOR = EnvSelectorSpec(" in selector_text
    assert "def select(context: TaskContext, candidates: list[EnvCandidate])" in selector_text

    readme_text = (module_root / "README.md").read_text(encoding="utf-8")
    assert "模块运行时只依赖 `crawler4j-contracts`" in readme_text
    assert "`crawler4j-sdk` 只作为 CLI / 校验 / 开发辅助存在" in readme_text
    assert "不会调用模块根 `run()` 或 `declare_ui()`" in readme_text


def test_generated_package_is_importable_without_runtime_shim(tmp_path: Path):
    module_root = _init_module(tmp_path)

    module = _import_generated_package(module_root)
    task_module = _import_module_child(module_root, "tasks", "example_task")
    workflow_module = _import_module_child(module_root, "workflows", "main_workflow")
    hook_module = _import_module_child(module_root, "hooks", "on_cleanup")
    selector_module = _import_module_child(module_root, "env_selectors", "random_ready")

    assert hasattr(module, "run") is False
    assert hasattr(module, "declare_ui") is False
    assert hasattr(task_module, "TASK")
    assert hasattr(task_module, "execute")
    assert hasattr(workflow_module, "WORKFLOW")
    assert hasattr(workflow_module, "run")
    assert hasattr(hook_module, "handle")
    assert hasattr(selector_module, "SELECTOR")
    assert hasattr(selector_module, "select")


def test_page_create_registers_manifest_and_generates_page_spec(tmp_path: Path, monkeypatch):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)

    assert commands.cmd_page_create(
        Namespace(name="dashboard", display_name="Dashboard", description="Dashboard 页面", group=None, force=False)
    ) == 0

    manifest = _read_manifest(module_root)
    assert manifest["ui_extension"]["pages"] == [
        {
            "id": "dashboard",
            "label": "Dashboard",
            "icon": "📄",
        }
    ]

    page_text = (module_root / "pages" / "dashboard.py").read_text(encoding="utf-8")
    assert "PAGE = PageSpec(" in page_text
    assert 'id="dashboard"' in page_text
    assert '"load_handler": "load_dashboard_page"' in page_text
    assert "def load_dashboard_page(" in page_text
    assert "declare_ui" not in page_text


def test_page_create_supports_grouped_source_layout(tmp_path: Path, monkeypatch):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)

    assert commands.cmd_page_create(
        Namespace(
            name="account_detail",
            display_name="Account Detail",
            description="Account Detail 页面",
            group="account",
            force=False,
        )
    ) == 0

    manifest = _read_manifest(module_root)
    assert manifest["ui_extension"]["pages"] == [
        {
            "id": "account_detail",
            "label": "Account Detail",
            "icon": "📄",
        }
    ]

    page_path = module_root / "pages" / "account" / "detail.py"
    assert page_path.exists()
    page_text = page_path.read_text(encoding="utf-8")
    assert 'id="account_detail"' in page_text
    assert '"load_handler": "load_account_detail_page"' in page_text
    assert "def load_account_detail_page(" in page_text

    page_module = _import_module_child(module_root, "pages", "account.detail")
    assert page_module.PAGE.id == "account_detail"


def test_env_selector_list_reads_exported_selector_specs(tmp_path: Path, monkeypatch, capsys):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)

    assert commands.cmd_env_selector_create(
        Namespace(name="pick_ready", display_name="Pick Ready", description="Pick Ready 选择器", force=False)
    ) == 0
    assert commands.cmd_env_selector_list(Namespace()) == 0

    lines = [line.strip() for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert "return_none" in lines
    assert "random_ready" in lines
    assert "pick_ready" in lines


def test_env_selector_list_fails_fast_on_import_error(tmp_path: Path, monkeypatch, capsys):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)
    (module_root / "env_selectors" / "random_ready.py").write_text(
        "from missing_runtime_dependency import nope\n",
        encoding="utf-8",
    )

    assert commands.cmd_env_selector_list(Namespace()) == 1
    output = capsys.readouterr().out
    assert "读取环境选择器失败" in output
    assert "missing_runtime_dependency" in output


def test_collect_structure_errors_requires_runtime_api_and_default_workflow(tmp_path: Path):
    module_root = _init_module(tmp_path)
    manifest = _read_manifest(module_root)
    manifest.pop("runtime_api", None)
    manifest["default_workflow"] = ""

    errors = commands.collect_structure_errors(module_root, manifest)

    assert "module.yaml.runtime_api 必须是 core-native-v1" in errors
    assert "module.yaml 缺少 default_workflow" in errors


def test_collect_structure_errors_allow_optional_sdk_only_layout_bits(tmp_path: Path):
    module_root = _init_module(tmp_path)
    shutil.rmtree(module_root / "pages")
    shutil.rmtree(module_root / "hooks")
    shutil.rmtree(module_root / "env_selectors")
    (module_root / "pyproject.toml").unlink()

    errors = commands.collect_structure_errors(module_root, _read_manifest(module_root))

    assert errors == []


def test_collect_full_errors_rejects_manifest_page_missing_from_files(tmp_path: Path, monkeypatch):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)
    assert commands.cmd_page_create(
        Namespace(name="dashboard", display_name=None, description=None, group=None, force=False)
    ) == 0
    (module_root / "pages" / "dashboard.py").unlink()

    errors = commands.collect_full_errors(module_root, _read_manifest(module_root))

    assert "module.yaml.ui_extension.pages 声明的宿主页缺少页面文件: dashboard" in errors


def test_collect_full_errors_rejects_page_file_missing_from_manifest(tmp_path: Path, monkeypatch):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)
    assert commands.cmd_page_create(
        Namespace(name="dashboard", display_name=None, description=None, group=None, force=False)
    ) == 0
    manifest = _read_manifest(module_root)
    manifest["ui_extension"]["pages"] = []
    _write_manifest(module_root, manifest)

    errors = commands.collect_full_errors(module_root, _read_manifest(module_root))

    assert "pages/ 声明了未写入 module.yaml.ui_extension.pages 的宿主页: dashboard" in errors


def test_collect_full_errors_accepts_grouped_page_source_layout(tmp_path: Path, monkeypatch):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)
    assert commands.cmd_page_create(
        Namespace(name="account_detail", display_name=None, description=None, group="account", force=False)
    ) == 0

    errors = commands.collect_full_errors(module_root, _read_manifest(module_root))

    assert errors == []


def test_collect_full_errors_allow_manifest_name_to_differ_from_directory_name(tmp_path: Path):
    module_root = _init_module(tmp_path, output_name="demo_model_pkg")
    shutil.rmtree(module_root / "pages")
    shutil.rmtree(module_root / "hooks")
    shutil.rmtree(module_root / "env_selectors")
    (module_root / "pyproject.toml").unlink()

    errors = commands.collect_full_errors(module_root, _read_manifest(module_root))

    assert errors == []


def test_build_parser_registers_data_commands():
    parser = commands.build_parser()

    resource_args = parser.parse_args(
        ["data", "resource", "create", "accounts", "--storage-mode", "custom_table"]
    )
    query_args = parser.parse_args(
        ["data", "query", "create", "get_account_by_id", "--source", "accounts"]
    )
    seed_args = parser.parse_args(
        ["data", "seed", "create", "accounts_seed", "--resource", "accounts"]
    )

    assert resource_args.func is commands.cmd_data_resource_create
    assert resource_args.storage_mode == "custom_table"
    assert query_args.func is commands.cmd_data_query_create
    assert query_args.source == ["accounts"]
    assert seed_args.func is commands.cmd_data_seed_create
    assert seed_args.resource == "accounts"


def test_build_parser_registers_page_group_argument():
    parser = commands.build_parser()

    args = parser.parse_args(["page", "create", "account_detail", "--group", "account"])

    assert args.func is commands.cmd_page_create
    assert args.group == "account"


def test_data_commands_scaffold_manifest_sql_and_seed_files(tmp_path: Path, monkeypatch):
    module_root = _init_module(tmp_path)
    monkeypatch.chdir(module_root)

    assert commands.cmd_data_resource_create(
        Namespace(
            name="accounts",
            storage_mode="custom_table",
            record_key_field="account_id",
        )
    ) == 0
    assert commands.cmd_data_view_create(
        Namespace(
            name="account_stats",
            source=["accounts"],
            force=False,
        )
    ) == 0
    assert commands.cmd_data_query_create(
        Namespace(
            name="get_account_by_id",
            source=["accounts"],
            force=False,
        )
    ) == 0
    assert commands.cmd_data_seed_create(
        Namespace(
            name="accounts_seed",
            resource="accounts",
            mode="replace_if_empty",
            force=False,
        )
    ) == 0

    manifest = _read_manifest(module_root)
    assert manifest["data"]["resources"] == [
        {
            "id": "accounts",
            "storage_mode": "custom_table",
            "record_key_field": "account_id",
            "indexes": {},
            "cleanup_policy": "drop_table",
            "schema": {
                "version": 1,
                "columns": [
                    {"key": "account_id", "type": "text", "required": True},
                ],
            },
        }
    ]
    assert manifest["data"]["views"] == [
        {
            "id": "account_stats",
            "view_kind": "sql_view",
            "source_resource_ids": ["accounts"],
            "sql_file": "data/sql/views/account_stats.sql",
            "columns": [
                {
                    "name": "account_id",
                    "type": "text",
                    "nullable": False,
                    "filterable": True,
                    "sortable": True,
                }
            ],
            "cleanup_policy": "drop_view",
            "schema_version": 1,
        }
    ]
    assert manifest["data"]["queries"] == [
        {
            "id": "get_account_by_id",
            "source_resource_ids": ["accounts"],
            "sql_file": "data/sql/queries/get_account_by_id.sql",
            "params": [{"name": "account_id", "type": "text", "required": True}],
            "columns": [{"name": "account_id", "type": "text", "nullable": False}],
        }
    ]
    assert manifest["data"]["seeds"] == [
        {
            "id": "accounts_seed",
            "resource_id": "accounts",
            "file": "data/seeds/accounts_seed.json",
            "format": "json",
            "mode": "replace_if_empty",
        }
    ]
    assert (module_root / "data" / "sql" / "views" / "account_stats.sql").read_text(encoding="utf-8") == (
        "SELECT account_id\nFROM {{resource:accounts}}\n"
    )
    assert (module_root / "data" / "sql" / "queries" / "get_account_by_id.sql").read_text(encoding="utf-8") == (
        "SELECT account_id\n"
        "FROM {{resource:accounts}}\n"
        "WHERE account_id = :account_id\n"
        "LIMIT 1\n"
    )
    assert (module_root / "data" / "seeds" / "accounts_seed.json").read_text(encoding="utf-8") == (
        '[\n  {\n    "account_id": "sample-id"\n  }\n]\n'
    )


def test_archive_members_keep_generated_files_without_runtime_shim(tmp_path: Path):
    module_root = _init_module(tmp_path)
    (module_root / ".idea").mkdir()
    (module_root / ".idea" / "workspace.xml").write_text("<xml />", encoding="utf-8")

    members = commands._archive_members(module_root, "demo_model")
    archived_paths = {arcname for _, arcname in members}

    assert "demo_model/module.yaml" in archived_paths
    assert "demo_model/tasks/example_task.py" in archived_paths
    assert "demo_model/workflows/main_workflow.py" in archived_paths
    assert "demo_model/module_runtime.py" not in archived_paths
    assert "demo_model/.idea/workspace.xml" not in archived_paths

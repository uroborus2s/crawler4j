"""End-to-end CLI tests for the core-native-v2 module protocol."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest
import yaml

from crawler4j_sdk._version import (
    get_compatible_contracts_dependency_spec,
    get_compatible_sdk_dependency_spec,
)


WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
APP_PACKAGE_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j"
SDK_PACKAGE_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j-sdk"
CONTRACTS_PACKAGE_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j-contracts"


def _run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    python_path_parts = [
        str(APP_PACKAGE_ROOT),
        str(SDK_PACKAGE_ROOT),
        str(CONTRACTS_PACKAGE_ROOT),
    ]
    python_path = env.get("PYTHONPATH", "")
    if python_path:
        python_path_parts.append(python_path)
    env["PYTHONPATH"] = os.pathsep.join(python_path_parts)
    return subprocess.run(
        [sys.executable, "-m", "crawler4j_sdk.cli.commands", *args],
        cwd=str(cwd),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _init_demo_module(target: Path, *, module_name: str = "demo_model") -> None:
    init_result = _run_cli(
        "module",
        "init",
        module_name,
        "--repo",
        f"demo/{module_name}",
        "--output",
        str(target),
        "--no-install",
        "--no-git",
        cwd=WORKSPACE_ROOT,
    )
    assert init_result.returncode == 0, init_result.stderr


def test_cli_module_scaffold_flow_end_to_end(tmp_path: Path):
    target = tmp_path / "demo_model"

    _init_demo_module(target)
    assert (target / "__init__.py").exists()
    assert not (target / "module_runtime.py").exists()
    assert (target / "module.yaml").exists()
    assert (target / "pages" / "__init__.py").exists()
    assert (target / ".crawler4j" / "manifest.lock.json").exists()
    assert not (target / "hooks").exists()
    assert not (target / "env_selectors").exists()

    with (target / "pyproject.toml").open("rb") as fh:
        generated_pyproject = tomllib.load(fh)
    assert generated_pyproject["project"]["dependencies"] == [get_compatible_contracts_dependency_spec()]
    assert generated_pyproject["dependency-groups"]["dev"] == [
        get_compatible_sdk_dependency_spec(),
        "pytest>=9.0.2",
        "pytest-asyncio>=1.3.0",
    ]

    action_result = _run_cli("page-action", "create", "extra_task", cwd=target)
    assert action_result.returncode == 0, action_result.stderr
    assert (target / "tasks" / "extra_task.py").exists()

    workflow_result = _run_cli("workflow", "create", "repair_orders", cwd=target)
    assert workflow_result.returncode == 0, workflow_result.stderr
    assert (target / "workflows" / "repair_orders.py").exists()

    page_result = _run_cli("page", "create", "dashboard", cwd=target)
    assert page_result.returncode == 0, page_result.stderr
    table_result = _run_cli("page", "create", "accounts", cwd=target)
    assert table_result.returncode == 0, table_result.stderr

    lock_result = _run_cli("manifest", "lock", cwd=target)
    assert lock_result.returncode == 0, lock_result.stderr

    check_result = _run_cli("check", "full", cwd=target)
    assert check_result.returncode == 0, check_result.stderr

    package_result = _run_cli("package", "build", cwd=target)
    assert package_result.returncode == 0, package_result.stderr
    archive = target / "dist" / "demo_model-0.1.0.zip"
    assert archive.exists()

    verify_result = _run_cli("package", "verify", str(archive), cwd=target)
    assert verify_result.returncode == 0, verify_result.stderr

    debug_config_result = _run_cli("host", "debug", "config", "--module-root", str(target), cwd=target)
    assert debug_config_result.returncode == 0, debug_config_result.stderr
    assert (target / ".vscode" / "launch.json").exists()

    publish_dry_run_result = _run_cli("release", "publish", "--dry-run", cwd=target)
    assert publish_dry_run_result.returncode == 0, publish_dry_run_result.stderr

    with (target / "module.yaml").open("r", encoding="utf-8") as fh:
        manifest = yaml.safe_load(fh)

    assert manifest["runtime_api"] == "core-native-v2"
    assert "default_workflow" not in manifest
    assert "workflows" not in manifest
    assert manifest["upgrade_source"] == {
        "type": "github_release",
        "repo": "demo/demo_model",
        "allow_prerelease": False,
    }
    assert "ui_extension" not in manifest
    lock = json.loads((target / ".crawler4j" / "manifest.lock.json").read_text(encoding="utf-8"))
    lock_names = {(item["kind"], item["name"]) for item in lock["declarations"]}
    assert ("page_action", "extra_task") in lock_names
    assert ("workflow", "repair_orders") in lock_names
    assert ("page", "dashboard") in lock_names
    assert ("page", "accounts") in lock_names

    with zipfile.ZipFile(archive) as zf:
        members = set(zf.namelist())
    assert "demo_model/module.yaml" in members
    assert "demo_model/.crawler4j/manifest.lock.json" in members
    assert "demo_model/pages/dashboard.py" in members
    assert "demo_model/pages/accounts.py" in members
    assert "demo_model/env_selectors/pick_ready.py" not in members
    assert "demo_model/tasks/extra_task.py" in members
    assert "demo_model/workflows/repair_orders.py" in members
    assert "demo_model/module_runtime.py" not in members


def test_cli_rejects_removed_commands(tmp_path: Path):
    removed_cases = [
        ("init-model", "removed_command_project"),
        ("add", "task_name"),
        ("task", "create", "task_name"),
        ("new", "task_name"),
        ("list",),
        ("add-workflow", "sync_orders"),
        ("add-ui", "dashboard"),
        ("add-data-table", "accounts"),
        ("add-data", "removed_data"),
    ]

    for argv in removed_cases:
        result = _run_cli(*argv, cwd=tmp_path)
        assert result.returncode != 0
        assert "invalid choice" in result.stderr

    assert not (tmp_path / "removed_command_project").exists()


def test_cli_check_full_rejects_missing_runtime_api(tmp_path: Path):
    target = tmp_path / "demo_model"
    _init_demo_module(target)

    manifest_path = target / "module.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("runtime_api", None)
    manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")

    check_result = _run_cli("check", "full", cwd=target)
    assert check_result.returncode == 1
    assert "module.yaml.runtime_api 必须是 core-native-v2" in check_result.stdout


def test_cli_check_and_package_reject_legacy_module_runtime(tmp_path: Path):
    target = tmp_path / "demo_model"
    _init_demo_module(target)
    (target / "module_runtime.py").write_text("# legacy runtime shim\n", encoding="utf-8")

    check_result = _run_cli("check", "full", cwd=target)
    assert check_result.returncode == 1
    assert "core-native-v2 模块不允许保留旧运行时薄壳: module_runtime.py" in check_result.stdout

    package_result = _run_cli("package", "build", cwd=target)
    assert package_result.returncode == 1
    assert "core-native-v2 模块不允许保留旧运行时薄壳: module_runtime.py" in package_result.stdout


def test_cli_check_full_rejects_removed_manifest_ui_extension(tmp_path: Path):
    target = tmp_path / "demo_model"
    _init_demo_module(target)

    manifest_path = target / "module.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["ui_extension"] = {
        "pages": [{"id": "dashboard", "label": "Dashboard", "icon": "📄"}],
    }
    manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), encoding="utf-8")

    check_result = _run_cli("check", "full", cwd=target)
    assert check_result.returncode == 1
    assert "module.yaml 不再允许声明 ui_extension" in check_result.stdout


def test_cli_check_full_accepts_page_source_not_registered_as_menu_entry(tmp_path: Path):
    target = tmp_path / "demo_model"
    _init_demo_module(target)

    page_result = _run_cli("page", "create", "account_detail", "--group", "account", "--no-menu", cwd=target)
    assert page_result.returncode == 0, page_result.stderr
    lock_result = _run_cli("manifest", "lock", cwd=target)
    assert lock_result.returncode == 0, lock_result.stdout

    check_result = _run_cli("check", "full", cwd=target)
    assert check_result.returncode == 0, check_result.stdout

    package_result = _run_cli("package", "build", cwd=target)
    assert package_result.returncode == 0, package_result.stdout
    archive = target / "dist" / "demo_model-0.1.0.zip"
    assert archive.exists()

    verify_result = _run_cli("package", "verify", str(archive), cwd=target)
    assert verify_result.returncode == 0, verify_result.stdout

    with (target / "module.yaml").open("r", encoding="utf-8") as fh:
        manifest = yaml.safe_load(fh)
    assert "ui_extension" not in manifest
    assert (target / "pages" / "account" / "detail.py").exists()
    with zipfile.ZipFile(archive) as zf:
        members = set(zf.namelist())
    assert "demo_model/pages/account/detail.py" in members


def test_cli_page_create_supports_grouped_source_layout_and_packaging(tmp_path: Path):
    target = tmp_path / "demo_model"

    _init_demo_module(target)

    page_result = _run_cli("page", "create", "account_detail", "--group", "account", cwd=target)
    assert page_result.returncode == 0, page_result.stderr
    assert (target / "pages" / "account" / "detail.py").exists()
    lock_result = _run_cli("manifest", "lock", cwd=target)
    assert lock_result.returncode == 0, lock_result.stdout

    check_result = _run_cli("check", "full", cwd=target)
    assert check_result.returncode == 0, check_result.stdout

    package_result = _run_cli("package", "build", cwd=target)
    assert package_result.returncode == 0, package_result.stdout
    archive = target / "dist" / "demo_model-0.1.0.zip"
    assert archive.exists()

    verify_result = _run_cli("package", "verify", str(archive), cwd=target)
    assert verify_result.returncode == 0, verify_result.stdout

    with (target / "module.yaml").open("r", encoding="utf-8") as fh:
        manifest = yaml.safe_load(fh)
    assert "ui_extension" not in manifest

    with zipfile.ZipFile(archive) as zf:
        members = set(zf.namelist())
    assert "demo_model/pages/account/detail.py" in members


def test_cli_check_and_package_allow_manifest_name_to_differ_from_directory_name(tmp_path: Path):
    target = tmp_path / "demo_model_pkg"
    archive = target / "dist" / "mismatch-layout.zip"

    _init_demo_module(target, module_name="demo_model")
    (target / "pyproject.toml").unlink()
    lock_result = _run_cli("manifest", "lock", cwd=target)
    assert lock_result.returncode == 0, lock_result.stdout

    check_result = _run_cli("check", "full", cwd=target)
    assert check_result.returncode == 0, check_result.stdout

    package_result = _run_cli("package", "build", "--output", str(archive), cwd=target)
    assert package_result.returncode == 0, package_result.stdout
    assert archive.exists()

    verify_result = _run_cli("package", "verify", str(archive), cwd=target)
    assert verify_result.returncode == 0, verify_result.stdout

    with zipfile.ZipFile(archive) as zf:
        members = set(zf.namelist())
    assert "demo_model/module.yaml" in members
    assert "demo_model/tasks/example_action.py" in members
    assert "demo_model/workflows/main_workflow.py" in members
    assert "demo_model/pyproject.toml" not in members
    assert "demo_model/pages/__init__.py" in members
    assert "demo_model/hooks/__init__.py" not in members
    assert "demo_model/env_selectors/__init__.py" not in members


@pytest.mark.parametrize("extra_name", ["ui/", "config_schema.json", "strategy.yaml"])
def test_cli_package_build_rejects_additional_legacy_module_artifacts(tmp_path: Path, extra_name: str):
    target = tmp_path / "demo_model"

    _init_demo_module(target)
    if extra_name == "ui/":
        extra_ui_dir = target / "ui"
        extra_ui_dir.mkdir()
        (extra_ui_dir / "custom_page.py").write_text("class CustomPage: ...\n", encoding="utf-8")
        expected = "残留旧 UI 目录: ui/"
    else:
        (target / extra_name).write_text("{}", encoding="utf-8")
        expected = f"残留旧 UI 文件: {extra_name}"

    package_result = _run_cli("package", "build", cwd=target)
    assert package_result.returncode == 1
    assert expected in package_result.stdout

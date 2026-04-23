"""End-to-end CLI tests for the refactored crawler4j SDK command tree."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest
import yaml

from crawler4j_sdk._version import get_compatible_dependency_spec


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


def _init_demo_module(target: Path) -> None:
    init_result = _run_cli(
        "module",
        "init",
        "demo_model",
        "--repo",
        "demo/demo_model",
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
    assert (target / "module_runtime.py").exists()
    assert (target / "module.yaml").exists()
    assert (target / "pages" / "__init__.py").exists()
    assert (target / "hooks" / "__init__.py").exists()
    assert (target / "env_selectors" / "__init__.py").exists()
    assert not (target / "data").exists()

    with (target / "pyproject.toml").open("rb") as fh:
        generated_pyproject = tomllib.load(fh)
    assert get_compatible_dependency_spec() in generated_pyproject["project"]["dependencies"]

    task_result = _run_cli("task", "create", "extra_task", cwd=target)
    assert task_result.returncode == 0, task_result.stderr
    assert (target / "tasks" / "extra_task.py").exists()

    workflow_result = _run_cli("workflow", "create", "repair_orders", cwd=target)
    assert workflow_result.returncode == 0, workflow_result.stderr
    assert (target / "workflows" / "repair_orders.py").exists()

    page_result = _run_cli("page", "create", "dashboard", cwd=target)
    assert page_result.returncode == 0, page_result.stderr
    assert not (target / "ui").exists()

    table_result = _run_cli("page", "create", "accounts", cwd=target)
    assert table_result.returncode == 0, table_result.stderr

    selector_result = _run_cli("env-selector", "create", "pick_ready", cwd=target)
    assert selector_result.returncode == 0, selector_result.stderr
    hook_result = _run_cli("hook", "create", "on_cleanup", "--force", cwd=target)
    assert hook_result.returncode == 0, hook_result.stderr

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

    assert manifest["upgrade_source"] == {
        "type": "github_release",
        "repo": "demo/demo_model",
        "allow_prerelease": False,
    }
    assert manifest["ui_extension"]["pages"] == [
        {
            "id": "dashboard",
            "label": "Dashboard",
            "icon": "📄",
        },
        {
            "id": "accounts",
            "label": "Accounts",
            "icon": "📄",
        },
    ]
    assert [item["name"] for item in manifest["workflows"]] == ["main_workflow", "repair_orders"]


def test_cli_rejects_removed_commands(tmp_path: Path):
    removed_cases = [
        ("init-model", "removed_command_project"),
        ("add", "task_name"),
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


def test_cli_check_full_rejects_manifest_declare_ui_drift(tmp_path: Path):
    target = tmp_path / "demo_model"

    _init_demo_module(target)

    page_result = _run_cli("page", "create", "dashboard", cwd=target)
    assert page_result.returncode == 0, page_result.stderr

    runtime_path = target / "module_runtime.py"
    runtime_path.write_text(
        runtime_path.read_text(encoding="utf-8").replace("    return _pages.declare_pages(context)", "    return None"),
        encoding="utf-8",
    )

    check_result = _run_cli("check", "full", cwd=target)
    assert check_result.returncode == 1
    assert "module.yaml.ui_extension.pages 声明的宿主页未从 declare_ui 注册: dashboard" in check_result.stdout


@pytest.mark.parametrize("extra_name", ["ui/", "config_schema.json", "strategy.yaml"])
def test_cli_check_full_allows_additional_module_artifacts(tmp_path: Path, extra_name: str):
    target = tmp_path / "demo_model"

    _init_demo_module(target)
    if extra_name == "ui/":
        extra_ui_dir = target / "ui"
        extra_ui_dir.mkdir()
        (extra_ui_dir / "custom_page.py").write_text("class CustomPage: ...\n", encoding="utf-8")
    else:
        (target / extra_name).write_text("{}", encoding="utf-8")

    check_result = _run_cli("check", "full", cwd=target)
    assert check_result.returncode == 0


@pytest.mark.parametrize("extra_name", ["ui/", "config_schema.json", "strategy.yaml"])
def test_cli_package_build_allows_additional_module_artifacts(tmp_path: Path, extra_name: str):
    target = tmp_path / "demo_model"

    _init_demo_module(target)
    if extra_name == "ui/":
        extra_ui_dir = target / "ui"
        extra_ui_dir.mkdir()
        (extra_ui_dir / "custom_page.py").write_text("class CustomPage: ...\n", encoding="utf-8")
    else:
        (target / extra_name).write_text("{}", encoding="utf-8")

    package_result = _run_cli("package", "build", cwd=target)
    assert package_result.returncode == 0


def test_cli_package_build_rejects_manifest_declare_ui_drift(tmp_path: Path):
    target = tmp_path / "demo_model"

    _init_demo_module(target)

    page_result = _run_cli("page", "create", "dashboard", cwd=target)
    assert page_result.returncode == 0, page_result.stderr

    runtime_path = target / "module_runtime.py"
    runtime_path.write_text(
        runtime_path.read_text(encoding="utf-8").replace("    return _pages.declare_pages(context)", "    return None"),
        encoding="utf-8",
    )

    package_result = _run_cli("package", "build", cwd=target)
    assert package_result.returncode == 1
    assert "module.yaml.ui_extension.pages 声明的宿主页未从 declare_ui 注册: dashboard" in package_result.stdout


@pytest.mark.parametrize("extra_name", ["ui/", "config_schema.json", "strategy.yaml"])
def test_cli_package_verify_allows_additional_module_artifacts(tmp_path: Path, extra_name: str):
    target = tmp_path / "demo_model"

    _init_demo_module(target)
    if extra_name == "ui/":
        extra_ui_dir = target / "ui"
        extra_ui_dir.mkdir()
        (extra_ui_dir / "custom_page.py").write_text("class CustomPage: ...\n", encoding="utf-8")
    else:
        (target / extra_name).write_text("{}", encoding="utf-8")

    archive_path = tmp_path / "demo_model-0.1.0.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in target.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(target)
            zf.write(path, f"{target.name}/{relative.as_posix()}")

    verify_result = _run_cli("package", "verify", str(archive_path), cwd=target)
    assert verify_result.returncode == 0


def test_cli_package_verify_rejects_manifest_declare_ui_drift(tmp_path: Path):
    target = tmp_path / "demo_model"

    _init_demo_module(target)

    page_result = _run_cli("page", "create", "dashboard", cwd=target)
    assert page_result.returncode == 0, page_result.stderr

    runtime_path = target / "module_runtime.py"
    runtime_path.write_text(
        runtime_path.read_text(encoding="utf-8").replace("    return _pages.declare_pages(context)", "    return None"),
        encoding="utf-8",
    )

    archive_path = tmp_path / "demo_model-0.1.0.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in target.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(target)
            zf.write(path, f"{target.name}/{relative.as_posix()}")

    verify_result = _run_cli("package", "verify", str(archive_path), cwd=target)
    assert verify_result.returncode == 1
    assert "module.yaml.ui_extension.pages 声明的宿主页未从 declare_ui 注册: dashboard" in verify_result.stdout

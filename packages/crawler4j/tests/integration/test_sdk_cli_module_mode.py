"""End-to-end CLI tests for the refactored crawler4j SDK command tree."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import yaml

from crawler4j_sdk._version import get_compatible_dependency_spec


REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    python_path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(REPO_ROOT) if not python_path else f"{REPO_ROOT}{os.pathsep}{python_path}"
    return subprocess.run(
        [sys.executable, "-m", "crawler4j_sdk.cli.commands", *args],
        cwd=str(cwd),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_cli_module_scaffold_flow_end_to_end(tmp_path: Path):
    target = tmp_path / "demo_model"

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
        cwd=REPO_ROOT,
    )
    assert init_result.returncode == 0, init_result.stderr
    assert (target / "__init__.py").exists()
    assert (target / "module_runtime.py").exists()
    assert (target / "module.yaml").exists()
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
        cwd=REPO_ROOT,
    )
    assert init_result.returncode == 0, init_result.stderr

    page_result = _run_cli("page", "create", "dashboard", cwd=target)
    assert page_result.returncode == 0, page_result.stderr

    runtime_path = target / "module_runtime.py"
    runtime_path.write_text(
        runtime_path.read_text(encoding="utf-8").replace("    _declare_dashboard_page(context)\n", ""),
        encoding="utf-8",
    )

    check_result = _run_cli("check", "full", cwd=target)
    assert check_result.returncode == 1
    assert "module.yaml.ui_extension.pages 声明的宿主页未从 declare_ui 注册: dashboard" in check_result.stdout


def test_cli_package_build_allows_additional_ui_directory(tmp_path: Path):
    target = tmp_path / "demo_model"

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
        cwd=REPO_ROOT,
    )
    assert init_result.returncode == 0, init_result.stderr

    extra_ui_dir = target / "ui"
    extra_ui_dir.mkdir()
    (extra_ui_dir / "custom_page.py").write_text("class CustomPage: ...\n", encoding="utf-8")

    package_result = _run_cli("package", "build", cwd=target)
    assert package_result.returncode == 0, package_result.stderr
    assert (target / "dist" / "demo_model-0.1.0.zip").exists()


def test_cli_package_build_rejects_manifest_declare_ui_drift(tmp_path: Path):
    target = tmp_path / "demo_model"

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
        cwd=REPO_ROOT,
    )
    assert init_result.returncode == 0, init_result.stderr

    page_result = _run_cli("page", "create", "dashboard", cwd=target)
    assert page_result.returncode == 0, page_result.stderr

    runtime_path = target / "module_runtime.py"
    runtime_path.write_text(
        runtime_path.read_text(encoding="utf-8").replace("    _declare_dashboard_page(context)\n", ""),
        encoding="utf-8",
    )

    package_result = _run_cli("package", "build", cwd=target)
    assert package_result.returncode == 1
    assert "module.yaml.ui_extension.pages 声明的宿主页未从 declare_ui 注册: dashboard" in package_result.stdout


def test_cli_package_verify_rejects_manifest_declare_ui_drift(tmp_path: Path):
    target = tmp_path / "demo_model"

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
        cwd=REPO_ROOT,
    )
    assert init_result.returncode == 0, init_result.stderr

    page_result = _run_cli("page", "create", "dashboard", cwd=target)
    assert page_result.returncode == 0, page_result.stderr

    runtime_path = target / "module_runtime.py"
    runtime_path.write_text(
        runtime_path.read_text(encoding="utf-8").replace("    _declare_dashboard_page(context)\n", ""),
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

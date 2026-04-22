"""End-to-end CLI tests for the refactored crawler4j SDK command tree."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
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

    table_result = _run_cli("data-table", "create", "accounts", cwd=target)
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
            "entry": "core:page:dashboard",
        },
        {
            "id": "accounts",
            "label": "Accounts",
            "icon": "📋",
            "entry": "core:data_table:accounts",
        },
    ]
    assert [item["name"] for item in manifest["workflows"]] == ["main_workflow", "repair_orders"]


def test_cli_rejects_legacy_commands(tmp_path: Path):
    legacy_cases = [
        ("init-model", "removed_command_project"),
        ("add", "task_name"),
        ("new", "task_name"),
        ("list",),
        ("add-workflow", "sync_orders"),
        ("add-ui", "dashboard"),
        ("add-data-table", "accounts"),
        ("add-data", "legacy_data"),
    ]

    for argv in legacy_cases:
        result = _run_cli(*argv, cwd=tmp_path)
        assert result.returncode != 0
        assert "invalid choice" in result.stderr

    assert not (tmp_path / "removed_command_project").exists()

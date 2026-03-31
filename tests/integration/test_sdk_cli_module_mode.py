"""End-to-end CLI tests for module-only scaffolding."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml


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
        "init-model",
        "demo_model",
        "--output",
        str(target),
        "--defaults",
        "--no-install",
        "--no-git",
        cwd=REPO_ROOT,
    )
    assert init_result.returncode == 0, init_result.stderr
    assert (target / "__init__.py").exists()
    assert (target / "module.yaml").exists()
    assert (target / "ui" / "config_schema.json").exists()
    assert (target / ".gitignore").exists()
    assert (target / ".python-version").exists()
    assert not (target / "debug_runner.py").exists()

    new_result = _run_cli("new", "extra_task", cwd=target)
    assert new_result.returncode == 0, new_result.stderr
    assert (target / "tasks" / "extra_task.py").exists()

    workflow_result = _run_cli("add-workflow", "repair_orders", cwd=target)
    assert workflow_result.returncode == 0, workflow_result.stderr
    assert (target / "workflows" / "repair_orders.py").exists()

    list_result = _run_cli("list", cwd=target)
    assert list_result.returncode == 0, list_result.stderr
    assert "example_task" in list_result.stdout
    assert "extra_task" in list_result.stdout

    with (target / "module.yaml").open("r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)
    assert manifest["sdk_version_range"] == ">=2.0.0"
    workflow_names = [item["name"] for item in manifest["workflows"]]
    assert "main_workflow" in workflow_names
    assert "repair_orders" in workflow_names


def test_cli_rejects_legacy_init_command_end_to_end(tmp_path: Path):
    result = _run_cli("init", "legacy_project", cwd=tmp_path)

    assert result.returncode != 0
    assert "invalid choice" in result.stderr
    assert not (tmp_path / "legacy_project").exists()

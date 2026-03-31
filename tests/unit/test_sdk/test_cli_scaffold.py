"""CLI scaffolding tests for module-only projects."""

from __future__ import annotations

import importlib
import sys
from argparse import Namespace
from pathlib import Path
import tomllib

import pytest
import yaml

from crawler4j_sdk.cli import commands


def _import_generated_package(package_root: Path):
    """Import a generated package from a temporary parent directory."""
    package_name = package_root.name
    parent = str(package_root.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    stale = [name for name in sys.modules if name == package_name or name.startswith(f"{package_name}.")]
    for name in stale:
        sys.modules.pop(name, None)

    return importlib.import_module(package_name)


def _read_manifest(module_root: Path) -> dict:
    with (module_root / "module.yaml").open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def model_args(tmp_path: Path) -> Namespace:
    target = tmp_path / "demo_model"
    return Namespace(
        name="demo_model",
        output=str(target),
        force=False,
        no_install=True,
        no_git=True,
        workflow_name="main_workflow",
        display_name=None,
        description=None,
        workflow_display_name=None,
        workflow_description=None,
        python_version="3.12",
        defaults=True,
        no_ui=False,
    )


class TestModelScaffoldInit:
    def test_init_model_creates_complete_module_project(self, model_args: Namespace):
        target = Path(model_args.output)

        result = commands.cmd_init_model(model_args)

        assert result == 0
        assert (target / "__init__.py").exists()
        assert (target / "module.yaml").exists()
        assert (target / "ui" / "config_schema.json").exists()
        assert (target / ".gitignore").exists()
        assert (target / ".python-version").exists()
        assert (target / "tasks" / "__init__.py").exists()
        assert (target / "tasks" / "example_task.py").exists()
        assert (target / "workflows" / "__init__.py").exists()
        assert (target / "workflows" / "main_workflow.py").exists()
        assert (target / "pyproject.toml").exists()

        manifest = _read_manifest(target)
        assert manifest["name"] == "demo_model"
        assert manifest["ui_extension"]["type"] == "declarative"
        assert manifest["ui_extension"]["entry"] == "ui/config_schema.json"
        assert manifest["workflows"][0]["name"] == "main_workflow"

    def test_init_model_generates_importable_module_package(self, model_args: Namespace):
        target = Path(model_args.output)
        commands.cmd_init_model(model_args)

        module = _import_generated_package(target)

        assert hasattr(module, "run")
        assert hasattr(module, "prepare_env")
        assert "example_task" in module.assembler.task_scripts
        assert "main_workflow" in module.assembler.workflows

    def test_init_model_generated_pyproject_does_not_duplicate_cli_or_playwright_dependency(self, model_args: Namespace):
        target = Path(model_args.output)

        result = commands.cmd_init_model(model_args)

        assert result == 0
        with (target / "pyproject.toml").open("rb") as f:
            pyproject = tomllib.load(f)

        dependencies = pyproject["project"]["dependencies"]
        assert "scripts" not in pyproject["project"]
        assert all("playwright" not in dependency for dependency in dependencies)
        assert "crawler4j-sdk>=2.0.0,<3.0.0" in dependencies

    def test_init_model_interactive_wizard_runs_git_init_and_uv_sync(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        target = tmp_path / "ctrip_model"
        # commands.cmd_init_model doesn't use interactive wizard anymore in latest implementation, 
        # it just uses args. 
        args = Namespace(
            name="ctrip_model",
            output=str(target),
            force=False,
            no_install=False,
            no_git=False,
            workflow_name="main_workflow",
            display_name="携程",
            description="携程任务模块",
            workflow_display_name=None,
            workflow_description=None,
            python_version="3.12",
            defaults=True,
            no_ui=False,
        )

        calls: list[tuple[list[str], str]] = []

        def fake_run(cmd: list[str], cwd: str | None = None, check: bool = False, capture_output: bool = False):
            calls.append((cmd, cwd or ""))
            return None

        monkeypatch.setattr(commands.subprocess, "run", fake_run)

        result = commands.cmd_init_model(args)

        assert result == 0
        assert calls == [
            (["git", "init"], str(target)),
            (["uv", "sync"], str(target)),
        ]

    def test_legacy_init_command_is_no_longer_supported(self, monkeypatch: pytest.MonkeyPatch, capsys):
        monkeypatch.setattr(sys, "argv", ["crawler4j", "init", "demo_project"])

        with pytest.raises(SystemExit) as exc_info:
            commands.main()

        captured = capsys.readouterr()
        assert exc_info.value.code == 2
        assert "invalid choice" in captured.err
        assert "init-model" in captured.err


class TestModelScaffoldExtensions:
    def test_add_workflow_creates_file_and_updates_manifest(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        model_args: Namespace,
    ):
        target = Path(model_args.output)
        commands.cmd_init_model(model_args)
        monkeypatch.chdir(target)

        result = commands.cmd_add_workflow(
            Namespace(
                name="sync_orders",
                force=False,
            )
        )

        assert result == 0
        assert (target / "workflows" / "sync_orders.py").exists()

        manifest = _read_manifest(target)
        workflow_names = [item["name"] for item in manifest["workflows"]]
        assert "sync_orders" in workflow_names

    def test_add_ui_creates_code_ui_and_updates_manifest(
        self,
        monkeypatch: pytest.MonkeyPatch,
        model_args: Namespace,
    ):
        target = Path(model_args.output)
        commands.cmd_init_model(model_args)
        monkeypatch.chdir(target)

        result = commands.cmd_add_ui(
            Namespace(
                name="dashboard",
                type="code",
                force=False,
            )
        )

        assert result == 0
        assert (target / "ui" / "dashboard.py").exists()

        manifest = _read_manifest(target)
        assert manifest["ui_extension"]["type"] == "micro_app"
        assert manifest["ui_extension"]["entry"] == "ui.dashboard:DashboardPage"

    def test_add_requires_model_project_context(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
        monkeypatch.chdir(tmp_path)

        with pytest.raises(SystemExit):
            commands.cmd_add(Namespace(name="extra_task", force=False))

        captured = capsys.readouterr()
        assert "找不到 module.yaml" in captured.out

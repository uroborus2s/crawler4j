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
        assert (target / "config_schema.json").exists()
        assert (target / ".gitignore").exists()
        assert (target / ".python-version").exists()
        assert (target / "tasks" / "__init__.py").exists()
        assert (target / "tasks" / "example_task.py").exists()
        assert (target / "workflows" / "__init__.py").exists()
        assert (target / "workflows" / "main_workflow.py").exists()
        assert (target / "pyproject.toml").exists()
        assert not (target / "debug_runner.py").exists()

        manifest = _read_manifest(target)
        assert manifest["name"] == "demo_model"
        assert manifest["ui_extension"]["type"] == "declarative"
        assert manifest["ui_extension"]["entry"] == "config_schema.json"
        assert manifest["workflows"][0]["name"] == "main_workflow"

    def test_init_model_generates_importable_module_package(self, model_args: Namespace):
        target = Path(model_args.output)
        commands.cmd_init_model(model_args)

        module = _import_generated_package(target)

        assert hasattr(module, "run")
        assert hasattr(module, "prepare_env")
        assert "example_task" in module.TASK_SCRIPTS
        assert "main_workflow" in module.WORKFLOWS

    def test_init_model_generated_pyproject_does_not_duplicate_cli_or_playwright_dependency(self, model_args: Namespace):
        target = Path(model_args.output)

        result = commands.cmd_init_model(model_args)

        assert result == 0
        with (target / "pyproject.toml").open("rb") as f:
            pyproject = tomllib.load(f)

        dependencies = pyproject["project"]["dependencies"]
        assert "scripts" not in pyproject["project"]
        assert all("playwright" not in dependency for dependency in dependencies)
        assert any("crawler4j-sdk" in dependency for dependency in dependencies)

    def test_init_model_defaults_mode_does_not_prompt(self, model_args: Namespace, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr("builtins.input", lambda _: pytest.fail("defaults 模式不应触发交互输入"))

        result = commands.cmd_init_model(model_args)

        assert result == 0

    def test_init_model_interactive_wizard_runs_git_init_and_uv_sync(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        target = tmp_path / "ctrip_model"
        args = Namespace(
            name="ctrip_model",
            output=str(target),
            force=False,
            no_install=False,
            no_git=False,
            workflow_name="main_workflow",
            display_name=None,
            description=None,
            workflow_display_name=None,
            workflow_description=None,
            python_version="3.12",
            defaults=False,
            no_ui=False,
        )

        answers = iter(
            [
                "",
                "携程",
                "携程任务模块",
                "login_workflow",
                "登录工作流",
                "登录与探测工作流",
                "",
                "",
                "",
                "",
            ]
        )
        monkeypatch.setattr("builtins.input", lambda _="": next(answers))

        calls: list[tuple[list[str], str]] = []

        def fake_run(cmd: list[str], cwd: str | None = None, check: bool = False):
            calls.append((cmd, cwd or ""))
            return None

        monkeypatch.setattr(commands.subprocess, "run", fake_run)

        result = commands.cmd_init_model(args)

        assert result == 0
        manifest = _read_manifest(target)
        assert manifest["display_name"] == "携程"
        assert manifest["description"] == "携程任务模块"
        assert manifest["workflows"][0]["name"] == "login_workflow"
        assert manifest["workflows"][0]["display_name"] == "登录工作流"
        assert manifest["workflows"][0]["description"] == "登录与探测工作流"
        assert (target / ".gitignore").exists()
        assert (target / ".python-version").read_text(encoding="utf-8").strip() == "3.12"
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
                display_name="同步订单",
                description="同步订单的示例工作流",
                force=False,
            )
        )

        assert result == 0
        assert (target / "workflows" / "sync_orders.py").exists()

        manifest = _read_manifest(target)
        workflow_names = [item["name"] for item in manifest["workflows"]]
        assert "sync_orders" in workflow_names

    def test_add_ui_creates_schema_and_updates_manifest(
        self,
        monkeypatch: pytest.MonkeyPatch,
        model_args: Namespace,
    ):
        target = Path(model_args.output)
        model_args.no_ui = True
        commands.cmd_init_model(model_args)
        monkeypatch.chdir(target)

        result = commands.cmd_add_ui(
            Namespace(
                title="Demo Model 配置",
                description="用于测试的 UI 配置页",
                force=False,
            )
        )

        assert result == 0
        assert (target / "config_schema.json").exists()

        manifest = _read_manifest(target)
        assert manifest["ui_extension"]["type"] == "declarative"
        assert manifest["ui_extension"]["entry"] == "config_schema.json"

    def test_new_task_in_model_project_is_auto_discovered(
        self,
        monkeypatch: pytest.MonkeyPatch,
        model_args: Namespace,
    ):
        target = Path(model_args.output)
        commands.cmd_init_model(model_args)
        monkeypatch.chdir(target)

        result = commands.cmd_new(Namespace(name="extra_task", force=False))

        assert result == 0
        module = _import_generated_package(target)
        assert "extra_task" in module.TASK_SCRIPTS

    def test_add_requires_model_project_context(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
        monkeypatch.chdir(tmp_path)

        result = commands.cmd_add(Namespace(name="extra_task", force=False))

        captured = capsys.readouterr()
        assert result == 1
        assert "model 项目" in captured.out
        assert not (tmp_path / "tasks").exists()

    def test_new_requires_model_project_context(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
        monkeypatch.chdir(tmp_path)

        result = commands.cmd_new(Namespace(name="extra_task", force=False))

        captured = capsys.readouterr()
        assert result == 1
        assert "model 项目" in captured.out
        assert not (tmp_path / "tasks").exists()

    def test_list_requires_model_project_context(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
        monkeypatch.chdir(tmp_path)

        result = commands.cmd_list(Namespace())

        captured = capsys.readouterr()
        assert result == 1
        assert "model 项目" in captured.out

    def test_list_shows_tasks_inside_model_project(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys,
        model_args: Namespace,
    ):
        target = Path(model_args.output)
        commands.cmd_init_model(model_args)
        monkeypatch.chdir(target)

        result = commands.cmd_list(Namespace())

        captured = capsys.readouterr()
        assert result == 0
        assert "example_task" in captured.out

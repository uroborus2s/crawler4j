"""Packaging configuration regression tests for publishable subpackages."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _load_pyproject(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def _load_module_version(package_dir: str) -> str:
    module_path = REPO_ROOT / package_dir / "__init__.py"
    spec = importlib.util.spec_from_file_location(f"{package_dir}.__init__", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return str(module.__version__)


def test_sdk_wheel_packages_target_real_package_dir():
    pyproject = _load_pyproject(REPO_ROOT / "crawler4j_sdk" / "pyproject.toml")
    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["sources"][""] == "crawler4j_sdk"
    assert "cli" in wheel["only-include"]
    assert "__init__.py" in wheel["only-include"]


def test_sdk_cli_package_exports_console_script_without_playwright_runtime_dependency():
    pyproject = _load_pyproject(REPO_ROOT / "crawler4j_sdk" / "pyproject.toml")
    dependencies = pyproject["project"]["dependencies"]
    scripts = pyproject["project"]["scripts"]

    assert scripts["crawler4j"] == "crawler4j_sdk.cli.commands:main"
    assert all("playwright" not in dependency for dependency in dependencies)


def test_sdk_runtime_version_matches_publish_metadata():
    pyproject = _load_pyproject(REPO_ROOT / "crawler4j_sdk" / "pyproject.toml")
    assert _load_module_version("crawler4j_sdk") == pyproject["project"]["version"]


def test_contracts_wheel_packages_target_real_package_dir():
    pyproject = _load_pyproject(REPO_ROOT / "crawler4j_contracts" / "pyproject.toml")
    wheel = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["sources"][""] == "crawler4j_contracts"
    assert "context.py" in wheel["only-include"]
    assert "__init__.py" in wheel["only-include"]


def test_contracts_runtime_version_matches_publish_metadata():
    pyproject = _load_pyproject(REPO_ROOT / "crawler4j_contracts" / "pyproject.toml")
    assert _load_module_version("crawler4j_contracts") == pyproject["project"]["version"]


def test_root_app_package_does_not_reexport_sdk_cli_command():
    pyproject = _load_pyproject(REPO_ROOT / "pyproject.toml")
    scripts = pyproject["project"]["scripts"]

    assert scripts["start"] == "src.ui.app:main"
    assert "crawler4j" not in scripts


def test_pyinstaller_spec_targets_real_ui_entry_and_runtime_assets():
    spec_text = (REPO_ROOT / "crawler4j.spec").read_text(encoding="utf-8")

    assert 'APP_ENTRY = PROJECT_ROOT / "src" / "ui" / "app.py"' in spec_text
    assert '(str(UI_ICON), "src/ui/assets")' in spec_text
    assert "src/main.py" not in spec_text

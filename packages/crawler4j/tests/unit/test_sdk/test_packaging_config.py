"""Packaging configuration regression tests for publishable subpackages."""

from __future__ import annotations

import ast
import tomllib
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = APP_ROOT.parents[1]


def _load_pyproject(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def _load_module_version(package_root: Path, package_dir: str) -> str:
    _ = package_dir
    module_path = package_root / "src" / "__init__.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__version__":
                value = ast.literal_eval(node.value)
                return str(value)

    raise AssertionError(f"Failed to find __version__ in {module_path}")


def test_sdk_packaging_maps_flat_src_to_public_package_names():
    pyproject = _load_pyproject(WORKSPACE_ROOT / "packages" / "crawler4j-sdk" / "pyproject.toml")
    setuptools_cfg = pyproject["tool"]["setuptools"]
    assert pyproject["build-system"]["build-backend"] == "setuptools.build_meta"
    assert setuptools_cfg["packages"] == ["crawler4j_sdk", "crawler4j_sdk.cli"]
    assert setuptools_cfg["package-dir"]["crawler4j_sdk"] == "src"
    assert setuptools_cfg["package-dir"]["crawler4j_sdk.cli"] == "src/cli"
    assert setuptools_cfg["package-data"]["crawler4j_sdk"] == ["py.typed"]


def test_sdk_cli_package_exports_console_script_without_playwright_runtime_dependency():
    pyproject = _load_pyproject(WORKSPACE_ROOT / "packages" / "crawler4j-sdk" / "pyproject.toml")
    dependencies = pyproject["project"]["dependencies"]
    scripts = pyproject["project"]["scripts"]

    assert scripts["crawler4j"] == "crawler4j_sdk.cli.commands:main"
    assert all("playwright" not in dependency for dependency in dependencies)


def test_sdk_runtime_version_matches_publish_metadata():
    package_root = WORKSPACE_ROOT / "packages" / "crawler4j-sdk"
    pyproject = _load_pyproject(package_root / "pyproject.toml")
    assert _load_module_version(package_root, "crawler4j_sdk") == pyproject["project"]["version"]


def test_contracts_packaging_maps_flat_src_to_public_package_name():
    pyproject = _load_pyproject(WORKSPACE_ROOT / "packages" / "crawler4j-contracts" / "pyproject.toml")
    setuptools_cfg = pyproject["tool"]["setuptools"]
    assert pyproject["build-system"]["build-backend"] == "setuptools.build_meta"
    assert setuptools_cfg["packages"] == ["crawler4j_contracts"]
    assert setuptools_cfg["package-dir"]["crawler4j_contracts"] == "src"
    assert setuptools_cfg["package-data"]["crawler4j_contracts"] == ["py.typed"]


def test_contracts_runtime_version_matches_publish_metadata():
    package_root = WORKSPACE_ROOT / "packages" / "crawler4j-contracts"
    pyproject = _load_pyproject(package_root / "pyproject.toml")
    assert _load_module_version(package_root, "crawler4j_contracts") == pyproject["project"]["version"]


def test_root_app_package_does_not_reexport_sdk_cli_command():
    pyproject = _load_pyproject(APP_ROOT / "pyproject.toml")
    scripts = pyproject["project"]["scripts"]

    assert scripts["start"] == "src.ui.app:main"
    assert "crawler4j" not in scripts


def test_workspace_root_declares_packages_workspace_members():
    pyproject = _load_pyproject(WORKSPACE_ROOT / "pyproject.toml")

    assert pyproject["project"]["name"] == "crawler4j-workspace"
    assert pyproject["tool"]["uv"]["workspace"]["members"] == ["packages/*"]
    assert pyproject["tool"]["uv"]["sources"]["crawler4j"]["workspace"] is True
    assert pyproject["tool"]["uv"]["sources"]["crawler4j-sdk"]["workspace"] is True
    assert pyproject["tool"]["uv"]["sources"]["crawler4j-contracts"]["workspace"] is True


def test_dev_scripts_live_in_workspace_root_instead_of_app_package():
    root_scripts = WORKSPACE_ROOT / "scripts"
    package_scripts = APP_ROOT / "scripts"

    assert root_scripts.exists()
    assert {
        "db_cli.py",
        "debug_runner.py",
        "generate_icon.py",
        "smoke_test_ui.py",
    }.issubset({path.name for path in root_scripts.glob("*.py")})
    assert list(package_scripts.glob("*.py")) == []


def test_root_app_runtime_does_not_keep_version_mirror_file():
    assert not (APP_ROOT / "src" / "__version__.py").exists()


def test_pyinstaller_spec_targets_real_ui_entry_and_runtime_assets():
    spec_text = (APP_ROOT / "crawler4j.spec").read_text(encoding="utf-8")

    assert 'APP_ENTRY = PROJECT_ROOT / "src" / "ui" / "app.py"' in spec_text
    assert "sys.path.insert(0, str(PROJECT_ROOT))" in spec_text
    assert '(str(UI_ICON), "src/ui/assets")' in spec_text
    assert 'PROJECT_METADATA = PROJECT_ROOT / "pyproject.toml"' in spec_text
    assert 'def _load_project_version' in spec_text
    assert "from src.__version__ import VERSION" not in spec_text
    assert "src/main.py" not in spec_text

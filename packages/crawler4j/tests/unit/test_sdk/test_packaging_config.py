"""Packaging configuration regression tests for publishable subpackages."""

from __future__ import annotations

import ast
import importlib.util
import re
import tomllib
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = APP_ROOT.parents[1]
BASE_VERSION_RE = re.compile(r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)")


def _load_pyproject(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def _load_version_helper(package_root: Path):
    helper_path = package_root / "src" / "_version.py"
    module_name = f"{package_root.name.replace('-', '_')}_version_helper"
    spec = importlib.util.spec_from_file_location(module_name, helper_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_literal_module_version(package_root: Path) -> str | None:
    module_path = package_root / "src" / "__init__.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__version__":
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                    return node.value.value
                return None

    return None


def _build_compatible_requirement(distribution_name: str, version: str) -> str:
    match = BASE_VERSION_RE.match(version.strip())
    if not match:
        raise AssertionError(f"Unsupported version format: {version}")
    base_version = f"{match.group('major')}.{match.group('minor')}.{match.group('patch')}"
    upper_bound = f"{int(match.group('major')) + 1}.0.0"
    return f"{distribution_name}>={base_version},<{upper_bound}"


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
    contracts_pyproject = _load_pyproject(WORKSPACE_ROOT / "packages" / "crawler4j-contracts" / "pyproject.toml")
    dependencies = pyproject["project"]["dependencies"]
    scripts = pyproject["project"]["scripts"]

    assert scripts["crawler4j"] == "crawler4j_sdk.cli.commands:main"
    assert all("playwright" not in dependency for dependency in dependencies)
    assert _build_compatible_requirement("crawler4j-contracts", contracts_pyproject["project"]["version"]) in dependencies


def test_sdk_runtime_version_matches_publish_metadata():
    package_root = WORKSPACE_ROOT / "packages" / "crawler4j-sdk"
    pyproject = _load_pyproject(package_root / "pyproject.toml")
    version_helper = _load_version_helper(package_root)

    assert version_helper.get_version() == pyproject["project"]["version"]
    assert _load_literal_module_version(package_root) is None


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
    assert pyproject["project"]["version"]
    assert not (package_root / "src" / "_version.py").exists()
    assert _load_literal_module_version(package_root) is None


def test_root_app_package_does_not_reexport_sdk_cli_command():
    pyproject = _load_pyproject(APP_ROOT / "pyproject.toml")
    contracts_pyproject = _load_pyproject(WORKSPACE_ROOT / "packages" / "crawler4j-contracts" / "pyproject.toml")
    dependencies = pyproject["project"]["dependencies"]
    scripts = pyproject["project"]["scripts"]

    assert scripts["start"] == "src.ui.app:main"
    assert "crawler4j" not in scripts
    assert f"crawler4j-contracts>={contracts_pyproject['project']['version']}" in dependencies


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

"""Packaging configuration regression tests for publishable subpackages."""

from __future__ import annotations

import ast
import importlib.util
import re
import shutil
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


def _load_script_module(script_name: str):
    script_path = WORKSPACE_ROOT / "scripts" / script_name
    module_name = f"workspace_script_{script_name.replace('.', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
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
    major = int(match.group("major"))
    minor = int(match.group("minor"))
    upper_bound = f"0.{minor + 1}.0" if major == 0 else f"{major + 1}.0.0"
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
    assert version_helper.get_compatible_dependency_spec() == "crawler4j-sdk>=0.3.0,<0.4.0"
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
    assert _build_compatible_requirement("crawler4j-contracts", contracts_pyproject["project"]["version"]) in dependencies


def test_workspace_root_declares_packages_workspace_members():
    pyproject = _load_pyproject(WORKSPACE_ROOT / "pyproject.toml")

    assert pyproject["project"]["name"] == "crawler4j-workspace"
    assert pyproject["tool"]["uv"]["workspace"]["members"] == ["packages/*"]
    assert pyproject["tool"]["uv"]["sources"]["crawler4j"]["workspace"] is True
    assert pyproject["tool"]["uv"]["sources"]["crawler4j-sdk"]["workspace"] is True
    assert pyproject["tool"]["uv"]["sources"]["crawler4j-contracts"]["workspace"] is True


def test_workspace_root_declares_console_shortcuts_for_build_and_publish():
    pyproject = _load_pyproject(WORKSPACE_ROOT / "pyproject.toml")

    assert pyproject["project"]["scripts"]["build"] == "scripts.build_workspace_packages:build_main"
    assert pyproject["project"]["scripts"]["package-desktop"] == "scripts.package_desktop_app:main"
    assert pyproject["project"]["scripts"]["publish"] == "scripts.build_workspace_packages:publish_main"
    assert pyproject["build-system"]["build-backend"] == "setuptools.build_meta"
    assert pyproject["tool"]["setuptools"]["packages"] == ["scripts"]


def test_dev_scripts_live_in_workspace_root_instead_of_app_package():
    root_scripts = WORKSPACE_ROOT / "scripts"
    package_scripts = APP_ROOT / "scripts"

    assert root_scripts.exists()
    assert {
        "build_workspace_packages.py",
        "db_cli.py",
        "package_desktop_app.py",
        "smoke_test_ui.py",
    }.issubset({path.name for path in root_scripts.glob("*.py")})
    assert list(package_scripts.glob("*.py")) == []


def test_root_app_runtime_does_not_keep_version_mirror_file():
    assert not (APP_ROOT / "src" / "__version__.py").exists()


def test_pyinstaller_spec_targets_real_ui_entry_and_runtime_assets():
    spec_text = (APP_ROOT / "crawler4j.spec").read_text(encoding="utf-8")
    paths_text = (APP_ROOT / "src" / "utils" / "paths.py").read_text(encoding="utf-8")

    assert 'APP_ENTRY = PROJECT_ROOT / "src" / "ui" / "app.py"' in spec_text
    assert 'WORKSPACE_ROOT = PROJECT_ROOT.parents[1]' in spec_text
    assert 'DOCS_ROOT = WORKSPACE_ROOT / "docs"' in spec_text
    assert '(str(DOCS_ROOT / "index.md"), "docs")' in spec_text
    assert '(str(DOCS_ROOT / "01-getting-started"), "docs/01-getting-started")' in spec_text
    assert '(str(DOCS_ROOT / "02-user-guide"), "docs/02-user-guide")' in spec_text
    assert '(str(DOCS_ROOT / "03-developer-guide"), "docs/03-developer-guide")' in spec_text
    assert "if MODULES_DIR.exists():" in spec_text
    assert 'datas=_build_datas(),' in spec_text
    assert "sys.path.insert(0, str(PROJECT_ROOT))" in spec_text
    assert '(str(UI_ICON), "src/ui/assets")' in spec_text
    assert 'PROJECT_METADATA = PROJECT_ROOT / "pyproject.toml"' in spec_text
    assert 'def _load_project_version' in spec_text
    assert "from src.__version__ import VERSION" not in spec_text
    assert "src/main.py" not in spec_text
    assert "def get_docs_root() -> Path:" in paths_text


def test_pyinstaller_spec_collects_workspace_runtime_packages_for_desktop_bundle():
    spec_text = (APP_ROOT / "crawler4j.spec").read_text(encoding="utf-8")

    assert "from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata" in spec_text
    assert "import debugpy" in spec_text
    assert 'DEBUGPY_ROOT = Path(debugpy.__file__).resolve().parent' in spec_text
    assert 'DEBUGPY_VENDORED_PYDEVD_ROOT = DEBUGPY_ROOT / "_vendored" / "pydevd"' in spec_text
    assert 'datas.extend(collect_data_files("debugpy"))' in spec_text
    assert 'datas.extend(collect_data_files("debugpy", include_py_files=True))' in spec_text
    assert '"debugpy",' in spec_text
    assert 'hiddenimports.extend(collect_submodules("debugpy"))' in spec_text
    assert 'hiddenimports.extend(_build_debugpy_vendored_hiddenimports())' in spec_text
    assert "def _build_debugpy_vendored_hiddenimports() -> list[str]:" in spec_text
    assert '"crawler4j_contracts": "crawler4j-contracts"' in spec_text
    assert '"crawler4j_sdk": "crawler4j-sdk"' in spec_text
    assert '"crawler4j_contracts": WORKSPACE_ROOT / "packages" / "crawler4j-contracts" / "src"' in spec_text
    assert '"crawler4j_sdk": WORKSPACE_ROOT / "packages" / "crawler4j-sdk" / "src"' in spec_text
    assert 'alias_root = PYINSTALLER_SUPPORT_ROOT / "workspace-package-aliases"' in spec_text
    assert "shutil.copytree(source_root, target_root)" in spec_text
    assert "hiddenimports.extend(collect_submodules(package_name))" in spec_text
    assert "datas.extend(copy_metadata(dist_name))" in spec_text
    assert "hiddenimports=_build_hiddenimports()," in spec_text
    assert "str(DEBUGPY_VENDORED_PYDEVD_ROOT)," in spec_text


def test_workspace_build_script_targets_publishable_packages_and_dist_dirs():
    script = _load_script_module("build_workspace_packages.py")

    assert [target.package for target in script.BUILD_TARGETS] == [
        "crawler4j-sdk",
        "crawler4j",
        "crawler4j-contracts",
    ]
    assert [target.dist_dir for target in script.BUILD_TARGETS] == [
        WORKSPACE_ROOT / "packages" / "crawler4j-sdk" / "dist",
        WORKSPACE_ROOT / "packages" / "crawler4j" / "dist",
        WORKSPACE_ROOT / "packages" / "crawler4j-contracts" / "dist",
    ]


def test_workspace_build_script_uses_uv_clear_for_each_target():
    script = _load_script_module("build_workspace_packages.py")
    target = script.BUILD_TARGETS[0]

    assert script.build_command(target) == [
        "uv",
        "build",
        "--package",
        "crawler4j-sdk",
        "--out-dir",
        str(WORKSPACE_ROOT / "packages" / "crawler4j-sdk" / "dist"),
        "--clear",
    ]


def test_workspace_build_script_preserves_desktop_subdir_for_root_package(tmp_path, monkeypatch):
    script = _load_script_module("build_workspace_packages.py")
    dist_dir = tmp_path / "crawler4j-dist"
    desktop_dir = dist_dir / "desktop" / "macos"
    desktop_dir.mkdir(parents=True)
    kept_marker = desktop_dir / "keep.txt"
    kept_marker.write_text("desktop artifact", encoding="utf-8")
    target = script.BuildTarget("crawler4j", dist_dir)

    def fake_run(command, *, cwd, check):
        assert command == script.build_command(target)
        assert cwd == script.WORKSPACE_ROOT
        assert check is True
        shutil.rmtree(dist_dir)
        dist_dir.mkdir(parents=True)
        (dist_dir / "crawler4j-0.2.0-py3-none-any.whl").write_text("wheel", encoding="utf-8")

    monkeypatch.setattr(script.subprocess, "run", fake_run)

    script.run_build(target)

    assert (dist_dir / "crawler4j-0.2.0-py3-none-any.whl").read_text(encoding="utf-8") == "wheel"
    assert kept_marker.read_text(encoding="utf-8") == "desktop artifact"


def test_workspace_build_script_parse_args_defaults_to_build_mode():
    script = _load_script_module("build_workspace_packages.py")

    args = script.parse_args(["crawler4j"])

    assert args.action == "build"
    assert args.packages == ["crawler4j"]
    assert args.dry_run is False


def test_workspace_build_script_parse_args_supports_publish_shorthand():
    script = _load_script_module("build_workspace_packages.py")

    args = script.parse_args(["publish", "crawler4j-sdk", "--dry-run"])

    assert args.action == "publish"
    assert args.packages == ["crawler4j-sdk"]
    assert args.dry_run is True


def test_workspace_build_script_uses_package_local_dist_glob_for_publish():
    script = _load_script_module("build_workspace_packages.py")
    target = script.BUILD_TARGETS[0]

    assert script.publish_command(target) == [
        "uv",
        "publish",
        str(WORKSPACE_ROOT / "packages" / "crawler4j-sdk" / "dist" / "*"),
    ]
    assert script.publish_command(target, dry_run=True) == [
        "uv",
        "publish",
        "--dry-run",
        str(WORKSPACE_ROOT / "packages" / "crawler4j-sdk" / "dist" / "*"),
    ]


def test_desktop_packaging_script_uses_fixed_platform_specific_paths():
    script = _load_script_module("package_desktop_app.py")

    assert script.platform_slug("darwin") == "macos"
    assert script.platform_slug("win32") == "windows"
    assert script.platform_slug("linux") == "linux"
    assert script.dist_dir("darwin") == WORKSPACE_ROOT / "packages" / "crawler4j" / "dist" / "desktop" / "macos"
    assert script.build_dir("darwin") == WORKSPACE_ROOT / "packages" / "crawler4j" / "build" / "pyinstaller" / "macos"
    assert script.build_command("darwin") == [
        "pyinstaller",
        "--noconfirm",
        "--clean",
        "--distpath",
        str(WORKSPACE_ROOT / "packages" / "crawler4j" / "dist" / "desktop" / "macos"),
        "--workpath",
        str(WORKSPACE_ROOT / "packages" / "crawler4j" / "build" / "pyinstaller" / "macos"),
        str(WORKSPACE_ROOT / "packages" / "crawler4j" / "crawler4j.spec"),
    ]


def test_desktop_packaging_script_cleans_and_recreates_fixed_output_dirs(tmp_path, monkeypatch):
    script = _load_script_module("package_desktop_app.py")
    monkeypatch.setattr(script, "DESKTOP_DIST_ROOT", tmp_path / "dist-root")
    monkeypatch.setattr(script, "PYINSTALLER_BUILD_ROOT", tmp_path / "build-root")

    stale_dist = script.dist_dir("windows")
    stale_build = script.build_dir("windows")
    stale_dist.mkdir(parents=True)
    stale_build.mkdir(parents=True)
    (stale_dist / "stale.txt").write_text("stale", encoding="utf-8")
    (stale_build / "stale.txt").write_text("stale", encoding="utf-8")

    target_dist, target_build = script.clean_output_dirs("windows")

    assert target_dist == stale_dist
    assert target_build == stale_build
    assert target_dist.exists()
    assert target_build.exists()
    assert not (target_dist / "stale.txt").exists()
    assert not (target_build / "stale.txt").exists()


def test_desktop_packaging_script_prunes_macos_collect_dir_after_app_bundle_build(tmp_path, monkeypatch):
    script = _load_script_module("package_desktop_app.py")
    monkeypatch.setattr(script, "DESKTOP_DIST_ROOT", tmp_path / "dist-root")

    target_dist = script.dist_dir("darwin")
    collect_dir = target_dist / script.APP_NAME
    app_bundle = target_dist / script.MACOS_APP_NAME
    collect_dir.mkdir(parents=True)
    app_bundle.mkdir(parents=True)

    removed = script.prune_macos_collect_dir("darwin")

    assert removed == collect_dir
    assert not collect_dir.exists()
    assert app_bundle.exists()

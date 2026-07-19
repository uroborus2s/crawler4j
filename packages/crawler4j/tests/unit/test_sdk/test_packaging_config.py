"""Packaging configuration regression tests for publishable subpackages."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import plistlib
import re
import shutil
import tarfile
import tomllib
from pathlib import Path

import pytest


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


def _write_test_sdist(path: Path, member_names: list[str]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for member_name in member_names:
            archive.addfile(tarfile.TarInfo(member_name))


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
    assert (
        _build_compatible_requirement("crawler4j-contracts", contracts_pyproject["project"]["version"]) in dependencies
    )


def test_sdk_runtime_version_matches_publish_metadata():
    package_root = WORKSPACE_ROOT / "packages" / "crawler4j-sdk"
    pyproject = _load_pyproject(package_root / "pyproject.toml")
    version_helper = _load_version_helper(package_root)

    assert version_helper.get_version() == pyproject["project"]["version"]
    assert version_helper.get_compatible_dependency_spec() == _build_compatible_requirement(
        "crawler4j-sdk",
        pyproject["project"]["version"],
    )
    assert _load_literal_module_version(package_root) is None


def test_sdk_contracts_dependency_spec_matches_current_contracts_version():
    package_root = WORKSPACE_ROOT / "packages" / "crawler4j-sdk"
    version_helper = _load_version_helper(package_root)
    contracts_pyproject = _load_pyproject(WORKSPACE_ROOT / "packages" / "crawler4j-contracts" / "pyproject.toml")

    assert version_helper.get_compatible_contracts_dependency_spec() == _build_compatible_requirement(
        "crawler4j-contracts",
        contracts_pyproject["project"]["version"],
    )


def test_sdk_pyproject_declares_same_contracts_range_as_version_helper():
    package_root = WORKSPACE_ROOT / "packages" / "crawler4j-sdk"
    version_helper = _load_version_helper(package_root)
    sdk_pyproject = _load_pyproject(package_root / "pyproject.toml")

    assert version_helper.get_compatible_contracts_dependency_spec() in sdk_pyproject["project"]["dependencies"]


def test_sdk_contracts_dependency_spec_prefers_installed_contracts_metadata_when_repo_pyproject_missing(
    tmp_path,
    monkeypatch,
):
    package_root = WORKSPACE_ROOT / "packages" / "crawler4j-sdk"
    version_helper = _load_version_helper(package_root)

    def fake_version(name: str) -> str:
        if name == version_helper.CONTRACTS_PACKAGE_NAME:
            return "0.3.2"
        if name == version_helper.PACKAGE_NAME:
            return "0.5.0"
        raise version_helper.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(version_helper.metadata, "version", fake_version)
    monkeypatch.setattr(version_helper, "CONTRACTS_PYPROJECT_PATH", tmp_path / "missing-pyproject.toml")

    assert version_helper.get_compatible_contracts_dependency_spec() == "crawler4j-contracts>=0.3.2,<0.4.0"


def test_sdk_contracts_dependency_spec_prefers_source_pyproject_inside_repo_checkout(tmp_path, monkeypatch):
    package_root = WORKSPACE_ROOT / "packages" / "crawler4j-sdk"
    version_helper = _load_version_helper(package_root)
    pyproject_path = tmp_path / "crawler4j-contracts.toml"
    pyproject_path.write_text('[project]\nversion = "0.3.7"\n', encoding="utf-8")

    def fake_version(name: str) -> str:
        if name == version_helper.CONTRACTS_PACKAGE_NAME:
            return "0.4.0"
        if name == version_helper.PACKAGE_NAME:
            return "0.5.0"
        raise version_helper.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(version_helper.metadata, "version", fake_version)
    monkeypatch.setattr(version_helper, "CONTRACTS_PYPROJECT_PATH", pyproject_path)

    assert version_helper.get_compatible_contracts_dependency_spec() == "crawler4j-contracts>=0.3.7,<0.4.0"


def test_sdk_readme_dependency_example_matches_generated_compatibility_ranges():
    package_root = WORKSPACE_ROOT / "packages" / "crawler4j-sdk"
    readme_text = (package_root / "README.md").read_text(encoding="utf-8")
    sdk_pyproject = _load_pyproject(package_root / "pyproject.toml")
    contracts_pyproject = _load_pyproject(WORKSPACE_ROOT / "packages" / "crawler4j-contracts" / "pyproject.toml")

    assert _build_compatible_requirement("crawler4j-contracts", contracts_pyproject["project"]["version"]) in readme_text
    assert _build_compatible_requirement("crawler4j-sdk", sdk_pyproject["project"]["version"]) in readme_text
    assert "crawler4j-contracts==<compatible-version>" not in readme_text
    assert "crawler4j-sdk==<compatible-version>" not in readme_text


def test_workspace_release_docs_reflect_current_versions_and_publish_order():
    root_readme = (WORKSPACE_ROOT / "README.md").read_text(encoding="utf-8")
    deployment_guide = (
        WORKSPACE_ROOT / "docs" / "04-project-development" / "08-operations-maintenance" / "deployment-guide.md"
    ).read_text(encoding="utf-8")
    contracts_version = _load_pyproject(WORKSPACE_ROOT / "packages" / "crawler4j-contracts" / "pyproject.toml")[
        "project"
    ]["version"]
    sdk_version = _load_pyproject(WORKSPACE_ROOT / "packages" / "crawler4j-sdk" / "pyproject.toml")["project"][
        "version"
    ]
    app_version = _load_pyproject(APP_ROOT / "pyproject.toml")["project"]["version"]

    assert f"| `crawler4j` | `{app_version}` |" in root_readme
    assert f"| `crawler4j-sdk` | `{sdk_version}` |" in root_readme
    assert f"| `crawler4j-contracts` | `{contracts_version}` |" in root_readme
    assert root_readme.index("uv run publish crawler4j-contracts") < root_readme.index(
        "uv run publish crawler4j-sdk"
    )
    assert deployment_guide.index("uv run publish crawler4j-contracts") < deployment_guide.index(
        "uv run publish crawler4j-sdk"
    )


def test_contracts_packaging_maps_flat_src_to_public_package_name():
    pyproject = _load_pyproject(WORKSPACE_ROOT / "packages" / "crawler4j-contracts" / "pyproject.toml")
    setuptools_cfg = pyproject["tool"]["setuptools"]
    assert pyproject["build-system"]["build-backend"] == "setuptools.build_meta"
    assert pyproject["project"]["dependencies"] == []
    assert setuptools_cfg["package-dir"][""] == "src"
    assert setuptools_cfg["packages"]["find"] == {
        "where": ["src"],
        "include": ["crawler4j_contracts*"],
    }
    assert setuptools_cfg["package-data"]["crawler4j_contracts"] == ["py.typed"]


def test_contracts_package_no_longer_ships_default_http_runtime():
    package_root = WORKSPACE_ROOT / "packages" / "crawler4j-contracts"
    context_path = package_root / "src" / "crawler4j_contracts" / "context.py"
    tree = ast.parse(context_path.read_text(encoding="utf-8"), filename=str(context_path))

    assert all(
        not (isinstance(node, ast.ClassDef) and node.name == "DefaultHttpClient")
        for node in tree.body
    )


def test_contracts_runtime_version_matches_publish_metadata():
    package_root = WORKSPACE_ROOT / "packages" / "crawler4j-contracts"
    pyproject = _load_pyproject(package_root / "pyproject.toml")
    assert pyproject["project"]["version"]
    assert not (package_root / "src" / "_version.py").exists()
    module_path = package_root / "src" / "crawler4j_contracts" / "__init__.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"), filename=str(module_path))
    assert all(
        not (
            isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets)
        )
        for node in tree.body
    )


def test_root_app_package_does_not_reexport_sdk_cli_command():
    pyproject = _load_pyproject(APP_ROOT / "pyproject.toml")
    contracts_pyproject = _load_pyproject(WORKSPACE_ROOT / "packages" / "crawler4j-contracts" / "pyproject.toml")
    dependencies = pyproject["project"]["dependencies"]
    scripts = pyproject["project"]["scripts"]

    assert scripts["start"] == "src.ui.app:main"
    assert "crawler4j" not in scripts
    assert (
        _build_compatible_requirement("crawler4j-contracts", contracts_pyproject["project"]["version"]) in dependencies
    )


def test_root_app_declares_http2_and_brotli_as_host_runtime_capabilities():
    pyproject = _load_pyproject(APP_ROOT / "pyproject.toml")

    assert "httpx[http2,brotli]>=0.28.1" in pyproject["project"]["dependencies"]
    assert "httpx>=0.28.1" not in pyproject["project"]["dependencies"]


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
    assert pyproject["project"]["scripts"]["deploy-windows-release"] == "scripts.deploy_windows_release:main"
    assert (
        pyproject["project"]["scripts"]["deploy-macos-internal-release"]
        == "scripts.deploy_macos_internal_release:main"
    )
    assert pyproject["project"]["scripts"]["install-sparkle"] == "scripts.install_sparkle_vendor:main"
    assert pyproject["project"]["scripts"]["package-desktop"] == "scripts.package_desktop_app:main"
    assert pyproject["project"]["scripts"]["package-windows-release"] == "scripts.package_windows_release:main"
    assert (
        pyproject["project"]["scripts"]["package-macos-internal-release"]
        == "scripts.package_macos_internal_release:main"
    )
    assert pyproject["project"]["scripts"]["publish"] == "scripts.build_workspace_packages:publish_main"
    assert pyproject["build-system"]["build-backend"] == "setuptools.build_meta"
    assert pyproject["tool"]["setuptools"]["packages"] == ["scripts"]


def test_dev_scripts_live_in_workspace_root_instead_of_app_package():
    root_scripts = WORKSPACE_ROOT / "scripts"
    package_scripts = APP_ROOT / "scripts"

    assert root_scripts.exists()
    assert {
        "build_workspace_packages.py",
        "deploy_macos_internal_release.py",
        "deploy_windows_release.py",
        "db_cli.py",
        "install_sparkle_vendor.py",
        "package_desktop_app.py",
        "package_windows_release.py",
        "package_macos_internal_release.py",
        "smoke_test_ui.py",
    }.issubset({path.name for path in root_scripts.glob("*.py")})
    assert list(package_scripts.glob("*.py")) == []


def test_root_app_runtime_does_not_keep_version_mirror_file():
    assert not (APP_ROOT / "src" / "__version__.py").exists()


def test_pyinstaller_spec_targets_real_ui_entry_and_runtime_assets():
    spec_text = (APP_ROOT / "crawler4j.spec").read_text(encoding="utf-8")
    paths_text = (APP_ROOT / "src" / "utils" / "paths.py").read_text(encoding="utf-8")

    assert 'APP_ENTRY = PROJECT_ROOT / "src" / "ui" / "app.py"' in spec_text
    assert "WORKSPACE_ROOT = PROJECT_ROOT.parents[1]" in spec_text
    assert 'DOCS_ROOT = WORKSPACE_ROOT / "docs"' in spec_text
    assert '(str(DOCS_ROOT / "index.md"), "docs")' in spec_text
    assert '(str(DOCS_ROOT / "01-getting-started"), "docs/01-getting-started")' in spec_text
    assert '(str(DOCS_ROOT / "02-user-guide"), "docs/02-user-guide")' in spec_text
    assert '(str(DOCS_ROOT / "03-developer-guide"), "docs/03-developer-guide")' in spec_text
    assert "if MODULES_DIR.exists():" in spec_text
    assert "datas=_build_datas()," in spec_text
    assert "sys.path.insert(0, str(PROJECT_ROOT))" in spec_text
    assert 'PROJECT_METADATA = PROJECT_ROOT / "pyproject.toml"' in spec_text
    assert "def _load_project_version" in spec_text
    assert "from src.__version__ import VERSION" not in spec_text
    assert "src/main.py" not in spec_text
    assert "dark_theme.qss" not in spec_text
    assert 'src/ui/styles' not in spec_text
    assert "def get_docs_root() -> Path:" in paths_text


def test_pyinstaller_spec_collects_workspace_runtime_packages_for_desktop_bundle():
    spec_text = (APP_ROOT / "crawler4j.spec").read_text(encoding="utf-8")

    assert "from importlib.metadata import PackageNotFoundError, distribution" in spec_text
    assert "from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata" in spec_text
    assert "import debugpy" in spec_text
    assert "DEBUGPY_ROOT = Path(debugpy.__file__).resolve().parent" in spec_text
    assert 'DEBUGPY_VENDORED_PYDEVD_ROOT = DEBUGPY_ROOT / "_vendored" / "pydevd"' in spec_text
    assert 'SINGLE_FILE_MODULE_RESOURCE_DISTS = ("sinanz",)' in spec_text
    assert "def _build_single_file_module_resource_datas() -> list[tuple[str, str]]:" in spec_text
    assert "datas.extend(_build_single_file_module_resource_datas())" in spec_text
    assert 'datas.extend(collect_data_files("debugpy"))' in spec_text
    assert 'datas.extend(collect_data_files("debugpy", include_py_files=True))' in spec_text
    assert '"debugpy",' in spec_text
    assert '"ddddocr",' not in spec_text
    assert '"cv2",' not in spec_text
    assert 'hiddenimports.extend(collect_submodules("debugpy"))' in spec_text
    assert "hiddenimports.extend(_build_debugpy_vendored_hiddenimports())" in spec_text
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


def test_pyinstaller_spec_collects_optional_host_http_runtime_packages():
    spec_text = (APP_ROOT / "crawler4j.spec").read_text(encoding="utf-8")

    assert 'HOST_HTTP_RUNTIME_PACKAGES = ("h2", "hpack", "hyperframe", "brotli")' in spec_text
    assert 'HOST_HTTP_RUNTIME_DISTS = ("httpx", "h2", "hpack", "hyperframe", "Brotli")' in spec_text
    assert "for package_name in HOST_HTTP_RUNTIME_PACKAGES:" in spec_text
    assert "hiddenimports.extend(collect_submodules(package_name))" in spec_text
    assert "for dist_name in HOST_HTTP_RUNTIME_DISTS:" in spec_text
    assert "datas.extend(copy_metadata(dist_name))" in spec_text


def test_workspace_build_script_targets_publishable_packages_and_dist_dirs():
    script = _load_script_module("build_workspace_packages.py")

    assert [target.package for target in script.BUILD_TARGETS] == [
        "crawler4j-contracts",
        "crawler4j-sdk",
        "crawler4j",
    ]
    assert [target.dist_dir for target in script.BUILD_TARGETS] == [
        WORKSPACE_ROOT / "packages" / "crawler4j-contracts" / "dist",
        WORKSPACE_ROOT / "packages" / "crawler4j-sdk" / "dist",
        WORKSPACE_ROOT / "packages" / "crawler4j" / "dist",
    ]


def test_workspace_build_script_uses_uv_clear_for_each_target():
    script = _load_script_module("build_workspace_packages.py")
    target = next(target for target in script.BUILD_TARGETS if target.package == "crawler4j-sdk")

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
        assert list(tmp_path.iterdir()) == [dist_dir]
        shutil.rmtree(dist_dir)
        dist_dir.mkdir(parents=True)
        (dist_dir / "crawler4j-test.whl").write_text("wheel", encoding="utf-8")
        _write_test_sdist(dist_dir / "crawler4j-test.tar.gz", ["crawler4j-test/README.md"])

    monkeypatch.setattr(script.subprocess, "run", fake_run)

    script.run_build(target)

    assert (dist_dir / "crawler4j-test.whl").read_text(encoding="utf-8") == "wheel"
    assert kept_marker.read_text(encoding="utf-8") == "desktop artifact"


def test_workspace_build_script_rejects_preserved_desktop_content_in_root_sdist(tmp_path, monkeypatch):
    script = _load_script_module("build_workspace_packages.py")
    dist_dir = tmp_path / "crawler4j-dist"
    target = script.BuildTarget("crawler4j", dist_dir)

    def fake_run(command, *, cwd, check):
        assert command == script.build_command(target)
        assert cwd == script.WORKSPACE_ROOT
        assert check is True
        dist_dir.mkdir(parents=True)
        _write_test_sdist(
            dist_dir / "crawler4j-test.tar.gz",
            ["crawler4j-test/tmp-build-preserve/desktop/macos/Crawler4j.app/Contents/MacOS/Crawler4j"],
        )

    monkeypatch.setattr(script.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="preserved desktop content"):
        script.run_build(target)


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
    target = next(target for target in script.BUILD_TARGETS if target.package == "crawler4j-sdk")

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


def test_release_packaging_helper_loads_project_version_from_app_pyproject():
    helper = _load_script_module("release_packaging_helpers.py")
    pyproject = _load_pyproject(APP_ROOT / "pyproject.toml")

    assert helper.load_project_version() == pyproject["project"]["version"]


def test_release_packaging_helper_parses_dotenv_export_and_quoted_values(tmp_path):
    helper = _load_script_module("release_packaging_helpers.py")
    dotenv_path = tmp_path / ".env.release"
    dotenv_path.write_text(
        "\n".join(
            [
                "# release env",
                "export CRAWLER4J_RELEASE_NAME=internal",
                'CRAWLER4J_RELEASE_URL="https://updates.example.com/feed.xml"',
                "CRAWLER4J_RELEASE_CHANNEL='beta'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert helper.load_dotenv_file(dotenv_path) == {
        "CRAWLER4J_RELEASE_NAME": "internal",
        "CRAWLER4J_RELEASE_URL": "https://updates.example.com/feed.xml",
        "CRAWLER4J_RELEASE_CHANNEL": "beta",
    }


def test_release_packaging_helper_resolve_runtime_env_merges_dotenv_os_and_explicit_env(tmp_path, monkeypatch):
    helper = _load_script_module("release_packaging_helpers.py")
    dotenv_path = tmp_path / ".env.release"
    dotenv_path.write_text(
        "FROM_DOTENV=dotenv\nSHARED_KEY=dotenv\nFROM_OS=dotenv-default\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("FROM_OS", "os")
    monkeypatch.setenv("SHARED_KEY", "os")

    env_map = helper.resolve_runtime_env(
        {"FROM_CALL": "call", "SHARED_KEY": "call"},
        env_file=dotenv_path,
    )

    assert env_map["FROM_DOTENV"] == "dotenv"
    assert env_map["FROM_OS"] == "os"
    assert env_map["FROM_CALL"] == "call"
    assert env_map["SHARED_KEY"] == "call"


def test_release_packaging_helper_reset_output_dir_removes_stale_files(tmp_path):
    helper = _load_script_module("release_packaging_helpers.py")
    output_dir = tmp_path / "updates"
    output_dir.mkdir()
    (output_dir / "stale.txt").write_text("stale", encoding="utf-8")

    reset_dir = helper.reset_output_dir(output_dir)

    assert reset_dir == output_dir.resolve()
    assert reset_dir.exists()
    assert not (reset_dir / "stale.txt").exists()


def test_platform_release_scripts_reuse_shared_runtime_env_helpers(tmp_path, monkeypatch):
    helper = importlib.import_module("scripts.release_packaging_helpers")
    macos_script = _load_script_module("package_macos_internal_release.py")
    windows_script = _load_script_module("package_windows_release.py")
    macos_dotenv = tmp_path / ".mac.env"
    windows_dotenv = tmp_path / ".win.env"
    macos_dotenv.write_text("SHARED_KEY=mac-dotenv\n", encoding="utf-8")
    windows_dotenv.write_text("SHARED_KEY=win-dotenv\n", encoding="utf-8")

    monkeypatch.setattr(macos_script, "DEFAULT_ENV_FILE", macos_dotenv)
    monkeypatch.setattr(windows_script, "DEFAULT_ENV_FILE", windows_dotenv)
    assert macos_script.resolve_runtime_env()["SHARED_KEY"] == helper.resolve_runtime_env(
        default_env_file=macos_dotenv
    )["SHARED_KEY"]
    assert windows_script.resolve_runtime_env()["SHARED_KEY"] == helper.resolve_runtime_env(
        default_env_file=windows_dotenv
    )["SHARED_KEY"]


def test_windows_release_config_reads_env_defaults():
    script = _load_script_module("package_windows_release.py")

    config = script.load_windows_release_config(
        {
            script.VELOPACK_FEED_URL_ENV: "https://updates.example.com/win/releases.win.json",
        }
    )

    assert config.feed_url == "https://updates.example.com/win/releases.win.json"
    assert config.pack_id == script.DEFAULT_PACK_ID
    assert config.channel == script.DEFAULT_CHANNEL
    assert config.runtime == script.DEFAULT_RUNTIME
    assert config.main_exe == f"{script.package_desktop_app.APP_NAME}.exe"
    assert config.vpk_bin == script.DEFAULT_VPK_BIN
    assert config.use_dnx is False


def test_windows_release_write_update_config_to_bundle(tmp_path):
    script = _load_script_module("package_windows_release.py")
    bundle_dir = tmp_path / "Crawler4j"
    bundle_dir.mkdir(parents=True)
    config = script.WindowsReleaseConfig(
        feed_url="https://updates.example.com/win/releases.win.json",
        pack_id="io.github.uroborus2s.crawler4j",
        channel="win",
        runtime="win-x64",
    )

    config_path = script.write_windows_update_config(bundle_dir, config)

    assert config_path == bundle_dir / script.UPDATE_CONFIG_FILENAME
    payload = script.json.loads(config_path.read_text(encoding="utf-8"))
    assert payload == {
        "feed_url": "https://updates.example.com/win/releases.win.json",
        "pack_id": "io.github.uroborus2s.crawler4j",
        "channel": "win",
    }


def test_windows_release_build_vpk_pack_command_uses_global_vpk(tmp_path):
    script = _load_script_module("package_windows_release.py")
    bundle_dir = tmp_path / "Crawler4j"
    output_dir = tmp_path / "updates"
    config = script.WindowsReleaseConfig(
        feed_url="https://updates.example.com/win/releases.win.json",
        pack_id="io.github.uroborus2s.crawler4j",
        channel="win",
        runtime="win-x64",
    )

    command = script.build_vpk_pack_command(bundle_dir, output_dir, version="0.2.0", config=config)

    assert command == [
        "vpk",
        "pack",
        "--packId",
        "io.github.uroborus2s.crawler4j",
        "--packVersion",
        "0.2.0",
        "--packDir",
        str(bundle_dir),
        "--outputDir",
        str(output_dir),
        "--channel",
        "win",
        "--runtime",
        "win-x64",
        "--mainExe",
        "Crawler4j.exe",
        "--packTitle",
        script.package_desktop_app.APP_NAME,
        "--icon",
        str(script.WINDOWS_PACKAGE_ICON.resolve()),
    ]


def test_windows_release_build_vpk_pack_command_uses_dnx_when_requested(tmp_path):
    script = _load_script_module("package_windows_release.py")
    bundle_dir = tmp_path / "Crawler4j"
    output_dir = tmp_path / "updates"
    config = script.WindowsReleaseConfig(
        feed_url="https://updates.example.com/win/releases.win.json",
        pack_id="io.github.uroborus2s.crawler4j",
        channel="win",
        runtime="win-x64",
        use_dnx=True,
    )

    command = script.build_vpk_pack_command(
        bundle_dir,
        output_dir,
        version="0.2.0",
        config=config,
        velopack_version="0.0.1298",
    )

    assert command[:5] == ["dnx", "vpk", "--version", "0.0.1298", "pack"]
    assert "--packId" in command
    assert "--mainExe" in command
    assert command[command.index("--icon") + 1] == str(script.WINDOWS_PACKAGE_ICON.resolve())


def test_windows_release_normalizes_dev_velopack_version_for_dnx():
    script = _load_script_module("package_windows_release.py")

    assert script.normalize_dnx_package_version("0.0.1589.dev41669") == "0.0.1589"
    assert script.normalize_dnx_package_version("0.0.1589+local") == "0.0.1589"
    assert script.normalize_dnx_package_version("0.0.1589") == "0.0.1589"


def test_windows_release_build_vpk_pack_command_wraps_batch_shims_with_cmd(tmp_path, monkeypatch):
    script = _load_script_module("package_windows_release.py")
    bundle_dir = tmp_path / "Crawler4j"
    output_dir = tmp_path / "updates"
    config = script.WindowsReleaseConfig(
        feed_url="https://updates.example.com/win/releases.win.json",
        pack_id="io.github.uroborus2s.crawler4j",
        channel="win",
        runtime="win-x64",
        use_dnx=True,
    )
    monkeypatch.setattr(script.shutil, "which", lambda name: r"C:\Program Files\dotnet\dnx.cmd" if name == "dnx" else None)

    command = script.build_vpk_pack_command(
        bundle_dir,
        output_dir,
        version="0.2.0",
        config=config,
        velopack_version="0.0.1298",
    )

    assert command[:7] == [
        script.os.environ.get("COMSPEC", "cmd.exe"),
        "/c",
        r"C:\Program Files\dotnet\dnx.cmd",
        "vpk",
        "--version",
        "0.0.1298",
        "pack",
    ]
    assert "--packId" in command
    assert command[command.index("--icon") + 1] == str(script.WINDOWS_PACKAGE_ICON.resolve())


def test_windows_release_build_vpk_pack_command_uses_normalized_dnx_version(tmp_path):
    script = _load_script_module("package_windows_release.py")
    bundle_dir = tmp_path / "Crawler4j"
    output_dir = tmp_path / "updates"
    config = script.WindowsReleaseConfig(
        feed_url="https://updates.example.com/win/releases.win.json",
        pack_id="io.github.uroborus2s.crawler4j",
        channel="win",
        runtime="win-x64",
        use_dnx=True,
    )

    command = script.build_vpk_pack_command(
        bundle_dir,
        output_dir,
        version="0.2.0",
        config=config,
        velopack_version="0.0.1589.dev41669",
    )

    version_index = command.index("--version") + 1
    assert command[version_index] == "0.0.1589"
    assert command[command.index("--icon") + 1] == str(script.WINDOWS_PACKAGE_ICON.resolve())


def test_windows_release_build_release_artifacts_cleans_output_dir_before_packaging(tmp_path, monkeypatch):
    script = _load_script_module("package_windows_release.py")
    bundle_dir = tmp_path / "Crawler4j"
    bundle_dir.mkdir()
    output_dir = tmp_path / "updates"
    output_dir.mkdir()
    (output_dir / "stale.txt").write_text("stale", encoding="utf-8")
    observed: dict[str, object] = {}

    config = script.WindowsReleaseConfig(
        feed_url="https://updates.example.com/win/releases.win.json",
        pack_id="io.github.uroborus2s.crawler4j",
        channel="win",
        runtime="win-x64",
    )

    monkeypatch.setattr(script.release_packaging_helpers, "load_project_version", lambda: "0.2.0")
    monkeypatch.setattr(script, "load_windows_release_config", lambda *args, **kwargs: config)
    monkeypatch.setattr(script, "windows_bundle_dir", lambda: bundle_dir)
    monkeypatch.setattr(script, "write_windows_update_config", lambda bundle, release_config: bundle / script.UPDATE_CONFIG_FILENAME)

    def fake_build_vpk_pack_command(bundle, destination, *, version, config, velopack_version=None):
        observed["bundle_dir"] = bundle
        observed["output_dir"] = destination
        observed["version"] = version
        return ["vpk", "pack"]

    def fake_run(command, *, cwd, check):
        observed["command"] = command
        observed["cwd"] = cwd
        observed["check"] = check

    monkeypatch.setattr(script, "build_vpk_pack_command", fake_build_vpk_pack_command)
    monkeypatch.setattr(script.subprocess, "run", fake_run)

    args = script.parse_args(["--skip-build", "--output-dir", str(output_dir)])
    artifacts = script.build_release_artifacts(args, env={script.VELOPACK_FEED_URL_ENV: config.feed_url})

    assert artifacts.output_dir == output_dir.resolve()
    assert artifacts.update_config_path == bundle_dir / script.UPDATE_CONFIG_FILENAME
    assert observed["bundle_dir"] == bundle_dir
    assert observed["output_dir"] == output_dir.resolve()
    assert observed["version"] == "0.2.0"
    assert observed["command"] == ["vpk", "pack"]
    assert observed["cwd"] == script.WORKSPACE_ROOT
    assert observed["check"] is True
    assert output_dir.exists()
    assert not (output_dir / "stale.txt").exists()


def test_macos_internal_release_config_reads_env_and_vendor_layout(tmp_path, monkeypatch):
    script = _load_script_module("package_macos_internal_release.py")
    sparkle_root = tmp_path / "sparkle"
    (sparkle_root / "Sparkle.framework").mkdir(parents=True)
    generate_appcast = sparkle_root / "bin" / "generate_appcast"
    generate_appcast.parent.mkdir(parents=True)
    generate_appcast.write_text("#!/bin/sh\n", encoding="utf-8")

    env = {
        script.SPARKLE_ROOT_ENV: str(sparkle_root),
        script.SPARKLE_FEED_URL_ENV: "https://example.com/appcast.xml",
        script.SPARKLE_PUBLIC_KEY_ENV: "sparkle-public-key",
    }

    config = script.load_sparkle_release_config(env)

    assert config.sparkle_root == sparkle_root.resolve()
    assert config.framework_path == sparkle_root.resolve() / "Sparkle.framework"
    assert config.feed_url == "https://example.com/appcast.xml"
    assert config.public_key == "sparkle-public-key"
    assert config.generate_appcast_tool == generate_appcast.resolve()


def test_macos_internal_release_config_reads_default_dotenv_when_present(tmp_path, monkeypatch):
    script = _load_script_module("package_macos_internal_release.py")
    sparkle_root = tmp_path / "sparkle"
    (sparkle_root / "Sparkle.framework").mkdir(parents=True)
    generate_appcast = sparkle_root / "bin" / "generate_appcast"
    generate_appcast.parent.mkdir(parents=True)
    generate_appcast.write_text("#!/bin/sh\n", encoding="utf-8")

    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "\n".join(
            [
                f"{script.SPARKLE_ROOT_ENV}='{sparkle_root}'",
                f"{script.SPARKLE_FEED_URL_ENV}='https://updates.example.com/mac/appcast.xml'",
                f"{script.SPARKLE_PUBLIC_KEY_ENV}='dotenv-public-key'",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(script, "DEFAULT_ENV_FILE", dotenv_path)

    config = script.load_sparkle_release_config()

    assert config.sparkle_root == sparkle_root.resolve()
    assert config.feed_url == "https://updates.example.com/mac/appcast.xml"
    assert config.public_key == "dotenv-public-key"
    assert config.generate_appcast_tool == generate_appcast.resolve()


def test_macos_internal_release_config_reads_private_key_overrides_from_env(tmp_path, monkeypatch):
    script = _load_script_module("package_macos_internal_release.py")
    sparkle_root = tmp_path / "sparkle"
    (sparkle_root / "Sparkle.framework").mkdir(parents=True)
    generate_appcast = sparkle_root / "bin" / "generate_appcast"
    generate_appcast.parent.mkdir(parents=True)
    generate_appcast.write_text("#!/bin/sh\n", encoding="utf-8")

    private_key_file = tmp_path / "sparkle-private-key.txt"
    private_key_file.write_text("private-key", encoding="utf-8")

    config = script.load_sparkle_release_config(
        {
            script.SPARKLE_ROOT_ENV: str(sparkle_root),
            script.SPARKLE_FEED_URL_ENV: "https://updates.example.com/mac/appcast.xml",
            script.SPARKLE_PUBLIC_KEY_ENV: "dotenv-public-key",
            script.SPARKLE_KEYCHAIN_ACCOUNT_ENV: "crawler4j-internal",
            script.SPARKLE_PRIVATE_KEY_FILE_ENV: str(private_key_file),
        }
    )

    assert config.keychain_account == "crawler4j-internal"
    assert config.private_key_file == private_key_file.resolve()
    assert config.private_key is None


def test_macos_internal_release_config_rejects_multiple_private_key_sources(tmp_path):
    script = _load_script_module("package_macos_internal_release.py")
    sparkle_root = tmp_path / "sparkle"
    (sparkle_root / "Sparkle.framework").mkdir(parents=True)
    generate_appcast = sparkle_root / "bin" / "generate_appcast"
    generate_appcast.parent.mkdir(parents=True)
    generate_appcast.write_text("#!/bin/sh\n", encoding="utf-8")

    private_key_file = tmp_path / "sparkle-private-key.txt"
    private_key_file.write_text("private-key", encoding="utf-8")

    try:
        script.load_sparkle_release_config(
            {
                script.SPARKLE_ROOT_ENV: str(sparkle_root),
                script.SPARKLE_FEED_URL_ENV: "https://updates.example.com/mac/appcast.xml",
                script.SPARKLE_PUBLIC_KEY_ENV: "dotenv-public-key",
                script.SPARKLE_PRIVATE_KEY_ENV: "private-key",
                script.SPARKLE_PRIVATE_KEY_FILE_ENV: str(private_key_file),
            }
        )
    except ValueError as exc:
        assert "只能设置一种" in str(exc)
    else:
        raise AssertionError("Expected ValueError when multiple private key sources are configured.")


def test_macos_internal_release_updates_bundle_plist_with_sparkle_keys(tmp_path):
    script = _load_script_module("package_macos_internal_release.py")
    app_bundle = tmp_path / "Crawler4j.app"
    plist_path = app_bundle / "Contents" / "Info.plist"
    plist_path.parent.mkdir(parents=True)
    with plist_path.open("wb") as f:
        plistlib.dump({"CFBundleVersion": "0.0.0"}, f)

    config = script.SparkleReleaseConfig(
        sparkle_root=tmp_path / "sparkle",
        feed_url="https://example.com/appcast.xml",
        public_key="sparkle-public-key",
        auto_check=True,
    )

    script.update_bundle_plist(app_bundle, version="0.2.0", config=config)

    with plist_path.open("rb") as f:
        data = plistlib.load(f)

    assert data["CFBundleVersion"] == "0.2.0"
    assert data["CFBundleShortVersionString"] == "0.2.0"
    assert data["SUFeedURL"] == "https://example.com/appcast.xml"
    assert data["SUPublicEDKey"] == "sparkle-public-key"
    assert data["SUEnableAutomaticChecks"] is True
    assert data["SUEnableCodeSigningValidation"] is False
    assert data["SUPackageSigningCertificate"] == ""


def test_macos_internal_release_codesign_bundle_command_is_stable(tmp_path):
    script = _load_script_module("package_macos_internal_release.py")
    app_bundle = tmp_path / "Crawler4j.app"

    assert script.codesign_bundle_command(app_bundle) == [
        "codesign",
        "--force",
        "--sign",
        "-",
        "--deep",
        "--timestamp=none",
        str(app_bundle),
    ]


def test_macos_internal_release_build_release_artifacts_resigns_bundle_before_packaging(tmp_path, monkeypatch):
    script = _load_script_module("package_macos_internal_release.py")
    app_bundle = tmp_path / "Crawler4j.app"
    (app_bundle / "Contents").mkdir(parents=True)
    output_dir = tmp_path / "updates"
    events: list[tuple[str, object]] = []

    config = script.SparkleReleaseConfig(
        sparkle_root=tmp_path / "sparkle",
        feed_url="https://example.com/appcast.xml",
        public_key="sparkle-public-key",
        auto_check=True,
    )

    monkeypatch.setattr(script, "load_sparkle_release_config", lambda env=None, env_file=None: config)
    monkeypatch.setattr(script.release_packaging_helpers, "load_project_version", lambda: "0.2.0")
    monkeypatch.setattr(script, "app_bundle_path", lambda: app_bundle)
    monkeypatch.setattr(
        script,
        "copy_sparkle_framework",
        lambda bundle, framework_source: events.append(("copy", bundle)) or (bundle / "Contents" / "Frameworks" / "Sparkle.framework"),
    )
    monkeypatch.setattr(
        script,
        "update_bundle_plist",
        lambda bundle, *, version, config: events.append(("plist", bundle)) or (bundle / "Contents" / "Info.plist"),
    )
    monkeypatch.setattr(script, "ad_hoc_sign_bundle", lambda bundle: events.append(("codesign", bundle)))
    monkeypatch.setattr(
        script,
        "create_dmg",
        lambda bundle, destination, *, version, volume_name: events.append(("dmg", bundle))
        or (destination / "Crawler4j-0.2.0.dmg"),
    )

    args = script.parse_args(["--skip-build", "--skip-appcast", "--output-dir", str(output_dir)])
    artifacts = script.build_release_artifacts(args)

    assert artifacts.app_bundle == app_bundle
    assert artifacts.output_dir == output_dir
    assert artifacts.dmg_path == output_dir / "Crawler4j-0.2.0.dmg"
    assert artifacts.appcast_generated is False
    assert events == [
        ("copy", app_bundle),
        ("plist", app_bundle),
        ("codesign", app_bundle),
        ("dmg", app_bundle),
    ]


def test_macos_internal_release_build_release_artifacts_cleans_output_dir_before_packaging(tmp_path, monkeypatch):
    script = _load_script_module("package_macos_internal_release.py")
    app_bundle = tmp_path / "Crawler4j.app"
    (app_bundle / "Contents").mkdir(parents=True)
    output_dir = tmp_path / "updates"
    output_dir.mkdir()
    (output_dir / "stale.txt").write_text("stale", encoding="utf-8")
    observed: dict[str, object] = {}

    config = script.SparkleReleaseConfig(
        sparkle_root=tmp_path / "sparkle",
        feed_url="https://example.com/appcast.xml",
        public_key="sparkle-public-key",
        auto_check=True,
    )

    monkeypatch.setattr(script, "load_sparkle_release_config", lambda env=None, env_file=None: config)
    monkeypatch.setattr(script.release_packaging_helpers, "load_project_version", lambda: "0.2.0")
    monkeypatch.setattr(script, "app_bundle_path", lambda: app_bundle)
    monkeypatch.setattr(script, "copy_sparkle_framework", lambda bundle, framework_source: bundle / "Contents" / "Frameworks" / "Sparkle.framework")
    monkeypatch.setattr(script, "update_bundle_plist", lambda bundle, *, version, config: bundle / "Contents" / "Info.plist")
    monkeypatch.setattr(script, "ad_hoc_sign_bundle", lambda bundle: None)

    def fake_create_dmg(bundle, destination, *, version, volume_name):
        observed["bundle"] = bundle
        observed["output_dir"] = destination
        observed["version"] = version
        observed["volume_name"] = volume_name
        return destination / "Crawler4j-0.2.0.dmg"

    monkeypatch.setattr(script, "create_dmg", fake_create_dmg)

    args = script.parse_args(["--skip-build", "--skip-appcast", "--output-dir", str(output_dir)])
    artifacts = script.build_release_artifacts(args)

    assert artifacts.output_dir == output_dir.resolve()
    assert observed["bundle"] == app_bundle
    assert observed["output_dir"] == output_dir.resolve()
    assert observed["version"] == "0.2.0"
    assert observed["volume_name"] == script.package_desktop_app.APP_NAME
    assert output_dir.exists()
    assert not (output_dir / "stale.txt").exists()


def test_macos_internal_release_copies_sparkle_framework_into_bundle(tmp_path):
    script = _load_script_module("package_macos_internal_release.py")
    app_bundle = tmp_path / "Crawler4j.app"
    app_bundle.mkdir()
    source = tmp_path / "sparkle-root" / "Sparkle.framework"
    resource = source / "Versions" / "A" / "Resources" / "Sparkle"
    resource.parent.mkdir(parents=True)
    resource.write_text("sparkle", encoding="utf-8")

    target = script.copy_sparkle_framework(app_bundle, source)

    assert target == app_bundle / "Contents" / "Frameworks" / "Sparkle.framework"
    assert (target / "Versions" / "A" / "Resources" / "Sparkle").read_text(encoding="utf-8") == "sparkle"


def test_macos_internal_release_create_dmg_uses_hdiutil_with_applications_symlink(tmp_path, monkeypatch):
    script = _load_script_module("package_macos_internal_release.py")
    app_bundle = tmp_path / "Crawler4j.app"
    (app_bundle / "Contents").mkdir(parents=True)
    mounted_volume = tmp_path / "Volumes" / "Crawler4j 2"
    mounted_volume.mkdir(parents=True)
    (mounted_volume / ".DS_Store").write_text("finder-layout", encoding="utf-8")

    captured: list[dict[str, object]] = []

    attach_plist = plistlib.dumps(
        {
            "system-entities": [
                {"dev-entry": "/dev/disk9"},
                {
                    "dev-entry": "/dev/disk9s1",
                    "mount-point": str(mounted_volume),
                },
            ]
        }
    )

    class FakeCompletedProcess:
        def __init__(self, stdout: bytes = b""):
            self.stdout = stdout

    def fake_run(command, *, cwd, check, **kwargs):
        captured.append(
            {
                "command": command,
                "cwd": cwd,
                "check": check,
                "kwargs": kwargs,
            }
        )
        if command[0:2] == ["hdiutil", "attach"]:
            return FakeCompletedProcess(stdout=attach_plist)
        return FakeCompletedProcess()

    monkeypatch.setattr(script.subprocess, "run", fake_run)

    dmg_path = script.create_dmg(app_bundle, tmp_path / "updates", version="0.2.0", volume_name="Crawler4j")

    assert dmg_path == tmp_path / "updates" / "Crawler4j-0.2.0.dmg"
    assert len(captured) == 6

    create_command = captured[0]["command"]
    assert isinstance(create_command, list)
    assert create_command[0:5] == ["hdiutil", "create", "-ov", "-volname", "Crawler4j"]
    assert create_command[5] == "-srcfolder"
    assert create_command[6] != ""
    assert create_command[7:11] == ["-fs", "HFS+", "-format", "UDRW"]
    assert str(create_command[-1]).endswith("Crawler4j-0.2.0-staging.dmg")
    staging_dmg_path = str(create_command[-1])

    attach_command = captured[1]["command"]
    assert attach_command == [
        "hdiutil",
        "attach",
        "-readwrite",
        "-noverify",
        "-noautoopen",
        "-plist",
        staging_dmg_path,
    ]
    assert captured[1]["kwargs"] == {"capture_output": True}

    osascript_command = captured[2]["command"]
    assert osascript_command[0:2] == ["osascript", "-e"]
    assert "set current view of container window to icon view" in osascript_command[2]
    assert 'tell disk "Crawler4j 2"' in osascript_command[2]
    assert 'set position of item "Crawler4j.app" of container window to {220, 250}' in osascript_command[2]
    assert 'set position of item "Applications" of container window to {560, 250}' in osascript_command[2]

    detach_command = captured[3]["command"]
    assert detach_command == ["hdiutil", "detach", str(tmp_path / "Volumes" / "Crawler4j 2")]

    makehybrid_command = captured[4]["command"]
    assert makehybrid_command[0:2] == ["hdiutil", "makehybrid"]
    assert makehybrid_command[2] == "-hfs"
    assert makehybrid_command[3] == "-default-volume-name"
    assert makehybrid_command[4] == "Crawler4j"
    assert makehybrid_command[5] == "-hfs-volume-name"
    assert makehybrid_command[6] == "Crawler4j"
    assert makehybrid_command[7] == "-hfs-openfolder"
    assert str(makehybrid_command[8]).endswith("Crawler4j-0.2.0-hybrid-source")
    assert makehybrid_command[9] == "-ov"
    assert makehybrid_command[10] == "-o"
    assert str(makehybrid_command[11]).endswith("Crawler4j-0.2.0-hybrid.dmg")
    assert makehybrid_command[12] == makehybrid_command[8]

    final_convert_command = captured[5]["command"]
    assert final_convert_command == [
        "hdiutil",
        "convert",
        str(makehybrid_command[11]),
        "-ov",
        "-format",
        "UDZO",
        "-o",
        str(tmp_path / "updates" / "Crawler4j-0.2.0.dmg"),
    ]

    assert all(call["cwd"] == script.WORKSPACE_ROOT for call in captured)
    assert all(call["check"] is True for call in captured)


def test_macos_internal_release_parse_hdiutil_attach_plist_extracts_mount_point(tmp_path):
    script = _load_script_module("package_macos_internal_release.py")
    output = plistlib.dumps(
        {
            "system-entities": [
                {"dev-entry": "/dev/disk8"},
                {
                    "dev-entry": "/dev/disk8s1",
                    "mount-point": str(tmp_path / "Volumes" / "Crawler4j"),
                },
            ]
        }
    )

    device, mount_point = script.parse_hdiutil_attach_plist(output)

    assert device == "/dev/disk8s1"
    assert mount_point == tmp_path / "Volumes" / "Crawler4j"


def test_macos_internal_release_generate_appcast_command_is_stable(tmp_path):
    script = _load_script_module("package_macos_internal_release.py")
    tool = tmp_path / "generate_appcast"
    updates_dir = tmp_path / "updates"

    assert script.generate_appcast_command(tool, updates_dir) == [str(tool), str(updates_dir)]


def test_macos_internal_release_generate_appcast_command_uses_private_key_file(tmp_path):
    script = _load_script_module("package_macos_internal_release.py")
    tool = tmp_path / "generate_appcast"
    updates_dir = tmp_path / "updates"
    config = script.SparkleReleaseConfig(
        sparkle_root=tmp_path / "sparkle",
        feed_url="https://example.com/appcast.xml",
        public_key="sparkle-public-key",
        private_key_file=tmp_path / "sparkle-private-key.txt",
    )

    assert script.generate_appcast_command(tool, updates_dir, config=config) == [
        str(tool),
        "--ed-key-file",
        str(tmp_path / "sparkle-private-key.txt"),
        str(updates_dir),
    ]


def test_macos_internal_release_generate_appcast_command_uses_keychain_account(tmp_path):
    script = _load_script_module("package_macos_internal_release.py")
    tool = tmp_path / "generate_appcast"
    updates_dir = tmp_path / "updates"
    config = script.SparkleReleaseConfig(
        sparkle_root=tmp_path / "sparkle",
        feed_url="https://example.com/appcast.xml",
        public_key="sparkle-public-key",
        keychain_account="crawler4j-release",
    )

    assert script.generate_appcast_command(tool, updates_dir, config=config) == [
        str(tool),
        "--account",
        "crawler4j-release",
        str(updates_dir),
    ]


def test_macos_internal_release_run_generate_appcast_reads_private_key_from_stdin(tmp_path, monkeypatch):
    script = _load_script_module("package_macos_internal_release.py")
    tool = tmp_path / "generate_appcast"
    updates_dir = tmp_path / "updates"
    config = script.SparkleReleaseConfig(
        sparkle_root=tmp_path / "sparkle",
        feed_url="https://example.com/appcast.xml",
        public_key="sparkle-public-key",
        private_key="private-key-secret",
    )
    captured: dict[str, object] = {}

    def fake_run(command, *, cwd, check, **kwargs):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["check"] = check
        captured["kwargs"] = kwargs

    monkeypatch.setattr(script.subprocess, "run", fake_run)

    script.run_generate_appcast(tool, updates_dir, config=config)

    assert captured["command"] == [str(tool), "--ed-key-file", "-", str(updates_dir)]
    assert captured["cwd"] == script.WORKSPACE_ROOT
    assert captured["check"] is True
    assert captured["kwargs"] == {"input": b"private-key-secret"}


def test_install_sparkle_vendor_locates_distribution_root_in_nested_tree(tmp_path):
    script = _load_script_module("install_sparkle_vendor.py")
    sparkle_root = tmp_path / "Sparkle-2.8.0"
    (sparkle_root / "Sparkle.framework").mkdir(parents=True)
    tool = sparkle_root / "bin" / "generate_appcast"
    tool.parent.mkdir(parents=True)
    tool.write_text("#!/bin/sh\n", encoding="utf-8")

    assert script.locate_distribution_root(tmp_path) == sparkle_root.resolve()


def test_install_sparkle_vendor_copies_distribution_into_target(tmp_path):
    script = _load_script_module("install_sparkle_vendor.py")
    source_root = tmp_path / "Sparkle-2.8.0"
    framework = source_root / "Sparkle.framework" / "Versions" / "A" / "Sparkle"
    tool = source_root / "bin" / "generate_appcast"
    framework.parent.mkdir(parents=True)
    tool.parent.mkdir(parents=True)
    framework.write_text("sparkle", encoding="utf-8")
    tool.write_text("#!/bin/sh\n", encoding="utf-8")

    target_dir = script.install_distribution(source_root, tmp_path / "vendor" / "sparkle", force=False)

    assert target_dir == (tmp_path / "vendor" / "sparkle").resolve()
    assert (target_dir / "Sparkle.framework" / "Versions" / "A" / "Sparkle").read_text(encoding="utf-8") == "sparkle"
    assert (target_dir / "bin" / "generate_appcast").read_text(encoding="utf-8") == "#!/bin/sh\n"


def test_deploy_macos_internal_release_builds_rsync_command_from_env(tmp_path):
    script = _load_script_module("deploy_macos_internal_release.py")
    source_dir = tmp_path / "updates"
    source_dir.mkdir()
    args = script.parse_args(["--dry-run"])

    upload_target = script.resolve_upload_target(
        args,
        {script.UPLOAD_TARGET_ENV: "deploy@example.internal:/srv/updates/crawler4j"},
    )
    command = script.build_rsync_command(source_dir, upload_target, dry_run=True)

    assert upload_target == "deploy@example.internal:/srv/updates/crawler4j/mac"
    assert command == [
        "rsync",
        "-av",
        "--dry-run",
        f"{source_dir.resolve()}/",
        "deploy@example.internal:/srv/updates/crawler4j/mac/",
    ]


def test_deploy_macos_internal_release_reads_default_dotenv_for_upload_target(tmp_path, monkeypatch):
    package_script = _load_script_module("package_macos_internal_release.py")
    script = _load_script_module("deploy_macos_internal_release.py")
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        f"{script.UPLOAD_TARGET_ENV}='sso.whzhsc.cn:/var/www/crawler4j/'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(package_script, "DEFAULT_ENV_FILE", dotenv_path)
    monkeypatch.setattr(script.package_macos_internal_release, "DEFAULT_ENV_FILE", dotenv_path)
    args = script.parse_args([])

    upload_target = script.resolve_upload_target(args)

    assert upload_target == "sso.whzhsc.cn:/var/www/crawler4j/mac"


def test_deploy_windows_release_builds_sftp_commands_from_env(tmp_path):
    script = _load_script_module("deploy_windows_release.py")
    source_dir = tmp_path / "updates"
    source_dir.mkdir()
    (source_dir / "Setup.exe").write_text("setup", encoding="utf-8")
    (source_dir / "releases.win.json").write_text("{}", encoding="utf-8")
    args = script.parse_args(["--dry-run"])

    upload_target = script.resolve_upload_target(
        args,
        {script.UPLOAD_TARGET_ENV: "deploy@example.internal:/srv/updates/crawler4j"},
    )
    target = script.parse_sftp_target(upload_target)
    command = script.build_sftp_command(target, tmp_path / "upload.batch")
    batch_commands = script.build_sftp_batch_commands(source_dir, target.remote_dir)

    assert upload_target == "deploy@example.internal:/srv/updates/crawler4j/win"
    assert target == script.SFTPTarget(
        host="deploy@example.internal",
        remote_dir="/srv/updates/crawler4j/win",
    )
    assert command == [
        "sftp",
        "-b",
        str((tmp_path / "upload.batch").resolve()),
        "deploy@example.internal",
    ]
    assert batch_commands == [
        "-mkdir /srv",
        "-mkdir /srv/updates",
        "-mkdir /srv/updates/crawler4j",
        "-mkdir /srv/updates/crawler4j/win",
        "cd /srv/updates/crawler4j/win",
        f"put {(source_dir / 'Setup.exe').resolve()} Setup.exe",
        f"put {(source_dir / 'releases.win.json').resolve()} releases.win.json",
    ]


def test_deploy_windows_release_reads_default_dotenv_for_upload_target(tmp_path, monkeypatch):
    package_script = _load_script_module("package_windows_release.py")
    script = _load_script_module("deploy_windows_release.py")
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        f"{script.UPLOAD_TARGET_ENV}='sso.whzhsc.cn:/var/www/crawler4j/'\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(package_script, "DEFAULT_ENV_FILE", dotenv_path)
    monkeypatch.setattr(script.package_windows_release, "DEFAULT_ENV_FILE", dotenv_path)
    args = script.parse_args([])

    upload_target = script.resolve_upload_target(args)

    assert upload_target == "sso.whzhsc.cn:/var/www/crawler4j/win"

from __future__ import annotations

import tomllib
import zipfile
from pathlib import Path

import pytest

from crawler4j_sdk._version import (
    get_compatible_contracts_dependency_spec,
    get_compatible_sdk_dependency_spec,
)

from ._helpers import MODULE_VERSION, archive_members, load_manifest, run_cli


def test_sdk_cli_scaffold_acceptance_writes_current_dependency_ranges(module_root: Path):
    with (module_root / "pyproject.toml").open("rb") as fh:
        generated_pyproject = tomllib.load(fh)

    assert generated_pyproject["project"]["dependencies"] == [get_compatible_contracts_dependency_spec()]
    assert generated_pyproject["dependency-groups"]["dev"] == [
        get_compatible_sdk_dependency_spec(),
        "pytest>=9.0.2",
        "pytest-asyncio>=1.3.0",
    ]


def test_sdk_cli_scaffold_to_package_verify_acceptance(rich_module_root: Path, built_archive: Path):
    check_result = run_cli("check", "full", cwd=rich_module_root)
    check_result.assert_ok()
    check_result.assert_stdout_contains("full 校验通过")

    verify_result = run_cli("package", "verify", str(built_archive), cwd=rich_module_root)
    verify_result.assert_ok()
    verify_result.assert_stdout_contains("ZIP 校验通过")

    manifest = load_manifest(rich_module_root)
    with (rich_module_root / "pyproject.toml").open("rb") as fh:
        generated_pyproject = tomllib.load(fh)
    assert manifest["name"] == "demo_model"
    assert manifest["version"] == MODULE_VERSION
    assert manifest["runtime_api"] == "core-native-v2"
    for legacy_key in ("default_workflow", "workflows", "data", "objects", "interfaces", "tasks"):
        assert legacy_key not in manifest
    assert generated_pyproject["project"]["dependencies"] == [get_compatible_contracts_dependency_spec()]
    assert generated_pyproject["dependency-groups"]["dev"] == [
        get_compatible_sdk_dependency_spec(),
        "pytest>=9.0.2",
        "pytest-asyncio>=1.3.0",
    ]
    assert "ui_extension" not in manifest

    members = archive_members(built_archive)
    assert "demo_model/module.yaml" in members
    assert "demo_model/.crawler4j/manifest.lock.json" in members
    assert "demo_model/pages/dashboard.py" in members
    assert "demo_model/pages/accounts.py" in members
    assert "demo_model/tasks/extra_task.py" in members
    assert "demo_model/workflows/repair_orders.py" in members
    assert "demo_model/env_selectors/pick_ready.py" not in members
    assert "demo_model/module_runtime.py" not in members


def test_sdk_cli_scaffold_package_verify_rejects_legacy_module_runtime_acceptance(module_root: Path):
    (module_root / "module_runtime.py").write_text("# legacy runtime shim\n", encoding="utf-8")
    archive_path = module_root / "dist" / "demo_model-with-runtime-shim.zip"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in module_root.rglob("*"):
            if path.is_file() and "dist" not in path.relative_to(module_root).parts:
                archive.write(path, f"demo_model/{path.relative_to(module_root).as_posix()}")

    verify_result = run_cli("package", "verify", str(archive_path), cwd=module_root)
    verify_result.assert_failed()
    verify_result.assert_stdout_contains("core-native-v2 模块不允许保留旧运行时薄壳: module_runtime.py")


def test_sdk_cli_scaffold_supports_grouped_page_source_layout_acceptance(module_root: Path):
    page_result = run_cli("page", "create", "account_detail", "--group", "account", cwd=module_root)
    page_result.assert_ok()
    lock_result = run_cli("manifest", "lock", cwd=module_root)
    lock_result.assert_ok()

    check_result = run_cli("check", "full", cwd=module_root)
    check_result.assert_ok()

    package_result = run_cli("package", "build", cwd=module_root)
    package_result.assert_ok()

    archive_path = module_root / "dist" / f"{module_root.name}-{MODULE_VERSION}.zip"
    assert archive_path.exists()

    verify_result = run_cli("package", "verify", str(archive_path), cwd=module_root)
    verify_result.assert_ok()

    manifest = load_manifest(module_root)
    assert "ui_extension" not in manifest

    members = archive_members(archive_path)
    assert "demo_model/pages/account/detail.py" in members


@pytest.mark.parametrize("extra_name", ["ui/", "config_schema.json", "strategy.yaml"])
def test_sdk_cli_scaffold_rejects_additional_legacy_module_artifacts_acceptance(
    rich_module_root: Path,
    extra_name: str,
):
    if extra_name == "ui/":
        extra_ui_dir = rich_module_root / "ui"
        extra_ui_dir.mkdir()
        (extra_ui_dir / "custom_page.py").write_text("class CustomPage: ...\n", encoding="utf-8")
    else:
        (rich_module_root / extra_name).write_text("{}", encoding="utf-8")

    result = run_cli("package", "build", cwd=rich_module_root)
    result.assert_failed()
    if extra_name == "ui/":
        result.assert_stdout_contains("残留旧 UI 目录: ui/")
    else:
        result.assert_stdout_contains(f"残留旧 UI 文件: {extra_name}")

from __future__ import annotations

from pathlib import Path

import pytest

from ._helpers import MODULE_VERSION, archive_members, load_manifest, run_cli


def test_sdk_cli_scaffold_to_package_verify_acceptance(rich_module_root: Path, built_archive: Path):
    check_result = run_cli("check", "full", cwd=rich_module_root)
    check_result.assert_ok()
    check_result.assert_stdout_contains("full 校验通过")

    verify_result = run_cli("package", "verify", str(built_archive), cwd=rich_module_root)
    verify_result.assert_ok()
    verify_result.assert_stdout_contains("ZIP 校验通过")

    manifest = load_manifest(rich_module_root)
    assert manifest["name"] == "demo_model"
    assert manifest["version"] == MODULE_VERSION
    assert manifest["ui_extension"]["pages"] == [
        {
            "id": "dashboard",
            "label": "Dashboard",
            "icon": "📄",
        },
        {
            "id": "accounts",
            "label": "Accounts",
            "icon": "📄",
        },
    ]
    assert [item["name"] for item in manifest["workflows"]] == ["main_workflow", "repair_orders"]

    members = archive_members(built_archive)
    assert "demo_model/module.yaml" in members
    assert "demo_model/module_runtime.py" in members
    assert "demo_model/pages/dashboard.py" in members
    assert "demo_model/pages/accounts.py" in members
    assert "demo_model/env_selectors/pick_ready.py" in members
    assert "demo_model/tasks/extra_task.py" in members
    assert "demo_model/workflows/repair_orders.py" in members


@pytest.mark.parametrize("extra_name", ["ui/", "config_schema.json", "strategy.yaml"])
def test_sdk_cli_scaffold_allows_additional_module_artifacts_acceptance(
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
    result.assert_ok()

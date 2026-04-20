from __future__ import annotations

from pathlib import Path

from ._helpers import load_manifest, run_cli, save_manifest


def test_release_status_reports_ready_for_reusable_release_fixture(
    rich_module_root: Path,
    built_archive: Path,
):
    result = run_cli("release", "status", cwd=rich_module_root)

    result.assert_ok()
    result.assert_stdout_contains("发布状态: READY")
    result.assert_stdout_contains(f"安装包: {built_archive}")


def test_release_status_reports_blocked_when_manifest_drifts(rich_module_root: Path):
    manifest = load_manifest(rich_module_root)
    manifest["upgrade_source"]["repo"] = "invalid-repo"
    save_manifest(rich_module_root, manifest)

    result = run_cli("release", "status", cwd=rich_module_root)

    result.assert_failed()
    result.assert_stdout_contains("发布状态: BLOCKED")
    result.assert_stdout_contains("upgrade_source.repo 必须是 owner/repo 形式")

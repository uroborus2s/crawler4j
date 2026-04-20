from __future__ import annotations

from pathlib import Path

from ._helpers import get_host_app_data_dir, load_manifest, run_cli


def test_host_install_preview_and_apply_local_zip_acceptance(
    rich_module_root: Path,
    built_archive: Path,
    host_home: Path,
):
    devlink_result = run_cli(
        "host",
        "devlink",
        "add",
        str(rich_module_root),
        cwd=rich_module_root,
        home=host_home,
    )
    devlink_result.assert_ok()

    preview_result = run_cli(
        "host",
        "install",
        "preview",
        str(built_archive),
        "--skip-remote-check",
        cwd=rich_module_root,
        home=host_home,
    )
    preview_result.assert_ok()
    preview_result.assert_stdout_contains("安装来源: 本地 ZIP（跳过远端仓库校验）")
    preview_result.assert_stdout_contains("模块名: demo_model")

    apply_result = run_cli(
        "host",
        "install",
        "apply",
        str(built_archive),
        "--skip-remote-check",
        cwd=rich_module_root,
        home=host_home,
    )
    apply_result.assert_ok()
    apply_result.assert_stdout_contains("模块安装完成")

    installed_root = get_host_app_data_dir(host_home) / "modules" / "demo_model"
    assert installed_root.exists()
    installed_manifest = load_manifest(installed_root)
    assert installed_manifest["name"] == "demo_model"

    list_result = run_cli("host", "devlink", "list", cwd=rich_module_root, home=host_home)
    list_result.assert_ok()
    list_result.assert_stdout_contains("(无 DevLink)")

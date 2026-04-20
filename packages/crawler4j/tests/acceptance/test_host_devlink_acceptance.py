from __future__ import annotations

from pathlib import Path

from ._helpers import get_host_app_data_dir, run_cli


def test_host_devlink_add_list_remove_acceptance(module_root: Path, host_home: Path):
    add_result = run_cli("host", "devlink", "add", str(module_root), cwd=module_root, home=host_home)
    add_result.assert_ok()
    add_result.assert_stdout_contains("已注册 DevLink 模块")

    list_result = run_cli("host", "devlink", "list", cwd=module_root, home=host_home)
    list_result.assert_ok()
    list_result.assert_stdout_contains("demo_model")
    list_result.assert_stdout_contains(str(module_root.resolve()))

    remove_result = run_cli("host", "devlink", "remove", "demo_model", cwd=module_root, home=host_home)
    remove_result.assert_ok()
    remove_result.assert_stdout_contains("已移除 DevLink: demo_model")

    list_after_remove = run_cli("host", "devlink", "list", cwd=module_root, home=host_home)
    list_after_remove.assert_ok()
    list_after_remove.assert_stdout_contains("(无 DevLink)")

    assert (get_host_app_data_dir(host_home) / "config.db").exists()

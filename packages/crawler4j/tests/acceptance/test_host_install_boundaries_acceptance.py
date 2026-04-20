from __future__ import annotations

from pathlib import Path

import pytest

from ._helpers import run_cli


@pytest.mark.parametrize("action", ["preview", "apply"])
def test_host_install_rejects_directory_source_and_points_to_devlink(
    module_root: Path,
    host_home: Path,
    action: str,
):
    result = run_cli(
        "host",
        "install",
        action,
        str(module_root),
        "--skip-remote-check",
        cwd=module_root,
        home=host_home,
    )

    result.assert_failed()
    result.assert_stdout_contains("目录源码请走 `crawler4j host devlink add <module_root>`，不要走 install")

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest


QT_BOUND_TESTS = {
    "tests/unit/test_core/test_atm/test_run_profile_dialog.py",
    "tests/unit/test_core/test_atm/test_task_debug_dialog.py",
    "tests/unit/test_core/test_mms/test_module_detail_page.py",
    "tests/unit/test_core/test_mms/test_module_data_table_page.py",
    "tests/unit/test_core/test_mms/test_module_list_widget.py",
    "tests/unit/test_core/test_rem/test_env_list_widget.py",
}


def _pyqt_available() -> bool:
    probe = (
        "from PyQt6.QtWidgets import QApplication;"
        "app = QApplication([]);"
        "print('ok')"
    )
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")

    try:
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
            check=False,
        )
    except Exception:
        return False

    return completed.returncode == 0 and "ok" in completed.stdout


PYQT_AVAILABLE = _pyqt_available()


def pytest_ignore_collect(collection_path: Path, config) -> bool:  # noqa: ARG001
    if PYQT_AVAILABLE:
        return False

    normalized_path = collection_path.as_posix()
    return any(normalized_path.endswith(target) for target in QT_BOUND_TESTS)


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    if PYQT_AVAILABLE:
        return

    skip_marker = pytest.mark.skip(reason="PyQt6 runtime unavailable on this machine")
    for item in items:
        normalized_path = str(item.path).replace("\\", "/")
        if any(normalized_path.endswith(target) for target in QT_BOUND_TESTS):
            item.add_marker(skip_marker)

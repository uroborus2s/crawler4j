"""Headless UI smoke test for workspace development."""

from __future__ import annotations

import faulthandler
import os
import sys
from pathlib import Path


faulthandler.enable()
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j"
sys.path.insert(0, str(APP_ROOT))


def test_ui_instantiation() -> int:
    print("Initializing QApplication...")
    try:
        from PyQt6.QtWidgets import QApplication

        qt_app = QApplication.instance() or QApplication(sys.argv)
    except Exception as exc:
        print(f"FAILED to init QApplication: {exc}")
        return 1

    print("Importing Shell...")
    try:
        from src.ui.shell import Shell
    except Exception as exc:
        print(f"FAILED to import Shell: {exc}")
        import traceback

        traceback.print_exc()
        return 1

    print("Instantiating Shell...")
    try:
        window = Shell()
        window.close()
        qt_app.quit()
        print("Shell instantiated successfully.")
        print("Test Passed.")
        return 0
    except Exception as exc:
        print(f"FAILED to instantiate Shell: {exc}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(test_ui_instantiation())

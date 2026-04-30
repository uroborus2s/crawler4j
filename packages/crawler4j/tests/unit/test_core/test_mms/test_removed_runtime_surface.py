import importlib
from pathlib import Path

import pytest

def _assert_removed_module(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError) as exc_info:
        importlib.import_module(module_name)

    assert exc_info.value.name == module_name


def test_removed_legacy_runtime_and_ui_surface_stays_unavailable():
    workspace_root = Path(__file__).resolve().parents[6]
    removed_paths = [
        workspace_root / "packages" / "crawler4j-sdk" / "src" / "assembler.py",
        workspace_root / "packages" / "crawler4j-sdk" / "src" / "base.py",
        workspace_root / "packages" / "crawler4j-sdk" / "src" / "env_selector.py",
        workspace_root / "packages" / "crawler4j-sdk" / "src" / "hosted_ui.py",
        workspace_root / "packages" / "crawler4j-sdk" / "src" / "result.py",
        workspace_root / "packages" / "crawler4j-sdk" / "src" / "resource_pool.py",
        workspace_root / "packages" / "crawler4j-sdk" / "src" / "signal.py",
        workspace_root / "packages" / "crawler4j-sdk" / "src" / "workflow.py",
        workspace_root / "packages" / "crawler4j" / "src" / "automation",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "core",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "components" / "sidebar.py",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "components" / "config_editor.py",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "components" / "log_viewer.py",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "components" / "status_bar.py",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "assets" / "arrow_down.svg",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "assets" / "arrow_up.svg",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "styles" / "dark_theme.qss",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "utils" / "syntax_highlighter.py",
    ]
    removed_modules = [
        "crawler4j_sdk.assembler",
        "crawler4j_sdk.base",
        "crawler4j_sdk.env_selector",
        "crawler4j_sdk.hosted_ui",
        "crawler4j_sdk.result",
        "crawler4j_sdk.resource_pool",
        "crawler4j_sdk.signal",
        "crawler4j_sdk.workflow",
        "src.ui.core",
        "src.ui.components.sidebar",
        "src.ui.components.config_editor",
        "src.ui.components.log_viewer",
        "src.ui.components.status_bar",
        "src.ui.utils.syntax_highlighter",
        "src.utils.async_utils",
        "src.utils.captcha_solver",
        "src.utils.fingerprint_generator",
        "src.utils.hotel_matcher",
        "src.utils.network_checker",
        "src.utils.sms_platform",
    ]

    for path in removed_paths:
        assert path.exists() is False

    for module_name in removed_modules:
        _assert_removed_module(module_name)

    sdk_root = importlib.import_module("crawler4j_sdk")
    assert hasattr(sdk_root, "TaskContext") is False
    assert hasattr(sdk_root, "TaskResult") is False


def test_legacy_declaration_specs_are_removed_from_contracts_package():
    _assert_removed_module("crawler4j_contracts.specs")

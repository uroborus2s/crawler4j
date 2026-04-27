import ast
from pathlib import Path

from PyQt6.QtCore import Qt


PROJECT_ROOT = Path(__file__).resolve().parents[5]
CORE_UI_ROOT = PROJECT_ROOT / "packages" / "crawler4j" / "src" / "core"
PUBLIC_UI_REFACTORED_PAGES = (
    PROJECT_ROOT / "packages" / "crawler4j" / "src" / "ui" / "dashboard.py",
    CORE_UI_ROOT / "atm" / "ui" / "run_profile_dialog.py",
    CORE_UI_ROOT / "atm" / "ui" / "task_confirmation_dialog.py",
    CORE_UI_ROOT / "atm" / "ui" / "task_detail_dialog.py",
    CORE_UI_ROOT / "atm" / "ui" / "task_debug_dialog.py",
    CORE_UI_ROOT / "mms" / "ui" / "module_detail_page.py",
    CORE_UI_ROOT / "mms" / "ui" / "module_install_dialog.py",
    CORE_UI_ROOT / "mms" / "ui" / "module_list_widget.py",
    CORE_UI_ROOT / "rem" / "ui" / "ip_pool_dialogs.py",
    CORE_UI_ROOT / "system" / "ui" / "about_dialog.py",
    CORE_UI_ROOT / "system" / "ui" / "help_page.py",
    CORE_UI_ROOT / "system" / "ui" / "settings_page.py",
)


def test_core_ui_does_not_depend_on_native_message_button_box_or_progress_bar():
    forbidden = ("QMessageBox", "QDialogButtonBox", "QProgressBar")
    offenders: list[str] = []

    for path in CORE_UI_ROOT.glob("**/ui/*.py"):
        text = path.read_text(encoding="utf-8")
        hits = [token for token in forbidden if token in text]
        if hits:
            offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {', '.join(hits)}")

    assert offenders == []


def test_core_ui_popups_do_not_use_frameless_windows():
    offenders: list[str] = []
    for path in CORE_UI_ROOT.glob("**/ui/*.py"):
        if "FramelessWindowHint" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert offenders == []


def test_core_ui_dialogs_use_public_titled_dialog_helper():
    offenders: list[str] = []
    for path in CORE_UI_ROOT.glob("**/ui/*.py"):
        text = path.read_text(encoding="utf-8")
        if ("(QDialog)" in text or "QDialog(" in text) and "configure_titled_dialog" not in text:
            offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert offenders == []


def test_refactored_core_ui_pages_do_not_import_raw_form_widgets_from_qt() -> None:
    forbidden = {"QPushButton", "QCheckBox", "QLineEdit", "QPlainTextEdit", "QTextEdit"}
    offenders: list[str] = []

    for path in PUBLIC_UI_REFACTORED_PAGES:
        module = ast.parse(path.read_text(encoding="utf-8"))
        raw_imports: set[str] = set()
        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom) and node.module == "PyQt6.QtWidgets":
                raw_imports.update(alias.name for alias in node.names if alias.name in forbidden)
        if raw_imports:
            offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {', '.join(sorted(raw_imports))}")

    assert offenders == []


def test_public_dialog_components_expose_async_entrypoints():
    from src.ui.components.choice_dialog import ChoiceDialog
    from src.ui.components.confirm_dialog import ConfirmDialog
    from src.ui.components.message_dialog import MessageDialog
    from src.ui.components.progress_dialog import ProgressDialog

    assert callable(MessageDialog.show_async)
    assert callable(MessageDialog.information_async)
    assert callable(MessageDialog.warning_async)
    assert callable(MessageDialog.error_async)
    assert callable(ConfirmDialog.confirm_async)
    assert callable(ConfirmDialog.delete_confirm_async)
    assert callable(ChoiceDialog.choose_async)
    assert callable(ProgressDialog.open_progress)


def test_public_dialog_components_keep_native_title_bars(qtbot):
    from src.ui.components.choice_dialog import ChoiceDialog, DialogChoice
    from src.ui.components.confirm_dialog import ConfirmDialog
    from src.ui.components.message_dialog import MessageDialog
    from src.ui.components.progress_dialog import ProgressDialog

    dialogs = [
        MessageDialog("提示", "内容"),
        ConfirmDialog("确认", "继续吗？"),
        ChoiceDialog("选择", "请选择", choices=[DialogChoice("ok", "确认", "success")]),
        ProgressDialog("处理中", "请稍候"),
    ]
    for dialog in dialogs:
        qtbot.addWidget(dialog)
        assert dialog.windowTitle()
        assert not dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
        assert dialog.windowFlags() & Qt.WindowType.WindowType_Mask == Qt.WindowType.Window
        assert dialog.windowFlags() & Qt.WindowType.Window
        assert dialog.windowFlags() & Qt.WindowType.WindowTitleHint

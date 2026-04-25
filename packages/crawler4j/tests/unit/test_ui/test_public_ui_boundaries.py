from pathlib import Path

from PyQt6.QtCore import Qt


PROJECT_ROOT = Path(__file__).resolve().parents[5]
CORE_UI_ROOT = PROJECT_ROOT / "packages" / "crawler4j" / "src" / "core"


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
        assert dialog.windowFlags() & Qt.WindowType.WindowTitleHint

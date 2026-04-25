from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[5]
CORE_UI_ROOT = PROJECT_ROOT / "packages" / "crawler4j" / "src" / "core"


def test_core_ui_does_not_depend_on_native_message_or_button_box():
    forbidden = ("QMessageBox", "QDialogButtonBox")
    offenders: list[str] = []

    for path in CORE_UI_ROOT.glob("**/ui/*.py"):
        text = path.read_text(encoding="utf-8")
        hits = [token for token in forbidden if token in text]
        if hits:
            offenders.append(f"{path.relative_to(PROJECT_ROOT)}: {', '.join(hits)}")

    assert offenders == []


def test_public_dialog_components_expose_async_entrypoints():
    from src.ui.components.choice_dialog import ChoiceDialog
    from src.ui.components.confirm_dialog import ConfirmDialog
    from src.ui.components.message_dialog import MessageDialog

    assert callable(MessageDialog.show_async)
    assert callable(MessageDialog.information_async)
    assert callable(MessageDialog.warning_async)
    assert callable(MessageDialog.error_async)
    assert callable(ConfirmDialog.confirm_async)
    assert callable(ConfirmDialog.delete_confirm_async)
    assert callable(ChoiceDialog.choose_async)

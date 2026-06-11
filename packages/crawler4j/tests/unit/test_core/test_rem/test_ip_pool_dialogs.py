from src.core.rem.ui.ip_pool_dialogs import AddIPDialog, AddPoolDialog
from src.ui.components.combo_box import StyledComboBox
from src.ui.components.text_edit import StyledPlainTextEdit


def test_add_pool_dialog_uses_styled_combo_box(qtbot):
    dialog = AddPoolDialog()
    qtbot.addWidget(dialog)

    assert isinstance(dialog.strategy_combo, StyledComboBox)
    assert "QComboBox {" not in dialog.styleSheet()


def test_add_pool_dialog_exposes_least_recently_used_strategy(qtbot):
    dialog = AddPoolDialog()
    qtbot.addWidget(dialog)

    labels = [dialog.strategy_combo.itemText(index) for index in range(dialog.strategy_combo.count())]

    assert "最久未使用" in labels


def test_add_ip_dialog_uses_styled_combo_box(qtbot):
    dialog = AddIPDialog(pool_id="pool-1")
    qtbot.addWidget(dialog)

    assert isinstance(dialog.protocol_combo, StyledComboBox)
    assert "QComboBox {" not in dialog.styleSheet()


def test_batch_import_dialog_uses_public_plain_text_edit(qtbot):
    from src.core.rem.ui.ip_pool_dialogs import BatchImportDialog

    dialog = BatchImportDialog(pool_id="pool-1")
    qtbot.addWidget(dialog)

    assert isinstance(dialog.text_edit, StyledPlainTextEdit)
    assert "QPlainTextEdit {" not in dialog.styleSheet()

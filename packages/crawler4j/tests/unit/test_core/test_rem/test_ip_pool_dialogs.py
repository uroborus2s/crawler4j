from src.core.rem.ui.ip_pool_dialogs import AddIPDialog, AddPoolDialog
from src.ui.components.combo_box import StyledComboBox


def test_add_pool_dialog_uses_styled_combo_box(qtbot):
    dialog = AddPoolDialog()
    qtbot.addWidget(dialog)

    assert isinstance(dialog.strategy_combo, StyledComboBox)
    assert "QComboBox {" not in dialog.styleSheet()


def test_add_ip_dialog_uses_styled_combo_box(qtbot):
    dialog = AddIPDialog(pool_id="pool-1")
    qtbot.addWidget(dialog)

    assert isinstance(dialog.protocol_combo, StyledComboBox)
    assert "QComboBox {" not in dialog.styleSheet()

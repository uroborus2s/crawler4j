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


def test_add_ip_dialog_returns_manual_location_with_fixed_fingerprint_geo(qtbot):
    dialog = AddIPDialog(pool_id="pool-1")
    qtbot.addWidget(dialog)
    dialog.address_input.setText("10.0.0.8")
    dialog.latitude_input.setText("39.9072")
    dialog.longitude_input.setText("116.357")
    assert not hasattr(dialog, "country_input")
    assert not hasattr(dialog, "timezone_input")
    assert not hasattr(dialog, "language_input")

    entry = dialog.get_values()

    assert entry.manual_latitude == 39.9072
    assert entry.manual_longitude == 116.357
    assert entry.fingerprint_geo() == {
        "country": "CN",
        "timezone": "Asia/Shanghai",
        "language": "zh-CN,zh,en-US,en",
        "latitude": 39.9072,
        "longitude": 116.357,
    }


def test_batch_import_dialog_uses_public_plain_text_edit(qtbot):
    from src.core.rem.ui.ip_pool_dialogs import BatchImportDialog

    dialog = BatchImportDialog(pool_id="pool-1")
    qtbot.addWidget(dialog)

    assert isinstance(dialog.text_edit, StyledPlainTextEdit)
    assert "QPlainTextEdit {" not in dialog.styleSheet()

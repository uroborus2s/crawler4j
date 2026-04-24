from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel

from src.ui.components.card import Card


def test_card_renders_title_and_shared_surface(qtbot):
    card = Card(title="付款提醒")
    qtbot.addWidget(card)

    assert card.objectName() == "sharedCard"
    assert card.title_label is not None
    assert card.title_label.text() == "付款提醒"
    assert "QFrame#sharedCard" in card.styleSheet()
    assert "QFrame {" not in card.styleSheet()
    assert "border-radius: 18px;" in card.styleSheet()
    assert "QLabel#cardTitle" in card.styleSheet()


def test_card_supports_layout_params(qtbot):
    card = Card(
        title="活跃作业",
        title_align="center",
        content_align="center",
        content_vertical_align="center",
        min_height=180,
        padding=24,
    )
    qtbot.addWidget(card)
    card.content_layout.addWidget(QLabel("0"))

    margins = card.frame_layout.contentsMargins()

    assert card.title_align == "center"
    assert card.content_align == "center"
    assert card.content_vertical_align == "center"
    assert card.minimumHeight() == 180
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (24, 24, 24, 24)
    assert card.title_label is not None
    assert card.title_label.alignment() == Qt.AlignmentFlag.AlignHCenter
    assert card.frame_layout.itemAt(1).spacerItem() is not None
    assert card.frame_layout.itemAt(2).widget() is card.content_container
    assert card.frame_layout.itemAt(3).spacerItem() is not None
    assert card.content_row_layout.itemAt(0).spacerItem() is not None
    assert card.content_row_layout.itemAt(1).widget() is card.content_widget
    assert card.content_row_layout.itemAt(2).spacerItem() is not None

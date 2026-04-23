from src.ui.components.card import Card


def test_card_renders_title_and_shared_surface(qtbot):
    card = Card(title="付款提醒")
    qtbot.addWidget(card)

    assert card.title_label is not None
    assert card.title_label.text() == "付款提醒"
    assert "border-radius: 18px;" in card.styleSheet()
    assert "QLabel#cardTitle" in card.styleSheet()


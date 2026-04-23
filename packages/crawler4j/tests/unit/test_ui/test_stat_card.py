from src.ui.components.stat_card import StatCard


def test_stat_card_renders_value_subtitle_and_delta(qtbot):
    card = StatCard(
        "转化率",
        "18.3%",
        subtitle="较昨日",
        accent_color="#34d399",
        delta_text="12.5%",
        delta_direction="up",
    )
    qtbot.addWidget(card)

    assert card.minimumHeight() == 96
    assert card.maximumHeight() == 108
    assert card.title_label.text() == "转化率"
    assert card.value_label.text() == "18.3%"
    assert card.subtitle_label.text() == "较昨日"
    assert card.subtitle_label.isHidden() is False
    assert card.delta_label.text() == "↑ 12.5%"
    assert "#34d399" in card.styleSheet()
    assert "#4ade80" in card.delta_label.styleSheet()


def test_stat_card_setters_support_hiding_and_direction_changes(qtbot):
    card = StatCard("订单数", "24")
    qtbot.addWidget(card)

    assert card.subtitle_label.isHidden() is True
    assert card.delta_label.isHidden() is True

    card.set_subtitle("过去 24 小时")
    card.set_delta("3.2%", direction="down")

    assert card.subtitle_label.text() == "过去 24 小时"
    assert card.subtitle_label.isHidden() is False
    assert card.delta_label.text() == "↓ 3.2%"
    assert "#f87171" in card.delta_label.styleSheet()

    card.set_delta("")
    assert card.delta_label.text() == ""
    assert card.delta_label.isHidden() is True

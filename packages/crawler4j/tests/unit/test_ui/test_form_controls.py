from PyQt6.QtCore import QRect
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QStyle, QStyleOptionComboBox, QStyleOptionSpinBox

from src.ui.components.combo_box import StyledComboBox
from src.ui.components.spin_box import StyledDoubleSpinBox, StyledSpinBox


def _count_light_pixels(image, rect, *, min_lightness: int = 170) -> int:
    bounded = rect.intersected(image.rect())
    count = 0
    for x in range(bounded.left(), bounded.right() + 1):
        for y in range(bounded.top(), bounded.bottom() + 1):
            if QColor(image.pixel(x, y)).lightness() >= min_lightness:
                count += 1
    return count


def _scale_rect_for_image(rect: QRect, device_pixel_ratio: float) -> QRect:
    return QRect(
        int(rect.left() * device_pixel_ratio),
        int(rect.top() * device_pixel_ratio),
        max(1, int(rect.width() * device_pixel_ratio)),
        max(1, int(rect.height() * device_pixel_ratio)),
    )


def test_styled_combo_box_uses_css_triangle_arrow(qtbot):
    combo = StyledComboBox()
    qtbot.addWidget(combo)
    combo.addItems(["持续保活", "批次任务"])
    combo.resize(180, 36)
    combo.show()
    qtbot.waitExposed(combo)

    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    arrow_rect = combo.style().subControlRect(
        QStyle.ComplexControl.CC_ComboBox,
        option,
        QStyle.SubControl.SC_ComboBoxArrow,
        combo,
    )
    pixmap = combo.grab()
    image = pixmap.toImage()
    arrow_rect = _scale_rect_for_image(arrow_rect, pixmap.devicePixelRatio())

    style = combo.styleSheet()

    assert "QComboBox {" in style
    assert "QComboBox {{" not in style
    assert "QComboBox::down-arrow" in style
    assert "image: none;" in style
    assert "border: none;" in style
    assert "width: 0px;" in style
    assert "height: 0px;" in style
    assert _count_light_pixels(image, arrow_rect) >= 6


def test_styled_spin_box_uses_css_triangle_arrows(qtbot):
    spin = StyledSpinBox()
    qtbot.addWidget(spin)
    spin.resize(160, 36)
    spin.show()
    qtbot.waitExposed(spin)

    option = QStyleOptionSpinBox()
    spin.initStyleOption(option)
    up_rect = spin.style().subControlRect(
        QStyle.ComplexControl.CC_SpinBox,
        option,
        QStyle.SubControl.SC_SpinBoxUp,
        spin,
    )
    down_rect = spin.style().subControlRect(
        QStyle.ComplexControl.CC_SpinBox,
        option,
        QStyle.SubControl.SC_SpinBoxDown,
        spin,
    )
    pixmap = spin.grab()
    image = pixmap.toImage()
    up_rect = _scale_rect_for_image(up_rect, pixmap.devicePixelRatio())
    down_rect = _scale_rect_for_image(down_rect, pixmap.devicePixelRatio())

    style = spin.styleSheet()

    assert "QSpinBox::up-arrow" in style
    assert "QSpinBox::down-arrow" in style
    assert "image: none;" in style
    assert "border: none;" in style
    assert "width: 0px;" in style
    assert "height: 0px;" in style
    assert _count_light_pixels(image, up_rect) >= 4
    assert _count_light_pixels(image, down_rect) >= 4


def test_styled_double_spin_box_uses_css_triangle_arrows(qtbot):
    spin = StyledDoubleSpinBox()
    qtbot.addWidget(spin)
    spin.resize(160, 36)
    spin.show()
    qtbot.waitExposed(spin)

    option = QStyleOptionSpinBox()
    spin.initStyleOption(option)
    up_rect = spin.style().subControlRect(
        QStyle.ComplexControl.CC_SpinBox,
        option,
        QStyle.SubControl.SC_SpinBoxUp,
        spin,
    )
    down_rect = spin.style().subControlRect(
        QStyle.ComplexControl.CC_SpinBox,
        option,
        QStyle.SubControl.SC_SpinBoxDown,
        spin,
    )
    pixmap = spin.grab()
    image = pixmap.toImage()
    up_rect = _scale_rect_for_image(up_rect, pixmap.devicePixelRatio())
    down_rect = _scale_rect_for_image(down_rect, pixmap.devicePixelRatio())

    style = spin.styleSheet()

    assert "QDoubleSpinBox::up-arrow" in style
    assert "QDoubleSpinBox::down-arrow" in style
    assert _count_light_pixels(image, up_rect) >= 4
    assert _count_light_pixels(image, down_rect) >= 4

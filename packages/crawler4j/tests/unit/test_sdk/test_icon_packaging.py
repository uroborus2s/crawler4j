from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QImage


APP_ROOT = Path(__file__).resolve().parents[3]


def test_pyinstaller_spec_binds_runtime_and_bundle_icon_assets():
    spec_text = (APP_ROOT / "crawler4j.spec").read_text(encoding="utf-8")

    assert 'RUNTIME_ICON = PROJECT_ROOT / "src" / "ui" / "assets" / "app_icon.png"' in spec_text
    assert 'BUNDLE_ICON = PROJECT_ROOT / "src" / "ui" / "assets" / "app_icon.icns"' in spec_text
    assert '(str(RUNTIME_ICON), "src/ui/assets")' in spec_text
    assert "icon=str(BUNDLE_ICON) if IS_MAC else None," in spec_text
    assert 'icon=str(BUNDLE_ICON),' in spec_text


def test_shared_app_icon_assets_exist_and_legacy_jpg_is_removed():
    assets_root = APP_ROOT / "src" / "ui" / "assets"

    assert (assets_root / "app_icon.png").exists()
    assert (assets_root / "app_icon.icns").exists()
    assert not (assets_root / "app_icon.svg").exists()
    assert not (assets_root / "icon.jpg").exists()


def test_runtime_app_icon_uses_transparent_outer_corners():
    image = QImage(str(APP_ROOT / "src" / "ui" / "assets" / "app_icon.png"))

    assert not image.isNull()
    for x, y in (
        (0, 0),
        (20, 20),
        (40, 40),
        (60, 60),
        (1023, 0),
        (1003, 20),
        (983, 40),
        (963, 60),
        (0, 1023),
        (20, 1003),
        (40, 983),
        (60, 963),
        (1023, 1023),
        (1003, 1003),
        (983, 983),
        (963, 963),
    ):
        assert image.pixelColor(x, y).alpha() == 0

    width = image.width()
    height = image.height()
    center_x = width // 2
    center_y = height // 2
    left_inset = next(x for x in range(width) if image.pixelColor(x, center_y).alpha() > 0)
    right_inset = next((width - 1) - x for x in range(width) if image.pixelColor((width - 1) - x, center_y).alpha() > 0)
    top_inset = next(y for y in range(height) if image.pixelColor(center_x, y).alpha() > 0)
    bottom_inset = next((height - 1) - y for y in range(height) if image.pixelColor(center_x, (height - 1) - y).alpha() > 0)
    assert left_inset >= 50
    assert right_inset >= 50
    assert top_inset >= 50
    assert bottom_inset >= 50


def test_runtime_app_icon_uses_light_warm_background_with_blue_brand_badge_and_center_mark():
    image = QImage(str(APP_ROOT / "src" / "ui" / "assets" / "app_icon.png"))

    assert not image.isNull()
    background = image.pixelColor(160, 160)
    assert background.alpha() > 0
    assert background.red() >= background.green() >= background.blue()
    assert background.lightness() > 240

    badge = image.pixelColor(image.width() // 2, 340)
    assert badge.blue() > badge.green() > badge.red()

    center_mark = image.pixelColor(620, 520)
    assert center_mark.lightness() > 245

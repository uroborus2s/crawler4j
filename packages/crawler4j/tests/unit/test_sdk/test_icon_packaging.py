from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QImage


APP_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_PLATE_INSETS = (97, 96, 97, 96)
EXPECTED_BLUE_BADGE_BBOX = (210, 210, 815, 815)
EXPECTED_FOCUS_BBOX = (210, 210, 846, 850)


def test_pyinstaller_spec_binds_runtime_and_bundle_icon_assets():
    spec_text = (APP_ROOT / "crawler4j.spec").read_text(encoding="utf-8")

    assert 'RUNTIME_ICON = PROJECT_ROOT / "src" / "ui" / "assets" / "app_icon.png"' in spec_text
    assert 'MACOS_BUNDLE_ICON = PROJECT_ROOT / "src" / "ui" / "assets" / "app_icon.icns"' in spec_text
    assert 'WINDOWS_BUNDLE_ICON = PROJECT_ROOT / "src" / "ui" / "assets" / "app_icon.ico"' in spec_text
    assert '(str(RUNTIME_ICON), "src/ui/assets")' in spec_text
    assert "IS_WINDOWS = sys.platform.startswith(\"win\")" in spec_text
    assert "icon=str(MACOS_BUNDLE_ICON) if IS_MAC else str(WINDOWS_BUNDLE_ICON) if IS_WINDOWS else None," in spec_text
    assert 'icon=str(MACOS_BUNDLE_ICON),' in spec_text


def test_shared_app_icon_assets_exist_and_legacy_jpg_is_removed():
    assets_root = APP_ROOT / "src" / "ui" / "assets"

    assert (assets_root / "app_icon_master.png").exists()
    assert (assets_root / "app_icon.png").exists()
    assert (assets_root / "app_icon.icns").exists()
    assert (assets_root / "app_icon.ico").exists()
    assert not (assets_root / "app_icon.svg").exists()
    assert not (assets_root / "icon.jpg").exists()


def test_runtime_app_icon_uses_transparent_outer_corners_and_locked_plate_insets():
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
    left_inset = next(x for x in range(width) if image.pixelColor(x, center_y).alpha() > 220)
    right_inset = next(x for x in range(width) if image.pixelColor((width - 1) - x, center_y).alpha() > 220)
    top_inset = next(y for y in range(height) if image.pixelColor(center_x, y).alpha() > 220)
    bottom_inset = next(y for y in range(height) if image.pixelColor(center_x, (height - 1) - y).alpha() > 220)
    assert (left_inset, right_inset, top_inset, bottom_inset) == EXPECTED_PLATE_INSETS


def test_runtime_app_icon_locks_blue_badge_bbox_to_prevent_optical_regression():
    image = QImage(str(APP_ROOT / "src" / "ui" / "assets" / "app_icon.png"))

    assert not image.isNull()
    coords: list[tuple[int, int]] = []
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if (
                color.alpha() > 200
                and color.blue() > 180
                and color.green() > 120
                and color.red() < 130
            ):
                coords.append((x, y))

    xs = [x for x, _ in coords]
    ys = [y for _, y in coords]
    assert (min(xs), min(ys), max(xs) + 1, max(ys) + 1) == EXPECTED_BLUE_BADGE_BBOX
    left_margin = min(xs)
    right_margin = image.width() - (max(xs) + 1)
    top_margin = min(ys)
    bottom_margin = image.height() - (max(ys) + 1)
    assert abs(left_margin - right_margin) <= 1
    assert abs(top_margin - bottom_margin) <= 1


def test_runtime_app_icon_locks_magnifier_group_bbox_while_plate_insets_stay_fixed():
    image = QImage(str(APP_ROOT / "src" / "ui" / "assets" / "app_icon.png"))

    assert not image.isNull()
    coords: list[tuple[int, int]] = []
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            if color.alpha() < 30:
                continue
            if (
                color.red() > 220
                and color.green() > 215
                and color.blue() > 210
                and abs(color.red() - color.green()) < 15
                and abs(color.green() - color.blue()) < 20
            ):
                continue
            coords.append((x, y))

    xs = [x for x, _ in coords]
    ys = [y for _, y in coords]
    assert (min(xs), min(ys), max(xs) + 1, max(ys) + 1) == EXPECTED_FOCUS_BBOX


def test_runtime_app_icon_uses_light_warm_background_with_blue_brand_badge_and_center_mark():
    image = QImage(str(APP_ROOT / "src" / "ui" / "assets" / "app_icon.png"))

    assert not image.isNull()
    background = image.pixelColor(160, 160)
    assert background.alpha() > 0
    assert background.red() >= background.green() >= background.blue()
    assert background.lightness() > 240

    badge = image.pixelColor(image.width() // 2, 340)
    assert badge.blue() > badge.green() > badge.red()

    center_mark = image.pixelColor(470, 560)
    assert center_mark.lightness() > 245

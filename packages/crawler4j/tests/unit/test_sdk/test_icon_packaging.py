from __future__ import annotations

from pathlib import Path


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

    assert (assets_root / "app_icon.svg").exists()
    assert (assets_root / "app_icon.png").exists()
    assert (assets_root / "app_icon.icns").exists()
    assert not (assets_root / "icon.jpg").exists()

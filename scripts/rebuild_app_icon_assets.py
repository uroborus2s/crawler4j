"""Rebuild shared app icon assets from the checked-in master artwork."""

from __future__ import annotations

from pathlib import Path

from PIL import Image


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j" / "src" / "ui" / "assets"
MASTER_ICON = ASSETS_ROOT / "app_icon_master.png"
RUNTIME_ICON = ASSETS_ROOT / "app_icon.png"
MACOS_ICON = ASSETS_ROOT / "app_icon.icns"
WINDOWS_ICON = ASSETS_ROOT / "app_icon.ico"
ICON_SCALE = 0.965
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def build_runtime_icon() -> Image.Image:
    source = Image.open(MASTER_ICON).convert("RGBA")
    if source.width != source.height:
        raise ValueError(f"{MASTER_ICON} must be square")

    canvas = Image.new("RGBA", source.size, (0, 0, 0, 0))
    scaled_size = tuple(round(length * ICON_SCALE) for length in source.size)
    scaled = source.resize(scaled_size, Image.Resampling.LANCZOS)
    offset = (
        (canvas.width - scaled.width) // 2,
        (canvas.height - scaled.height) // 2,
    )
    canvas.alpha_composite(scaled, offset)
    return canvas


def main() -> None:
    runtime_icon = build_runtime_icon()
    runtime_icon.save(RUNTIME_ICON)
    runtime_icon.save(MACOS_ICON)
    runtime_icon.save(WINDOWS_ICON, sizes=ICO_SIZES)
    print(f"rebuilt {RUNTIME_ICON}")
    print(f"rebuilt {MACOS_ICON}")
    print(f"rebuilt {WINDOWS_ICON}")


if __name__ == "__main__":
    main()

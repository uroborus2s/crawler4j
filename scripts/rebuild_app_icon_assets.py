"""Render the canonical desktop app icon and rebuild png/icns/ico outputs."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j" / "src" / "ui" / "assets"
MASTER_ICON = ASSETS_ROOT / "app_icon_master.png"
RUNTIME_ICON = ASSETS_ROOT / "app_icon.png"
MACOS_ICON = ASSETS_ROOT / "app_icon.icns"
WINDOWS_ICON = ASSETS_ROOT / "app_icon.ico"
ICO_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

CANVAS_SIZE = 1024
# Dock 光学尺寸仍由外底板占画布比例决定；本轮保持镜面正中，并把手柄延长到更接近边缘的安全区。
PLATE_BOX = (97, 97, 927, 927)
PLATE_RADIUS = 180
BADGE_CENTER = (512, 512)
BADGE_OUTER_RADIUS = 332
BADGE_INNER_RADIUS = 302
HANDLE_START = (748, 748)
HANDLE_END = (824, 824)
HANDLE_WIDTH = 42
HANDLE_HIGHLIGHT_START = (760, 760)
HANDLE_HIGHLIGHT_END = (810, 810)
HANDLE_HIGHLIGHT_WIDTH = 12
BADGE_TEXT_CENTER = (480, 554)
BADGE_TEXT_SIZE = 398
BADGE_DOT_BOX = (640, 328, 690, 378)


def _draw_capsule(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], *, width: int, fill) -> None:
    draw.line((start, end), fill=fill, width=width)
    radius = width // 2
    draw.ellipse((start[0] - radius, start[1] - radius, start[0] + radius, start[1] + radius), fill=fill)
    draw.ellipse((end[0] - radius, end[1] - radius, end[0] + radius, end[1] + radius), fill=fill)


def _load_badge_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _build_plate_mask() -> Image.Image:
    mask = Image.new("L", (CANVAS_SIZE, CANVAS_SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(PLATE_BOX, radius=PLATE_RADIUS, fill=255)
    return mask


def _build_plate() -> Image.Image:
    plate = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    mask = _build_plate_mask()
    left, top, right, bottom = PLATE_BOX

    for y in range(top, bottom):
        for x in range(left, right):
            if mask.getpixel((x, y)) == 0:
                continue
            t = (x + y) / (2 * CANVAS_SIZE)
            plate.putpixel((x, y), (250 - int(8 * t), 248 - int(10 * t), 246 - int(8 * t), 255))

    draw = ImageDraw.Draw(plate)
    draw.rounded_rectangle(PLATE_BOX, radius=PLATE_RADIUS, outline=(255, 255, 255, 110), width=4)

    highlight = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(highlight).rounded_rectangle(
        (left + 6, top + 6, right - 6, bottom - 6),
        radius=PLATE_RADIUS - 6,
        outline=(255, 255, 255, 70),
        width=3,
    )
    plate.alpha_composite(highlight.filter(ImageFilter.GaussianBlur(4)))
    plate.putalpha(mask)
    return plate


def _build_plate_shadow() -> Image.Image:
    shadow = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    left, top, right, bottom = PLATE_BOX
    ImageDraw.Draw(shadow).rounded_rectangle(
        (left + 2, top + 10, right + 2, bottom + 10),
        radius=PLATE_RADIUS,
        fill=(60, 50, 40, 42),
    )
    return shadow.filter(ImageFilter.GaussianBlur(18))


def _build_group_shadow() -> Image.Image:
    shadow = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)
    cx, cy = BADGE_CENTER
    draw.ellipse(
        (
            cx - BADGE_OUTER_RADIUS + 6,
            cy - BADGE_OUTER_RADIUS + 10,
            cx + BADGE_OUTER_RADIUS + 6,
            cy + BADGE_OUTER_RADIUS + 10,
        ),
        fill=(30, 60, 120, 46),
    )
    _draw_capsule(draw, HANDLE_START, HANDLE_END, width=HANDLE_WIDTH + 8, fill=(50, 55, 75, 42))
    return shadow.filter(ImageFilter.GaussianBlur(18))


def _build_badge() -> Image.Image:
    badge = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(badge)
    cx, cy = BADGE_CENTER

    draw.ellipse(
        (cx - BADGE_OUTER_RADIUS, cy - BADGE_OUTER_RADIUS, cx + BADGE_OUTER_RADIUS, cy + BADGE_OUTER_RADIUS),
        fill=(248, 248, 249, 255),
    )

    blue_fill = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    blue_mask = Image.new("L", (CANVAS_SIZE, CANVAS_SIZE), 0)
    ImageDraw.Draw(blue_mask).ellipse(
        (cx - BADGE_INNER_RADIUS, cy - BADGE_INNER_RADIUS, cx + BADGE_INNER_RADIUS, cy + BADGE_INNER_RADIUS),
        fill=255,
    )
    for y in range(cy - BADGE_INNER_RADIUS, cy + BADGE_INNER_RADIUS):
        for x in range(cx - BADGE_INNER_RADIUS, cx + BADGE_INNER_RADIUS):
            if blue_mask.getpixel((x, y)) == 0:
                continue
            t = (y - (cy - BADGE_INNER_RADIUS)) / (2 * BADGE_INNER_RADIUS)
            blue_fill.putpixel((x, y), (92 - int(18 * t), 164 - int(28 * t), 244 - int(18 * t), 255))
    blue_fill.putalpha(blue_mask)
    badge.alpha_composite(blue_fill)

    draw.ellipse(
        (cx - BADGE_INNER_RADIUS, cy - BADGE_INNER_RADIUS, cx + BADGE_INNER_RADIUS, cy + BADGE_INNER_RADIUS),
        outline=(108, 172, 244, 255),
        width=3,
    )
    return badge


def _build_handle() -> Image.Image:
    handle = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(handle)
    _draw_capsule(draw, HANDLE_START, HANDLE_END, width=HANDLE_WIDTH, fill=(224, 226, 233, 255))
    _draw_capsule(
        draw,
        HANDLE_HIGHLIGHT_START,
        HANDLE_HIGHLIGHT_END,
        width=HANDLE_HIGHLIGHT_WIDTH,
        fill=(210, 214, 224, 210),
    )
    return handle


def _build_text_layer() -> Image.Image:
    text_layer = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)
    draw.text(
        BADGE_TEXT_CENTER,
        "4j",
        font=_load_badge_font(BADGE_TEXT_SIZE),
        anchor="mm",
        fill=(250, 250, 250, 255),
    )
    draw.ellipse(BADGE_DOT_BOX, fill=(255, 190, 76, 255))
    return text_layer


def build_master_icon() -> Image.Image:
    icon = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (0, 0, 0, 0))
    icon.alpha_composite(_build_plate_shadow())
    icon.alpha_composite(_build_plate())
    icon.alpha_composite(_build_group_shadow())
    icon.alpha_composite(_build_handle())
    icon.alpha_composite(_build_badge())
    icon.alpha_composite(_build_text_layer())
    return icon


def main() -> None:
    master_icon = build_master_icon()
    master_icon.save(MASTER_ICON)
    master_icon.save(RUNTIME_ICON)
    master_icon.save(MACOS_ICON)
    master_icon.save(WINDOWS_ICON, sizes=ICO_SIZES)
    print(f"rebuilt {MASTER_ICON}")
    print(f"rebuilt {RUNTIME_ICON}")
    print(f"rebuilt {MACOS_ICON}")
    print(f"rebuilt {WINDOWS_ICON}")


if __name__ == "__main__":
    main()

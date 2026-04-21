"""Application icon helpers."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtGui import QIcon, QPixmap

from src.utils.paths import get_resource_path


APP_ICON_RESOURCE = "src/ui/assets/app_icon.png"


def resolve_app_icon_path() -> Path | None:
    """Return the runtime icon path when the bundled asset exists."""
    icon_path = Path(get_resource_path(APP_ICON_RESOURCE))
    if icon_path.exists():
        return icon_path
    return None


def load_app_icon() -> QIcon:
    """Load the shared application icon."""
    icon_path = resolve_app_icon_path()
    if icon_path is None:
        return QIcon()
    return QIcon(str(icon_path))


def load_app_icon_pixmap(size: int) -> QPixmap:
    """Render the shared application icon at a square size."""
    icon = load_app_icon()
    if icon.isNull():
        return QPixmap()
    return icon.pixmap(size, size)

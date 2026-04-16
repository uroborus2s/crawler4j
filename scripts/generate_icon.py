"""Generate the workspace app icon asset."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QLinearGradient, QPainter, QPainterPath, QPen


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
ICON_PATH = WORKSPACE_ROOT / "packages" / "crawler4j" / "src" / "ui" / "assets" / "icon.jpg"


def generate_icon(path: Path, size: int = 512) -> None:
    """Generate a modern application icon."""
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#1e1e2e"))
    gradient.setColorAt(1.0, QColor("#11111b"))

    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)

    rect = QRectF(0, 0, size, size)
    radius = size * 0.22
    painter.drawRoundedRect(rect, radius, radius)

    border_pen = QPen(QColor("#cba6f7"), size * 0.02)
    painter.setPen(border_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(
        rect.adjusted(size * 0.02, size * 0.02, -size * 0.02, -size * 0.02),
        radius,
        radius,
    )

    painter.setPen(
        QPen(
            QColor("#89b4fa"),
            size * 0.04,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap,
            Qt.PenJoinStyle.RoundJoin,
        )
    )
    painter.setBrush(Qt.BrushStyle.NoBrush)

    center_x = size / 2
    center_y = size / 2
    offset = size * 0.25

    painter_path = QPainterPath()
    painter_path.moveTo(center_x - offset, center_y - offset)
    painter_path.lineTo(center_x, center_y)
    painter_path.moveTo(center_x + offset, center_y - offset)
    painter_path.lineTo(center_x, center_y)
    painter_path.moveTo(center_x - offset, center_y + offset)
    painter_path.lineTo(center_x, center_y)
    painter_path.moveTo(center_x + offset, center_y + offset)
    painter_path.lineTo(center_x, center_y)
    painter_path.moveTo(center_x - offset * 1.2, center_y)
    painter_path.lineTo(center_x + offset * 1.2, center_y)

    painter.drawPath(painter_path)

    painter.setBrush(QColor("#f38ba8"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QPointF(center_x, center_y), size * 0.08, size * 0.08)

    node_color = QColor("#a6e3a1")
    painter.setBrush(node_color)
    node_radius = size * 0.04
    nodes = [
        (center_x - offset, center_y - offset),
        (center_x + offset, center_y - offset),
        (center_x - offset, center_y + offset),
        (center_x + offset, center_y + offset),
        (center_x - offset * 1.2, center_y),
        (center_x + offset * 1.2, center_y),
    ]

    for x_pos, y_pos in nodes:
        painter.drawEllipse(QPointF(x_pos, y_pos), node_radius, node_radius)

    painter.end()

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(path))
    print(f"Icon saved to {path}")


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    generate_icon(ICON_PATH)
    app.quit()

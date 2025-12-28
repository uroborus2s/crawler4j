
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)


def generate_icon(path: str, size: int = 512):
    """Generate a modern application icon."""
    # Create image
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # 1. Background (Rounded Rect with Gradient)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#1e1e2e"))  # Catppuccin Base
    gradient.setColorAt(1.0, QColor("#11111b"))  # Catppuccin Crust
    
    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    
    rect = QRectF(0, 0, size, size)
    radius = size * 0.22  # Mac-style rounded corners
    painter.drawRoundedRect(rect, radius, radius)
    
    # 2. Accent Border
    border_pen = QPen(QColor("#cba6f7"), size * 0.02)  # Mauve border
    painter.setPen(border_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(rect.adjusted(size*0.02, size*0.02, -size*0.02, -size*0.02), radius, radius)
    
    # 3. Spider/Network Graphic
    # Draw a stylized network node or spider abstract
    painter.setPen(QPen(QColor("#89b4fa"), size * 0.04, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    
    center_x = size / 2
    center_y = size / 2
    offset = size * 0.25
    
    # Legs
    painter_path = QPainterPath()
    # Top Left
    painter_path.moveTo(center_x - offset, center_y - offset)
    painter_path.lineTo(center_x, center_y)
    # Top Right
    painter_path.moveTo(center_x + offset, center_y - offset)
    painter_path.lineTo(center_x, center_y)
    # Bottom Left
    painter_path.moveTo(center_x - offset, center_y + offset)
    painter_path.lineTo(center_x, center_y)
    # Bottom Right
    painter_path.moveTo(center_x + offset, center_y + offset)
    painter_path.lineTo(center_x, center_y)
    
    # Horizontal
    painter_path.moveTo(center_x - offset * 1.2, center_y)
    painter_path.lineTo(center_x + offset * 1.2, center_y)
    
    painter.drawPath(painter_path)
    
    # Center Node
    painter.setBrush(QColor("#f38ba8")) # Red-ish center
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QPointF(center_x, center_y), size * 0.08, size * 0.08)
    
    # End Nodes
    node_color = QColor("#a6e3a1") # Green nodes
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
    
    for x, y in nodes:
        painter.drawEllipse(QPointF(x, y), node_radius, node_radius)

    painter.end()
    
    # Save
    image.save(path)
    print(f"Icon saved to {path}")

if __name__ == "__main__":
    import os
    import sys
    
    # Ensure directory exists
    os.makedirs("src/assets", exist_ok=True)
    
    # Application instance needed for QImage/QPainter sometimes (though mostly for fonts/pixmaps)
    # But QImage with QPainter usually works without QApplication instance for headless, 
    # except font rendering might need it. We are drawing shapes only.
    # However, creating QGuiApplication is safer.
    from PyQt6.QtGui import QGuiApplication
    app = QGuiApplication(sys.argv)
    
    generate_icon("src/assets/icon.png")

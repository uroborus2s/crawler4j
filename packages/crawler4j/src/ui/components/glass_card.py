from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QFrame, QGraphicsDropShadowEffect

from src.ui.theme.styles import StyleSheets


class GlassCard(QFrame):
    """A container with glassmorphism style."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("class", "GlassCard") # For QSS targeting (not standard Qt selector but we used Class.GlassCard logic simulation in QSS usually need objectName or manual setStyleSheet)
        # Actually QSS selector 'QFrame.GlassCard' works if the *class name* is standard but better to set objectName or attribute.
        # But here we are applying stylesheet directly or relying on global.
        # Let's use direct stylesheet application for component to ensure it works easily.
        self.setStyleSheet(StyleSheets.GLASS_CARD)
        
        # Add shadow for depth
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

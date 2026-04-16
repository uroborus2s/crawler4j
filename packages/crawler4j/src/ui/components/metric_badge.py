from PyQt6.QtWidgets import QHBoxLayout, QLabel

from src.ui.theme.palette import Palette
from src.ui.widgets.glass_card import GlassCard


class MetricBadge(GlassCard):
    """A small glass card displaying a label and a value/status."""
    
    def __init__(self, label_text: str, value_text: str, status_color: str = Palette.ACCENT_PRIMARY, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        
        # Icon/Color Indicator
        indicator = QLabel()
        indicator.setFixedSize(12, 12)
        indicator.setStyleSheet(f"background-color: {status_color}; border-radius: 6px;")
        layout.addWidget(indicator)
        
        layout.addSpacing(10)
        
        # Label
        lbl_title = QLabel(label_text)
        lbl_title.setStyleSheet(f"color: {Palette.TEXT_SECONDARY}; font-size: 14px;")
        layout.addWidget(lbl_title)
        
        layout.addStretch()
        
        # Value
        self.lbl_value = QLabel(value_text)
        self.lbl_value.setStyleSheet(f"color: {Palette.TEXT_PRIMARY}; font-size: 24px; font-weight: bold;")
        layout.addWidget(self.lbl_value)

    def set_value(self, value: str):
        self.lbl_value.setText(value)

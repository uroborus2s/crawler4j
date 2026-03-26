from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QPushButton, QSizePolicy, QSpacerItem, QVBoxLayout, QWidget

from src.ui.theme.styles import StyleSheets


class Sidebar(QWidget):
    """Modern Sidebar navigation."""
    
    # Signals
    page_changed = pyqtSignal(str) # Emits page name (e.g., "dashboard", "automation")
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setStyleSheet(StyleSheets.SIDEBAR)
        self.setFixedWidth(240)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 20, 10, 20)
        layout.setSpacing(8)
        
        # --- Logo Area ---
        # (Placeholder for now)
        logo_btn = QPushButton("✨ Crawler4j")
        logo_btn.setStyleSheet("font-size: 18px; font-weight: bold; color: white; border: none; text-align: left; padding-left: 15px;")
        layout.addWidget(logo_btn)
        
        layout.addSpacing(20)
        
        # --- Navigation Buttons ---
        self.btn_dashboard = self._create_nav_btn("仪表板", "dashboard")
        self.btn_automation = self._create_nav_btn("自动化编排", "automation")
        self.btn_environments = self._create_nav_btn("环境资源", "environments")
        self.btn_plugins = self._create_nav_btn("插件中心", "plugins")
        
        layout.addWidget(self.btn_dashboard)
        layout.addWidget(self.btn_automation)
        layout.addWidget(self.btn_environments)
        layout.addWidget(self.btn_plugins)
        
        # Spacer
        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
        # --- Bottom Actions ---
        self.btn_settings = self._create_nav_btn("系统设置", "settings")
        layout.addWidget(self.btn_settings)
        
    def _create_nav_btn(self, text: str, page_id: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setAutoExclusive(True)
        # We can add icons later
        btn.clicked.connect(lambda: self.page_changed.emit(page_id))
        return btn

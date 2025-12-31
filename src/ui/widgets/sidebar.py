"""Sidebar navigation widget.

Provides left-side navigation for the main window.
"""

from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QLabel,
    QSpacerItem,
    QSizePolicy,
)


class Sidebar(QWidget):
    """Left sidebar navigation widget.

    Signals:
        page_changed: Emitted when navigation item is clicked, with page index.
    """

    page_changed = pyqtSignal(int)

    # Navigation items: (icon, label, index)
    NAV_ITEMS = [
        ("🖥️", "控制台", 0),
        ("✈️", "携程账号", 1),
        ("👷", "劳保账号", 2),
        ("🌐", "环境管理", 3),
        ("⚙️", "设置", 4),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(180)

        self._buttons: list[QPushButton] = []
        self._current_index = 0

        self._setup_ui()

    def _setup_ui(self):
        """Setup the sidebar UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(4)

        # App title
        title = QLabel("🤖 Crawler4j")
        title.setStyleSheet("""
            font-size: 18px;
            font-weight: bold;
            color: #89b4fa;
            padding: 8px 4px 20px 4px;
        """)
        layout.addWidget(title)

        # Navigation buttons
        for icon, label, index in self.NAV_ITEMS:
            btn = QPushButton(f"{icon}  {label}")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=index: self._on_nav_clicked(i))
            self._buttons.append(btn)
            layout.addWidget(btn)

        # Set first button as active
        if self._buttons:
            self._buttons[0].setChecked(True)

        # Spacer
        layout.addSpacerItem(
            QSpacerItem(
                20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
            )
        )

        # Version label
        version = QLabel("v0.1.0")
        version.setStyleSheet("color: #6c7086; font-size: 11px;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

    def _on_nav_clicked(self, index: int):
        """Handle navigation button click."""
        if index == self._current_index:
            return

        # Update button states
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)

        self._current_index = index
        self.page_changed.emit(index)

    def set_active(self, index: int):
        """Set active navigation item programmatically.

        Args:
            index: Page index to activate.
        """
        if 0 <= index < len(self._buttons):
            self._on_nav_clicked(index)

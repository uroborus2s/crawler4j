"""Main window module.

Provides the main application window with sidebar navigation and content area.
"""

import os

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from src.ui.widgets.sidebar import Sidebar
from src.ui.widgets.status_bar import StatusBarWidget


class MainWindow(QMainWindow):
    """Main application window.

    Layout:
    ┌──────────┬───────────────────────────────────────┐
    │          │                                       │
    │  Sidebar │   Content Area (Stacked Widget)      │
    │          │                                       │
    ├──────────┴───────────────────────────────────────┤
    │  Status Bar                                      │
    └──────────────────────────────────────────────────┘
    """

    def __init__(self):
        super().__init__()
        from src.__version__ import VERSION

        self.setWindowTitle(f"🤖 自动化爬虫 GUI (v{VERSION})")
        self.setMinimumSize(1200, 800)

        # Apply dark theme
        self._load_stylesheet()

        # Setup UI
        self._setup_ui()

        # Connect signals
        self._connect_signals()

    def _load_stylesheet(self):
        """Load the dark theme stylesheet."""
        from src.utils.paths import get_resource_path

        style_path = get_resource_path("src/ui/styles/dark_theme.qss")
        if os.path.exists(style_path):
            with open(style_path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())

    def _setup_ui(self):
        """Setup the main UI layout."""
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)

        # Main layout
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
        self.sidebar = Sidebar()
        main_layout.addWidget(self.sidebar)

        # Content area
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack, 1)

        # Status bar
        self.status_widget = StatusBarWidget()
        self.setStatusBar(self.status_widget)

        # We will add real pages in main.py

    def _connect_signals(self):
        """Connect sidebar navigation signals."""
        self.sidebar.page_changed.connect(self.content_stack.setCurrentIndex)

    def add_page(self, widget: QWidget):
        """Add a page to the content stack.

        Args:
            widget: Page widget to add.
        """
        self.content_stack.addWidget(widget)

    def set_page(self, index: int, widget: QWidget):
        """Replace a page in the content stack.

        Args:
            index: Page index (0-4).
            widget: New page widget.
        """
        old_widget = self.content_stack.widget(index)
        self.content_stack.removeWidget(old_widget)
        self.content_stack.insertWidget(index, widget)
        old_widget.deleteLater()

    def update_status(
        self,
        is_running: bool = False,
        running_count: int = 0,
        max_concurrent: int = 10,
        completed: int = 0,
        failed: int = 0,
    ):
        """Update status bar information.

        Args:
            is_running: Whether scheduler is running.
            running_count: Number of running environments.
            max_concurrent: Maximum concurrent environments.
            completed: Total completed tasks.
            failed: Total failed tasks.
        """
        self.status_widget.update_status(
            is_running=is_running,
            running_count=running_count,
            max_concurrent=max_concurrent,
            completed=completed,
            failed=failed,
        )

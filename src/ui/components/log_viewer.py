"""Log viewer widget.

Displays real-time logs with filtering and auto-scroll.
"""

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QComboBox,
    QPushButton,
    QLabel,
)
from PyQt6.QtGui import QFont

from src.utils.logger import LogEntry, LogLevel


class LogViewer(QWidget):
    """Real-time log viewer with filtering.

    Features:
    - Auto-scroll to latest logs
    - Filter by log level
    - Color-coded log levels
    - Clear logs button
    """

    # Color map for log levels
    LEVEL_COLORS = {
        LogLevel.INFO: "#cdd6f4",  # Default text
        LogLevel.WARNING: "#f9e2af",  # Yellow
        LogLevel.ERROR: "#f38ba8",  # Red
    }

    def __init__(self, parent=None):
        super().__init__(parent)

        self._auto_scroll = True
        self._level_filter: LogLevel | None = None

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Setup the log viewer UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        toolbar.addWidget(QLabel("日志级别:"))

        self.level_combo = QComboBox()
        self.level_combo.addItem("全部", None)
        self.level_combo.addItem("INFO", LogLevel.INFO)
        self.level_combo.addItem("WARNING", LogLevel.WARNING)
        self.level_combo.addItem("ERROR", LogLevel.ERROR)
        self.level_combo.setMaximumWidth(120)
        toolbar.addWidget(self.level_combo)

        toolbar.addStretch()

        self.auto_scroll_btn = QPushButton("⬇ 自动滚动")
        self.auto_scroll_btn.setCheckable(True)
        self.auto_scroll_btn.setChecked(True)
        self.auto_scroll_btn.setMaximumWidth(120)
        toolbar.addWidget(self.auto_scroll_btn)

        self.clear_btn = QPushButton("🗑 清空")
        self.clear_btn.setMaximumWidth(80)
        toolbar.addWidget(self.clear_btn)

        layout.addLayout(toolbar)

        # Log text area
        self.log_text = QPlainTextEdit()
        self.log_text.setObjectName("logViewer")
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(1000)  # Limit log lines

        # Set monospace font
        font = QFont("JetBrains Mono", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.log_text.setFont(font)

        layout.addWidget(self.log_text)

    def _connect_signals(self):
        """Connect internal signals."""
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)
        self.auto_scroll_btn.toggled.connect(self._on_auto_scroll_toggled)
        self.clear_btn.clicked.connect(self.clear)

    def _on_level_changed(self, index: int):
        """Handle level filter change."""
        self._level_filter = self.level_combo.itemData(index)

    def _on_auto_scroll_toggled(self, checked: bool):
        """Handle auto-scroll toggle."""
        self._auto_scroll = checked

    @pyqtSlot(object)
    def add_log(self, entry: LogEntry):
        """Add a log entry to the viewer.

        Args:
            entry: LogEntry object to display.
        """
        # Check filter
        if self._level_filter and entry.level != self._level_filter:
            return

        # Format and append
        color = self.LEVEL_COLORS.get(entry.level, "#cdd6f4")
        html = f'<span style="color: {color}">{str(entry)}</span>'

        self.log_text.appendHtml(html)

        # Auto-scroll
        if self._auto_scroll:
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def add_log_text(self, text: str, level: LogLevel = LogLevel.INFO):
        """Add a simple text log.

        Args:
            text: Log message text.
            level: Log level for coloring.
        """
        color = self.LEVEL_COLORS.get(level, "#cdd6f4")
        html = f'<span style="color: {color}">{text}</span>'

        self.log_text.appendHtml(html)

        if self._auto_scroll:
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def clear(self):
        """Clear all logs."""
        self.log_text.clear()

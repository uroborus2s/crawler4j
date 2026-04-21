"""实时日志控制台组件。

支持显示统一日志服务的实时日志，并按 Task ID 过滤。
"""

from html import escape

from PyQt6.QtCore import QTimer, pyqtSlot
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from src.core.foundation.logging import LogEntry, logger


class LogConsoleWidget(QWidget):
    """日志控制台。"""

    _flush_interval_ms = 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_task_id: str | None = None
        self._pending_lines: list[tuple[str, str, int]] = []
        self._setup_ui()
        self._setup_flush_timer()
        logger.signals.log_added.connect(self._on_log_added)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                font-family: 'Menlo', 'Consolas', 'Monaco', monospace;
                font-size: 12px;
            }
        """)
        self.text_edit.document().setMaximumBlockCount(2000)
        layout.addWidget(self.text_edit)

    def _setup_flush_timer(self) -> None:
        self._flush_timer = QTimer(self)
        self._flush_timer.setSingleShot(True)
        self._flush_timer.timeout.connect(self._flush_pending_lines)

    def set_filter(self, task_id: str | None):
        """设置过滤 ID。"""
        self._filter_task_id = task_id
        self.clear()

        if task_id:
            self.append_log(f"--- Listening for logs from Task: {task_id} ---")

        entries = list(reversed(logger.get_entries(limit=1000)))
        for entry in entries:
            self._append_entry(entry)
        self._flush_pending_lines()

    def clear(self):
        self._pending_lines.clear()
        self._flush_timer.stop()
        self.text_edit.clear()

    def append_log(self, text: str, color: str = "#cdd6f4"):
        """追加日志文本。"""
        if self._pending_lines:
            last_text, last_color, last_count = self._pending_lines[-1]
            if last_text == text and last_color == color:
                self._pending_lines[-1] = (last_text, last_color, last_count + 1)
            else:
                self._pending_lines.append((text, color, 1))
        else:
            self._pending_lines.append((text, color, 1))

        if not self._flush_timer.isActive():
            self._flush_timer.start(self._flush_interval_ms)

    def _flush_pending_lines(self) -> None:
        if not self._pending_lines:
            return

        scrollbar = self.text_edit.verticalScrollBar()
        stick_to_bottom = scrollbar.value() >= max(scrollbar.maximum() - 4, 0)

        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        for text, color, repeat_count in self._pending_lines:
            rendered = text if repeat_count == 1 else f"{text} (x{repeat_count})"
            cursor.insertHtml(f'<span style="color:{color}">{escape(rendered)}</span><br/>')

        self.text_edit.setTextCursor(cursor)
        if stick_to_bottom:
            scrollbar.setValue(scrollbar.maximum())
        self._pending_lines.clear()

    def _append_entry(self, entry: LogEntry):
        """Internal append entry."""
        if self._filter_task_id and entry.task_id != self._filter_task_id:
            return

        color = "#cdd6f4"
        if entry.level == "WARNING":
            color = "#f9e2af"
        elif entry.level == "ERROR":
            color = "#f38ba8"
        elif entry.level == "DEBUG":
            color = "#6c7086"
            
        time_str = entry.timestamp.strftime("%H:%M:%S")
        self.append_log(f"[{time_str}] {entry.message}", color)

    @pyqtSlot(object)
    def _on_log_added(self, entry: LogEntry):
        """Handle unified log stream updates."""
        self._append_entry(entry)

"""实时日志控制台组件。

支持显示实时日志，并按 Task ID 过滤。
"""

from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QTextEdit, QVBoxLayout, QWidget

from src.core.foundation.event_bus import Event, EventType, get_event_bus
from src.core.foundation.logging import LogEntry, logger


class LogConsoleWidget(QWidget):
    """日志控制台。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter_task_id: str | None = None
        self._setup_ui()
        
        # Subscribe to events
        get_event_bus().subscribe(EventType.TASK_LOG, self._on_task_log)

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

    def set_filter(self, task_id: str | None):
        """设置过滤 ID。"""
        self._filter_task_id = task_id
        self.clear()
        
        # TODO: Load history logs from memory or storage?
        # For now, we only show realtime logs after opening
        if task_id:
            self.append_log(f"--- Listening for logs from Task: {task_id} ---")
            
            # Load recent memory logs
            entries = logger.get_entries(limit=1000)
            for entry in entries:
                if entry.task_id == task_id:
                     self._append_entry(entry)

    def clear(self):
        self.text_edit.clear()

    def append_log(self, text: str, color: str = "#cdd6f4"):
        """追加日志文本。"""
        self.text_edit.append(f'<span style="color:{color}">{text}</span>')

    def _append_entry(self, entry: LogEntry):
        """Internal append entry."""
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
    def _on_task_log(self, event: Event):
        """Handle log event."""
        data = event.data
        task_id = event.task_run_id
        
        # Filter
        if self._filter_task_id and task_id != self._filter_task_id:
            return
            
        # Parse data back to display (or use raw data)
        # We construct a simple display here
        level = data.get("level", "INFO")
        message = data.get("message", "")
        created_at = data.get("created_at", "")
        
        color = "#cdd6f4"
        if level == "WARNING":
            color = "#f9e2af"
        elif level == "ERROR":
            color = "#f38ba8"
        elif level == "DEBUG":
            color = "#6c7086"
            
        # Check if created_at needs parsing or just use current time?
        # data['created_at'] is isoformat string
        import dateutil.parser
        try:
             dt = dateutil.parser.isoparse(created_at)
             time_str = dt.strftime("%H:%M:%S")
        except Exception:
             time_str = "??"

        self.append_log(f"[{time_str}] {message}", color)

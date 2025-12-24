"""Status bar widget.

Displays application status information at the bottom of the main window.
"""

from PyQt6.QtWidgets import QStatusBar, QLabel, QHBoxLayout, QWidget


class StatusBarWidget(QStatusBar):
    """Custom status bar with running status and statistics.
    
    Display format:
    [状态] | 并发: X/Y | 已完成: N | 失败: M
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the status bar UI."""
        # Container widget
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(16)
        
        # Status indicator
        self.status_label = QLabel("⚪ 已停止")
        self.status_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.status_label)
        
        # Separator
        sep1 = QLabel("|")
        sep1.setStyleSheet("color: #45475a;")
        layout.addWidget(sep1)
        
        # Concurrency
        self.concurrency_label = QLabel("并发: 0/10")
        layout.addWidget(self.concurrency_label)
        
        # Separator
        sep2 = QLabel("|")
        sep2.setStyleSheet("color: #45475a;")
        layout.addWidget(sep2)
        
        # Completed
        self.completed_label = QLabel("已完成: 0")
        self.completed_label.setStyleSheet("color: #a6e3a1;")
        layout.addWidget(self.completed_label)
        
        # Separator
        sep3 = QLabel("|")
        sep3.setStyleSheet("color: #45475a;")
        layout.addWidget(sep3)
        
        # Failed
        self.failed_label = QLabel("失败: 0")
        self.failed_label.setStyleSheet("color: #f38ba8;")
        layout.addWidget(self.failed_label)
        
        # Spacer
        layout.addStretch()
        
        self.addPermanentWidget(container)
    
    def update_status(
        self,
        is_running: bool = False,
        running_count: int = 0,
        max_concurrent: int = 10,
        completed: int = 0,
        failed: int = 0,
    ):
        """Update all status bar information.
        
        Args:
            is_running: Whether scheduler is running.
            running_count: Number of running environments.
            max_concurrent: Maximum concurrent environments.
            completed: Total completed tasks.
            failed: Total failed tasks.
        """
        # Status indicator
        if is_running:
            self.status_label.setText("🟢 运行中")
            self.status_label.setStyleSheet("font-weight: bold; color: #a6e3a1;")
        else:
            self.status_label.setText("⚪ 已停止")
            self.status_label.setStyleSheet("font-weight: bold; color: #6c7086;")
        
        # Concurrency
        self.concurrency_label.setText(f"并发: {running_count}/{max_concurrent}")
        
        # Completed
        self.completed_label.setText(f"已完成: {completed}")
        
        # Failed
        self.failed_label.setText(f"失败: {failed}")
    
    def set_running(self, is_running: bool):
        """Update only the running status indicator."""
        if is_running:
            self.status_label.setText("🟢 运行中")
            self.status_label.setStyleSheet("font-weight: bold; color: #a6e3a1;")
        else:
            self.status_label.setText("⚪ 已停止")
            self.status_label.setStyleSheet("font-weight: bold; color: #6c7086;")

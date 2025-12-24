"""Statistics dialog.

Displays task statistics for a Labor account using simple charts.
"""

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QFrame,
    QWidget,
)


class StatsDialog(QDialog):
    """Dialog displaying Labor account performance metrics.
    
    Shows counts for:
    - Completed
    - Discarded
    - Approved
    - Rejected
    """
    
    def __init__(self, account: dict, parent=None):
        """Initialize the dialog.
        
        Args:
            account: Labor account data dictionary.
            parent: Parent widget.
        """
        super().__init__(parent)
        
        self.account = account
        self.setWindowTitle(f"统计详情: {account.get('phone', 'Unknown')}")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(24)
        layout.setContentsMargins(32, 32, 32, 32)
        
        # Title
        title = QLabel("任务执行统计")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #89b4fa;")
        layout.addWidget(title)
        
        # Stats summary
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        
        completed = self.account.get("completed_count", 0)
        discarded = self.account.get("discarded_count", 0)
        approved = self.account.get("approved_count", 0)
        rejected = self.account.get("rejected_count", 0)
        total = completed + discarded
        
        stats_layout.addWidget(self._create_stat_card("总领题", str(total), "#cdd6f4"))
        stats_layout.addWidget(self._create_stat_card("已完成", str(completed), "#a6e3a1"))
        stats_layout.addWidget(self._create_stat_card("已废弃", str(discarded), "#f38ba8"))
        
        layout.addLayout(stats_layout)
        
        # Detail stats
        detail_group = QFrame()
        detail_group.setStyleSheet("background-color: #313244; border-radius: 12px; padding: 16px;")
        detail_layout = QVBoxLayout(detail_group)
        
        # Success rate
        success_rate = (approved / completed * 100) if completed > 0 else 0
        detail_layout.addWidget(self._create_progress_bar("通过率 (通过 / 完成)", success_rate, "#a6e3a1"))
        
        # Reject rate
        reject_rate = (rejected / completed * 100) if completed > 0 else 0
        detail_layout.addWidget(self._create_progress_bar("拒绝率 (拒绝 / 完成)", reject_rate, "#f38ba8"))
        
        # Completion rate
        completion_rate = (completed / total * 100) if total > 0 else 0
        detail_layout.addWidget(self._create_progress_bar("完成率 (完成 / 总领题)", completion_rate, "#89b4fa"))
        
        layout.addWidget(detail_group)
        
        # Close button
        buttons = QHBoxLayout()
        buttons.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self.accept)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)
    
    def _create_stat_card(self, title: str, value: str, color: str) -> QFrame:
        """Create a simple statistical card widget."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #313244;
                border-radius: 12px;
                padding: 12px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setSpacing(4)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        layout.addWidget(value_label)
        
        return card
    
    def _create_progress_bar(self, label_text: str, percentage: float, color: str) -> QWidget:
        """Create a label and progress bar widget."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 4)
        
        label_layout = QHBoxLayout()
        label_layout.addWidget(QLabel(label_text))
        label_layout.addStretch()
        label_layout.addWidget(QLabel(f"{percentage:.1f}%"))
        layout.addLayout(label_layout)
        
        bar_bg = QFrame()
        bar_bg.setFixedHeight(8)
        bar_bg.setStyleSheet("background-color: #1e1e2e; border-radius: 4px;")
        
        bar = QFrame(bar_bg)
        bar.setFixedHeight(8)
        bar.setStyleSheet(f"background-color: {color}; border-radius: 4px;")
        # Simple manual sizing for the bar
        # In a real widget we would handle resize events, but this is a dialog
        bar.setFixedWidth(int(percentage * 4.3)) # Approx width
        
        layout.addWidget(bar_bg)
        return container
    
    @classmethod
    def show_stats(cls, account: dict, parent=None):
        """Show stats dialog."""
        dialog = cls(account, parent)
        dialog.exec()

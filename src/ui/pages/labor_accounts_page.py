"""Labor accounts page.

Manages the Labor platform account pool.
"""

import pandas as pd
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.ui.dialogs.labor_account_dialog import LaborAccountDialog
from src.ui.widgets.confirm_dialog import ConfirmDialog
from src.ui.widgets.data_table import DataTable
from src.ui.widgets.toast import Toast
from src.utils.storage import LaborAccountRepository


class LaborAccountsPage(QWidget):
    """Labor accounts management page.

    Features:
    - Add/Edit/Delete accounts
    - Import from CSV
    - View task statistics
    """

    COLUMNS = [
        ("phone", "账号", 150),
        ("status", "状态", 80),
        ("locked_at", "锁定时间", 100),
        ("completed_count", "完成", 60),
        ("discarded_count", "废弃", 60),
        ("approved_count", "通过", 60),
        ("rejected_count", "拒绝", 60),
        ("updated_at", "最后更新", -1),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.repo = LaborAccountRepository()

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """Setup the page UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()

        title = QLabel("劳保账号管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        self.stats_label = QLabel("共 0 个账号")
        self.stats_label.setStyleSheet("color: #a6adc8;")
        header.addWidget(self.stats_label)

        layout.addLayout(header)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        add_btn = QPushButton("+ 添加账号")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._on_add)
        toolbar.addWidget(add_btn)

        import_btn = QPushButton("📥 导入CSV")
        import_btn.clicked.connect(self._on_import)
        toolbar.addWidget(import_btn)

        self.stats_btn = QPushButton("📊 查看统计")
        self.stats_btn.setEnabled(False)
        self.stats_btn.clicked.connect(self._on_view_stats)
        toolbar.addWidget(self.stats_btn)

        toolbar.addStretch()

        self.delete_btn = QPushButton("🗑 删除选中")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._on_batch_delete)
        self.delete_btn.setEnabled(False)
        toolbar.addWidget(self.delete_btn)

        layout.addLayout(toolbar)

        # Table
        self.table = DataTable(self.COLUMNS)
        self.table.row_double_clicked.connect(self._on_edit)
        self.table.selection_changed.connect(self._on_selection_changed)
        layout.addWidget(self.table, 1)

    def _load_data(self):
        """Load accounts from database."""
        accounts = self.repo.get_all(limit=1000)

        for acc in accounts:
            acc["status"] = self._format_status(acc.get("status", ""))

        self.table.set_data(accounts)

        total = len(accounts)
        total_completed = sum(a.get("completed_count", 0) for a in accounts)
        self.stats_label.setText(f"共 {total} 个账号，总完成: {total_completed}")

    def _format_status(self, status: str) -> str:
        """Format status for display."""
        status_map = {
            "active": "🟢 正常",
            "blacklisted": "🔴 置黑",
            "disabled": "⚪ 禁用",
        }
        return status_map.get(status, status)

    def _on_add(self):
        """Handle add button click."""
        result = LaborAccountDialog.add_account(self)
        if result:
            try:
                self.repo.create(
                    phone=result["phone"],
                    password=result["password"],
                )
                Toast.success(self, "账号添加成功")
                self._load_data()
            except Exception as e:
                Toast.error(self, f"添加失败: {e}")

    def _on_edit(self, row_data: dict):
        """Handle row double click to edit."""
        account_id = row_data.get("id")
        if not account_id:
            return
            
        account = self.repo.get_by_id(int(account_id))
        if not account:
            return

        result = LaborAccountDialog.edit_account(account, self)
        if result:
            Toast.success(self, "账号更新成功")
            self._load_data()

    def _on_import(self):
        """Handle CSV import."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择CSV文件", "", "CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            df = pd.read_csv(file_path)

            if "phone" not in df.columns or "password" not in df.columns:
                Toast.error(self, "CSV缺少必需的 'phone' 和 'password' 列")
                return

            imported = 0
            for _, row in df.iterrows():
                try:
                    self.repo.create(
                        phone=str(row["phone"]),
                        password=str(row["password"]),
                    )
                    imported += 1
                except Exception:
                    pass

            Toast.success(self, f"成功导入 {imported} 个账号")
            self._load_data()

        except Exception as e:
            Toast.error(self, f"导入失败: {e}")

    def _on_selection_changed(self, indices: list):
        """Handle table selection change."""
        has_selection = len(indices) > 0
        self.delete_btn.setEnabled(has_selection)
        self.stats_btn.setEnabled(len(indices) == 1)

    def _on_view_stats(self):
        """Handle view stats button click."""
        selected = self.table.get_selected_data()
        if len(selected) == 1:
            from src.ui.dialogs.stats_dialog import StatsDialog

            StatsDialog.show_stats(selected[0], self)

    def _on_batch_delete(self):
        """Handle batch delete."""
        selected = self.table.get_selected_data()
        if not selected:
            return

        if ConfirmDialog.confirm(
            self,
            "批量删除",
            f"确定要删除 {len(selected)} 个账号吗？此操作不可恢复。",
            danger=True,
        ):
            for acc in selected:
                self.repo.delete(acc["id"])
            Toast.success(self, f"已删除 {len(selected)} 个账号")
            self._load_data()

"""Ctrip accounts page.

Manages the Ctrip account pool.
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

from src.core.events import EventType, get_event_bus
from src.ui.dialogs.ctrip_account_dialog import CtripAccountDialog
from src.ui.widgets.confirm_dialog import ConfirmDialog
from src.ui.widgets.data_table import DataTable
from src.ui.widgets.toast import Toast
from src.utils.storage import CtripAccountRepository


class CtripAccountsPage(QWidget):
    """Ctrip accounts management page.

    Features:
    - Add/Edit/Delete accounts
    - Import from CSV
    - Batch operations (blacklist, enable, delete)
    - Search and pagination
    """

    # Table columns: (key, header, width)
    COLUMNS = [
        ("country_code", "区号", 50),
        ("phone_number", "手机号", 120),
        ("status", "状态", 80),
        ("account_type", "类型", 50),
        ("sms_verify_type", "接码", 50),
        ("consecutive_task_count", "连续任务", 70),
        ("task_interval_max", "间隔上限", 70),
        ("sms_platform_type", "接码平台", 80),
        ("updated_at", "最后更新", 140),
        ("_actions", "操作", 80),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.repo = CtripAccountRepository()

        self._setup_ui()
        self._connect_signals()
        self._load_data()

    def _setup_ui(self):
        """Setup the page UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Header
        header = QHBoxLayout()

        title = QLabel("携程账号管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)

        header.addStretch()

        # Stats
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

        toolbar.addStretch()

        # Batch operations
        self.blacklist_btn = QPushButton("🔴 批量置黑")
        self.blacklist_btn.clicked.connect(self._on_batch_blacklist)
        self.blacklist_btn.setEnabled(False)
        toolbar.addWidget(self.blacklist_btn)

        self.enable_btn = QPushButton("🟢 批量启用")
        self.enable_btn.clicked.connect(self._on_batch_enable)
        self.enable_btn.setEnabled(False)
        toolbar.addWidget(self.enable_btn)

        self.delete_btn = QPushButton("🗑 删除选中")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._on_batch_delete)
        self.delete_btn.setEnabled(False)
        toolbar.addWidget(self.delete_btn)

        layout.addLayout(toolbar)

        # Table
        self.table = DataTable(self.COLUMNS, action_callback=self._on_action_click)
        self.table.row_double_clicked.connect(self._on_edit)
        self.table.selection_changed.connect(self._on_selection_changed)
        layout.addWidget(self.table, 1)

    def _on_action_click(self, row_data: dict, action: str):
        """处理操作列按钮点击。"""
        if action == "edit":
            self._on_edit(row_data)

    def _connect_signals(self):
        """Connect to event bus signals for auto-refresh."""
        bus = get_event_bus()

        # 订阅环境创建事件（账号被绑定到环境时状态会变更）
        bus.environment_created.connect(self._on_account_status_changed)

        # 订阅通用事件以捕获账号相关变更
        bus.event_emitted.connect(self._on_event)

    def _on_event(self, event):
        """处理事件总线的通用事件。"""
        # 账号相关事件触发刷新
        if event.type in (
            EventType.CTRIP_ACCOUNT_ADDED,
            EventType.CTRIP_ACCOUNT_UPDATED,
            EventType.CTRIP_ACCOUNT_BLACKLISTED,
        ):
            self._load_data()

    def _on_account_status_changed(self, data: dict):
        """当账号状态变更时刷新数据。"""
        self._load_data()

    def _load_data(self):
        """Load accounts from database."""
        accounts = self.repo.get_all(limit=1000)

        # Format status for display
        for acc in accounts:
            acc["status"] = self._format_status(acc.get("status", ""))
            acc["account_type"] = self._format_type(acc.get("account_type", "manual"))
            acc["sms_verify_type"] = self._format_sms_type(
                acc.get("sms_verify_type", "manual")
            )

        self.table.set_data(accounts)

        # Update stats
        total = len(accounts)
        idle = sum(1 for a in accounts if "空闲" in a.get("status", ""))
        self.stats_label.setText(f"共 {total} 个，空闲: {idle}，其他: {total - idle}")

    def _format_status(self, status: str) -> str:
        """Format status for display."""
        status_map = {
            "idle": "⚪ 空闲",
            "active": "🟢 已绑定",
            "running": "🟡 运行中",
            "blacklisted": "🔴 置黑",
            "disabled": "⚫ 禁用",
        }
        return status_map.get(status, status)

    def _format_type(self, acc_type: str) -> str:
        """格式化账号类型。"""
        return "手动" if acc_type == "manual" else "API"

    def _format_sms_type(self, sms_type: str) -> str:
        """格式化接码模式。"""
        return "手动" if sms_type == "manual" else "自动"

    def _on_add(self):
        """Handle add button click."""
        result = CtripAccountDialog.add_account(self)
        if result:
            try:
                self.repo.create(
                    country_code=result.get("country_code", "+86"),
                    phone_number=result["phone_number"],
                    password=result.get("password"),
                    account_type=result.get("account_type", "manual"),
                    sms_verify_type=result.get("sms_verify_type", "manual"),
                    consecutive_task_count=result.get("consecutive_task_count", 15),
                    task_interval_max=result.get("task_interval_max", 2),
                    sms_platform_url=result.get("sms_platform_url"),
                    sms_platform_key=result.get("sms_platform_key"),
                    sms_platform_type=result.get("sms_platform_type"),
                )
                Toast.success(self, "账号添加成功")
                self._load_data()
            except Exception as e:
                Toast.error(self, f"添加失败: {e}")

    def _on_edit(self, row_data: dict):
        """Handle row double click to edit."""
        # Get full account data
        account_id = row_data.get("id")
        if account_id is None:
            return
        account = self.repo.get_by_id(int(account_id))
        if not account:
            return

        result = CtripAccountDialog.edit_account(account, self)
        if result:
            # Update in database
            try:
                self.repo.update(
                    int(account_id),
                    {
                        "country_code": result.get("country_code", "+86"),
                        "phone_number": result["phone_number"],
                        "password": result.get("password"),
                        "account_type": result.get("account_type", "manual"),
                        "sms_verify_type": result.get("sms_verify_type", "manual"),
                        "consecutive_task_count": result.get(
                            "consecutive_task_count", 5
                        ),
                        "task_interval_max": result.get("task_interval_max", 15),
                        "sms_platform_type": result.get("sms_platform_type"),
                        "sms_platform_url": result.get("sms_platform_url"),
                        "sms_platform_key": result.get("sms_platform_key"),
                    },
                )
                Toast.success(self, "账号更新成功")
                self._load_data()
            except Exception as e:
                Toast.error(self, f"更新失败: {e}")

    def _on_import(self):
        """Handle CSV import."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择CSV文件",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )

        if not file_path:
            return

        try:
            df = pd.read_csv(file_path)

            # Expected columns: phone, password (optional), sms_platform_type, sms_platform_url, sms_platform_key
            if "phone" not in df.columns and "phone_number" not in df.columns:
                Toast.error(self, "CSV缺少必需的 'phone' 或 'phone_number' 列")
                return

            imported = 0
            for _, row in df.iterrows():
                try:
                    self.repo.create(
                        country_code=str(row.get("country_code", "+86")),
                        phone_number=str(row.get("phone_number", row.get("phone", ""))),
                        password=row.get("password"),
                        sms_platform_url=row.get("sms_platform_url"),
                        sms_platform_key=row.get("sms_platform_key"),
                        sms_platform_type=row.get("sms_platform_type"),
                    )
                    imported += 1
                except Exception:
                    pass  # Skip duplicates

            Toast.success(self, f"成功导入 {imported} 个账号")
            self._load_data()

        except Exception as e:
            Toast.error(self, f"导入失败: {e}")

    def _on_selection_changed(self, indices: list):
        """Handle table selection change."""
        has_selection = len(indices) > 0
        self.blacklist_btn.setEnabled(has_selection)
        self.enable_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def _on_batch_blacklist(self):
        """Handle batch blacklist."""
        selected = self.table.get_selected_data()
        if not selected:
            return

        if ConfirmDialog.confirm(
            self,
            "批量置黑",
            f"确定要将 {len(selected)} 个账号置为黑名单吗？",
            danger=True,
        ):
            for acc in selected:
                self.repo.update_status(acc["id"], "blacklisted")
            Toast.success(self, f"已置黑 {len(selected)} 个账号")
            self._load_data()

    def _on_batch_enable(self):
        """Handle batch enable."""
        selected = self.table.get_selected_data()
        if not selected:
            return

        for acc in selected:
            self.repo.update_status(acc["id"], "active")
        Toast.success(self, f"已启用 {len(selected)} 个账号")
        self._load_data()

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

"""Environments page.

Manages browser environment bindings.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
)

from src.ui.widgets.data_table import DataTable
from src.ui.widgets.toast import Toast
from src.ui.widgets.confirm_dialog import ConfirmDialog
from src.utils.storage import EnvironmentRepository, CtripAccountRepository, LaborAccountRepository


class EnvironmentsPage(QWidget):
    """Environment management page.
    
    Displays all environment bindings (Ctrip + Labor + Browser profile).
    """
    
    COLUMNS = [
        ("display_id", "ID", 80),
        ("ctrip_phone", "携程账号", 150),
        ("labor_phone", "劳保账号", 150),
        ("browser_profile_id", "浏览器ID", 120),
        ("status", "状态", 100),
        ("last_run_at", "最后运行", -1),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.env_repo = EnvironmentRepository()
        self.ctrip_repo = CtripAccountRepository()
        self.labor_repo = LaborAccountRepository()
        
        self._setup_ui()
        self._load_data()
    
    def _setup_ui(self):
        """Setup the page UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        
        # Header
        header = QHBoxLayout()
        
        title = QLabel("环境管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        
        header.addStretch()
        
        self.stats_label = QLabel("共 0 个环境")
        self.stats_label.setStyleSheet("color: #a6adc8;")
        header.addWidget(self.stats_label)
        
        layout.addLayout(header)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        
        refresh_btn = QPushButton("🔄 刷新")
        refresh_btn.clicked.connect(self._load_data)
        toolbar.addWidget(refresh_btn)

        create_btn = QPushButton("+ 手动创建环境")
        create_btn.setObjectName("primary")
        create_btn.clicked.connect(self._on_create)
        toolbar.addWidget(create_btn)
        
        toolbar.addStretch()
        
        self.delete_btn = QPushButton("🗑 删除选中")
        self.delete_btn.setObjectName("danger")
        self.delete_btn.clicked.connect(self._on_delete)
        self.delete_btn.setEnabled(False)
        toolbar.addWidget(self.delete_btn)
        
        layout.addLayout(toolbar)
        
        # Table
        self.table = DataTable(self.COLUMNS)
        self.table.selection_changed.connect(self._on_selection_changed)
        layout.addWidget(self.table, 1)
    
    def _load_data(self):
        """Load environments from database."""
        environments = self.env_repo.get_all(limit=1000)
        
        # Enrich with account info
        display_data = []
        for env in environments:
            ctrip = self.ctrip_repo.get_by_id(env.get("ctrip_account_id"))
            labor = self.labor_repo.get_by_id(env.get("labor_account_id"))
            
            display_data.append({
                "id": env["id"],
                "display_id": f"ENV-{env['id']}",
                "ctrip_phone": self._mask_phone(ctrip.get("phone", "")) if ctrip else "-",
                "labor_phone": labor.get("phone", "-") if labor else "-",
                "browser_profile_id": env.get("browser_profile_id", ""),
                "status": self._format_status(env.get("status", "")),
                "last_run_at": env.get("last_run_at", "-"),
            })
        
        self.table.set_data(display_data)
        
        total = len(display_data)
        running = sum(1 for d in display_data if "运行" in d.get("status", ""))
        self.stats_label.setText(f"共 {total} 个，运行中: {running}，空闲: {total - running}")
    
    def _mask_phone(self, phone: str) -> str:
        """Mask phone number for display."""
        if len(phone) >= 7:
            return f"{phone[:3]}****{phone[-4:]}"
        return phone
    
    def _format_status(self, status: str) -> str:
        """Format status for display."""
        status_map = {
            "idle": "⚪ 空闲",
            "running": "🟢 运行",
            "error": "🔴 错误",
        }
        return status_map.get(status, status)
    
    def _on_selection_changed(self, indices: list):
        """Handle table selection change."""
        self.delete_btn.setEnabled(len(indices) > 0)

    def _on_create(self):
        """Handle manual create environment."""
        from src.ui.dialogs.create_env_dialog import CreateEnvDialog
        result = CreateEnvDialog.create_env(self)
        if result:
            try:
                self.env_repo.create(
                    ctrip_account_id=result["ctrip_account_id"],
                    labor_account_id=result["labor_account_id"],
                    browser_profile_id=result["browser_profile_id"],
                )
                Toast.success(self, "环境创建成功")
                self._load_data()
            except Exception as e:
                Toast.error(self, f"创建失败: {e}")
    
    def _on_delete(self):
        """Handle delete button click."""
        selected = self.table.get_selected_data()
        if not selected:
            return
        
        if ConfirmDialog.confirm(
            self,
            "删除环境",
            f"确定要删除 {len(selected)} 个环境吗？这将释放绑定的账号。",
            danger=True,
        ):
            for env in selected:
                self.env_repo.delete(env["id"])
            Toast.success(self, f"已删除 {len(selected)} 个环境")
            self._load_data()

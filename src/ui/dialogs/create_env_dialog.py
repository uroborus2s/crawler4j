"""Create environment dialog.

Dialog for manually binding a Ctrip account and a Labor account.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QComboBox,
    QPushButton,
    QLabel,
    QLineEdit,
)

from src.utils.storage import CtripAccountRepository, LaborAccountRepository


class CreateEnvDialog(QDialog):
    """Dialog for manually creating an environment binding.
    
    Allows selecting:
    - An available Ctrip account
    - An available Labor account
    - Browser profile ID
    """
    
    def __init__(self, parent=None):
        """Initialize the dialog."""
        super().__init__(parent)
        
        self.ctrip_repo = CtripAccountRepository()
        self.labor_repo = LaborAccountRepository()
        self.result_data: dict | None = None
        
        self.setWindowTitle("手动创建环境")
        self.setModal(True)
        self.setMinimumWidth(450)
        
        self._setup_ui()
        self._load_accounts()
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(24, 24, 24, 24)
        
        info = QLabel("请选择要绑定的账号和浏览器环境")
        info.setStyleSheet("color: #a6adc8;")
        layout.addWidget(info)
        
        # Form
        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        # Ctrip Account
        self.ctrip_combo = QComboBox()
        form.addRow("携程账号:", self.ctrip_combo)
        
        # Labor Account
        self.labor_combo = QComboBox()
        form.addRow("劳保账号:", self.labor_combo)
        
        # Browser Profile ID
        self.profile_input = QLineEdit()
        self.profile_input.setPlaceholderText("例如: profile_123")
        form.addRow("浏览器 ID:", self.profile_input)
        
        layout.addLayout(form)
        
        # Error label
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #f38ba8;")
        self.error_label.hide()
        layout.addWidget(self.error_label)
        
        # Buttons
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)
        
        create_btn = QPushButton("创建")
        create_btn.setObjectName("primary")
        create_btn.clicked.connect(self._on_create)
        buttons.addWidget(create_btn)
        
        layout.addLayout(buttons)
    
    def _load_accounts(self):
        """Load available accounts into combos."""
        # Load Ctrip accounts
        ctrip_accounts = self.ctrip_repo.get_all()
        for acc in ctrip_accounts:
            self.ctrip_combo.addItem(acc["phone"], acc["id"])
            
        # Load unbound Labor accounts
        labor_accounts = self.labor_repo.get_active_unbound()
        for acc in labor_accounts:
            self.labor_combo.addItem(acc["phone"], acc["id"])
            
        if self.ctrip_combo.count() == 0:
            self._show_error("没有可选的携程账号")
        elif self.labor_combo.count() == 0:
            self._show_error("没有空闲且启用的劳保账号")
    
    def _on_create(self):
        """Handle create button click."""
        ctrip_id = self.ctrip_combo.currentData()
        labor_id = self.labor_combo.currentData()
        profile_id = self.profile_input.text().strip()
        
        if not ctrip_id:
            self._show_error("请选择携程账号")
            return
        
        if not labor_id:
            self._show_error("请选择劳保账号")
            return
            
        if not profile_id:
            self._show_error("请输入浏览器 ID")
            return
            
        self.result_data = {
            "ctrip_account_id": ctrip_id,
            "labor_account_id": labor_id,
            "browser_profile_id": profile_id,
        }
        self.accept()
    
    def _show_error(self, message: str):
        """Show error message."""
        self.error_label.setText(message)
        self.error_label.show()
    
    @classmethod
    def create_env(cls, parent=None) -> dict | None:
        """Show dialog and return result."""
        dialog = cls(parent=parent)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.result_data
        return None

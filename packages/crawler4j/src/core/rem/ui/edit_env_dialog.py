"""环境编辑对话框。

提供环境配置的编辑功能：
- 代理 IP 修改
- 指纹刷新
"""

import asyncio

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from src.core.rem.models import Environment, ProxyMode


class EditEnvWorker(QThread):
    """编辑操作工作线程。"""
    
    finished = pyqtSignal(bool, str)  # (success, message)
    
    def __init__(
        self,
        env_id: int,
        action: str,
        proxy_value: str | None = None,
    ):
        super().__init__()
        self._env_id = env_id
        self._action = action
        self._proxy_value = proxy_value
    
    def run(self):
        from src.core.rem.manager import get_environment_manager
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            manager = get_environment_manager()
            
            if self._action == "update_proxy":
                success = loop.run_until_complete(
                    manager.update_env(self._env_id)
                )
                msg = "代理已更新" if success else "更新失败"
                self.finished.emit(success, msg)
                
            elif self._action == "refresh_proxy":
                success = loop.run_until_complete(
                    manager.update_env(self._env_id)
                )
                msg = "IP 已刷新" if success else "刷新失败（无可用 IP 池）"
                self.finished.emit(success, msg)
                
            elif self._action == "refresh_fingerprint":
                success = loop.run_until_complete(
                    manager.update_env(self._env_id)
                )
                msg = "指纹已刷新" if success else "刷新失败"
                self.finished.emit(success, msg)
            
            loop.close()
        except Exception as e:
            self.finished.emit(False, str(e))


class EditEnvDialog(QDialog):
    """编辑环境对话框。"""
    
    def __init__(self, env: Environment, parent=None):
        super().__init__(parent)
        self._env = env
        self._worker = None
        
        self.setWindowTitle(f"编辑环境 - {env.id}")
        self.setMinimumWidth(450)
        
        # 深色主题样式
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; }
            QLabel { color: #cdd6f4; background-color: transparent; }
            QLineEdit {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px 12px;
                color: #cdd6f4;
            }
            QLineEdit:focus { border-color: #89b4fa; }
            QLineEdit:disabled { 
                background-color: #1e1e2e; 
                color: #6c7086;
            }
            QPushButton {
                background-color: #45475a;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: #cdd6f4;
            }
            QPushButton:hover { background-color: #585b70; }
            QPushButton:disabled { background-color: #313244; color: #6c7086; }
        """)
        
        self._setup_ui()
        self._load_values()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 基本信息（只读）
        info_form = QFormLayout()
        
        self.id_label = QLabel()
        info_form.addRow("环境 ID:", self.id_label)
        
        self.provider_label = QLabel()
        info_form.addRow("Provider:", self.provider_label)
        
        self.status_label = QLabel()
        info_form.addRow("状态:", self.status_label)
        
        layout.addLayout(info_form)
        
        # 分隔线
        line = QLabel()
        line.setStyleSheet("background-color: #45475a; max-height: 1px;")
        line.setFixedHeight(1)
        layout.addWidget(line)
        
        # 代理配置
        proxy_section = QLabel("代理配置")
        proxy_section.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(proxy_section)
        
        proxy_form = QFormLayout()
        
        self.proxy_mode_label = QLabel()
        proxy_form.addRow("模式:", self.proxy_mode_label)
        
        self.proxy_current_label = QLabel()
        proxy_form.addRow("当前 IP:", self.proxy_current_label)
        
        # 代理输入 + 刷新按钮
        proxy_row = QHBoxLayout()
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("socks5://user:pass@host:port")
        proxy_row.addWidget(self.proxy_input)
        
        self.refresh_ip_btn = QPushButton("🔄 刷新")
        self.refresh_ip_btn.setFixedWidth(80)
        self.refresh_ip_btn.setToolTip("从 IP 池重新分配")
        self.refresh_ip_btn.clicked.connect(self._refresh_proxy)
        proxy_row.addWidget(self.refresh_ip_btn)
        
        proxy_form.addRow("新代理:", proxy_row)
        
        layout.addLayout(proxy_form)
        
        # 指纹配置
        fp_section = QLabel("指纹配置")
        fp_section.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(fp_section)
        
        fp_row = QHBoxLayout()
        fp_row.addWidget(QLabel("点击刷新重新随机化指纹"))
        fp_row.addStretch()
        
        self.refresh_fp_btn = QPushButton("🎲 刷新指纹")
        self.refresh_fp_btn.clicked.connect(self._refresh_fingerprint)
        fp_row.addWidget(self.refresh_fp_btn)
        
        layout.addLayout(fp_row)
        
        # 按钮区
        layout.addStretch()
        
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _load_values(self):
        """加载当前环境配置。"""
        self.id_label.setText(str(self._env.id))
        self.provider_label.setText(self._env.provider)
        self.status_label.setText(self._env.status.value)
        
        proxy = self._env.proxy_config
        if proxy:
            self.proxy_mode_label.setText(proxy.mode.value)
            self.proxy_current_label.setText(proxy.current_ip or "-")
            
            if proxy.mode == ProxyMode.STATIC:
                self.proxy_input.setText(proxy.static_value or "")
                self.refresh_ip_btn.setEnabled(False)
            elif proxy.mode == ProxyMode.POOL:
                self.proxy_input.setEnabled(False)
                self.proxy_input.setPlaceholderText("由 IP 池自动分配")
            else:
                self.proxy_input.setEnabled(False)
                self.refresh_ip_btn.setEnabled(False)
        else:
            self.proxy_mode_label.setText("无")
            self.proxy_current_label.setText("-")
            self.proxy_input.setEnabled(False)
            self.refresh_ip_btn.setEnabled(False)
    
    def _save(self):
        """保存代理配置。"""
        proxy = self._env.proxy_config
        
        if proxy and proxy.mode == ProxyMode.STATIC:
            new_value = self.proxy_input.text().strip()
            if new_value and new_value != proxy.static_value:
                self._run_action("update_proxy", proxy_value=new_value)
                return
        
        self.accept()
    
    def _refresh_proxy(self):
        """刷新代理 IP。"""
        self._run_action("refresh_proxy")
    
    def _refresh_fingerprint(self):
        """刷新指纹。"""
        self._run_action("refresh_fingerprint")
    
    def _run_action(self, action: str, proxy_value: str | None = None):
        """执行异步操作。"""
        self._set_buttons_enabled(False)
        
        self._worker = EditEnvWorker(
            self._env.id, 
            action,
            proxy_value=proxy_value,
        )
        self._worker.finished.connect(self._on_action_finished)
        self._worker.start()
    
    def _on_action_finished(self, success: bool, message: str):
        """操作完成回调。"""
        self._set_buttons_enabled(True)
        
        if success:
            QMessageBox.information(self, "成功", message)
            self.accept()
        else:
            QMessageBox.warning(self, "失败", message)
    
    def _set_buttons_enabled(self, enabled: bool):
        """设置按钮启用状态。"""
        self.refresh_ip_btn.setEnabled(enabled)
        self.refresh_fp_btn.setEnabled(enabled)

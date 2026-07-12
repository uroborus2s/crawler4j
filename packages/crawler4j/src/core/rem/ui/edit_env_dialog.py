"""环境编辑对话框。

提供环境配置的编辑功能：
- 代理 IP 修改
- 指纹刷新
"""

import asyncio

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from src.core.rem.models import Environment, ProxyMode
from src.ui.components.button import StyledButton
from src.ui.components.confirm_dialog import ConfirmDialog
from src.ui.components.dialog_window import configure_titled_dialog
from src.ui.components.line_edit import StyledLineEdit as QLineEdit
from src.ui.components.message_dialog import MessageDialog


class EditEnvWorker(QThread):
    """编辑操作工作线程。"""
    
    finished = pyqtSignal(bool, str)  # (success, message)
    
    def __init__(
        self,
        env_id: int,
        action: str,
        proxy_value: str | None = None,
        proxy_pool_id: str | None = None,
        proxy_entry_id: str | None = None,
    ):
        super().__init__()
        self._env_id = env_id
        self._action = action
        self._proxy_value = proxy_value
        self._proxy_pool_id = proxy_pool_id
        self._proxy_entry_id = proxy_entry_id

    def _build_update_request(self) -> tuple[dict[str, object], str, str]:
        if self._action == "update_proxy":
            if not self._proxy_value:
                raise ValueError("缺少代理地址，无法保存代理配置")
            return {"proxy_value": self._proxy_value}, "代理地址更新成功", "代理地址更新失败"

        if self._action == "refresh_proxy":
            if not self._proxy_pool_id:
                raise ValueError("当前环境未绑定 IP 池，无法刷新代理")
            return (
                {"proxy_pool_id": self._proxy_pool_id},
                "已从 IP 池随机分配并应用新代理",
                "随机更换代理失败（当前 IP 池可能没有其他可用 IP）",
            )

        if self._action == "update_proxy_entry":
            if not self._proxy_entry_id:
                raise ValueError("请选择要绑定的 IP")
            return {"proxy_entry_id": self._proxy_entry_id}, "所选 IP 已应用到环境", "应用所选 IP 失败"

        if self._action == "refresh_fingerprint":
            return (
                {"randomize_fingerprint": True},
                "环境指纹已刷新并完成检测",
                "环境指纹刷新或检测失败",
            )

        raise ValueError(f"不支持的操作: {self._action}")
    
    def run(self):
        from src.core.rem.manager import get_environment_manager
        
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            manager = get_environment_manager()
            kwargs, success_msg, failure_msg = self._build_update_request()
            success = loop.run_until_complete(manager.update_env(self._env_id, **kwargs))
            self.finished.emit(success, success_msg if success else failure_msg)
        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            loop.close()


class EditEnvDialog(QDialog):
    """编辑环境对话框。"""
    
    def __init__(self, env: Environment, parent=None):
        super().__init__(parent)
        self._env = env
        self._worker = None
        
        self.setWindowTitle(f"编辑环境 - {env.id}")
        configure_titled_dialog(self)
        self.setMinimumWidth(450)
        
        # 深色主题样式
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; }
            QLabel { color: #cdd6f4; background-color: transparent; }
            QLineEdit:disabled { 
                background-color: #1e1e2e; 
                color: #6c7086;
            }
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

        proxy_entry_row = QHBoxLayout()
        self.proxy_entry_combo = QComboBox()
        self.proxy_entry_combo.setEnabled(False)
        proxy_entry_row.addWidget(self.proxy_entry_combo)

        self.apply_proxy_btn = StyledButton(
            "应用所选 IP",
            variant="primary",
            min_height=40,
            min_width=120,
        )
        self.apply_proxy_btn.setEnabled(False)
        self.apply_proxy_btn.clicked.connect(self._apply_selected_proxy)
        proxy_entry_row.addWidget(self.apply_proxy_btn)
        proxy_form.addRow("可用 IP:", proxy_entry_row)
        
        # 手工代理只对静态代理模式显示。
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("socks5://user:pass@host:port")
        proxy_form.addRow("代理地址:", self.proxy_input)
        
        self.refresh_ip_btn = StyledButton(
            "随机更换 IP",
            variant="secondary",
            min_height=40,
            min_width=120,
        )
        self.refresh_ip_btn.setToolTip("忽略上方选择，从当前 IP 池随机分配并应用另一个可用 IP")
        self.refresh_ip_btn.clicked.connect(self._refresh_proxy)
        proxy_form.addRow("IP 池操作:", self.refresh_ip_btn)

        self._proxy_form = proxy_form
        
        layout.addLayout(proxy_form)
        
        # 指纹配置
        fp_section = QLabel("指纹配置")
        fp_section.setStyleSheet("font-weight: bold; margin-top: 8px;")
        layout.addWidget(fp_section)
        
        fp_row = QHBoxLayout()
        fp_row.addWidget(QLabel("点击刷新重新随机化指纹"))
        fp_row.addStretch()
        
        self.refresh_fp_btn = StyledButton("刷新指纹", variant="secondary", min_height=40)
        self.refresh_fp_btn.clicked.connect(self._refresh_fingerprint)
        fp_row.addWidget(self.refresh_fp_btn)
        
        layout.addLayout(fp_row)
        
        # 按钮区
        layout.addStretch()
        
        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.addStretch()

        cancel_btn = StyledButton(
            "取消",
            variant="secondary",
            min_height=40,
            min_width=92,
            horizontal_padding=20,
        )
        cancel_btn.setObjectName("editEnvCancelButton")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)

        save_btn = StyledButton(
            "保存",
            variant="success",
            min_height=40,
            min_width=92,
            horizontal_padding=20,
        )
        save_btn.setObjectName("editEnvSaveButton")
        save_btn.clicked.connect(self._save)
        button_row.addWidget(save_btn)
        layout.addLayout(button_row)
    
    def _load_values(self):
        """加载当前环境配置。"""
        self.id_label.setText(str(self._env.id))
        self.provider_label.setText(self._env.provider)
        self.status_label.setText(self._env.status.value)
        
        proxy = self._env.proxy_config
        is_static = bool(proxy and proxy.mode == ProxyMode.STATIC)
        has_pool = bool(proxy and proxy.mode == ProxyMode.POOL and proxy.pool_id)
        self._proxy_form.setRowVisible(self.proxy_input, is_static)
        self._proxy_form.setRowVisible(self.refresh_ip_btn, has_pool)
        if proxy:
            self.proxy_mode_label.setText(proxy.mode.value)
            self.proxy_current_label.setText(proxy.current_ip or "-")
            
            if proxy.mode == ProxyMode.STATIC:
                self.proxy_input.setText(proxy.static_value or "")
            elif proxy.mode == ProxyMode.POOL:
                self._load_pool_entries(proxy.pool_id, proxy.ip_entry_id)
            else:
                self._load_pool_entries(None, proxy.ip_entry_id)
        else:
            self.proxy_mode_label.setText("无")
            self.proxy_current_label.setText("-")
            self._load_pool_entries(None, None)

    def _load_pool_entries(self, pool_id: str | None, current_entry_id: str | None):
        """加载当前 IP 池条目。"""
        from src.core.rem.ip_pool import get_ip_pool_manager

        self.proxy_entry_combo.clear()
        manager = get_ip_pool_manager()
        if pool_id:
            pools = [pool] if (pool := manager.get_pool(str(pool_id))) is not None else []
        else:
            pools = manager.list_pools()
        for pool in pools:
            for entry in pool.entries:
                if not entry.is_available() or entry.is_expired():
                    continue
                self.proxy_entry_combo.addItem(f"{entry.address}:{entry.port} ({entry.protocol})", entry.id)
        index = self.proxy_entry_combo.findData(current_entry_id)
        if index >= 0:
            self.proxy_entry_combo.setCurrentIndex(index)
        has_entries = self.proxy_entry_combo.count() > 0
        self.proxy_entry_combo.setEnabled(has_entries)
        self.apply_proxy_btn.setEnabled(has_entries)

    def _apply_selected_proxy(self):
        """应用下拉框中明确选择的 IP。"""
        entry_id = str(self.proxy_entry_combo.currentData() or "")
        if not entry_id:
            MessageDialog.warning(self, "无法应用", "请先选择一个可用 IP")
            return
        proxy = self._env.proxy_config
        current_entry_id = str(proxy.ip_entry_id or "") if proxy else ""
        if entry_id == current_entry_id:
            MessageDialog.information(self, "无需更新", "当前环境已经使用所选 IP")
            return
        if not self._confirm_high_risk(
            "确认修改代理 IP",
            f"确定将环境代理切换为 {self.proxy_entry_combo.currentText()} 吗？\n"
            "修改代理可能影响当前登录状态和账号风控结果。",
            "确认修改",
        ):
            return
        self._run_action("update_proxy_entry", proxy_entry_id=entry_id)

    def _confirm_high_risk(self, title: str, message: str, confirm_text: str) -> bool:
        return ConfirmDialog.confirm(
            self,
            title,
            message,
            confirm_text=confirm_text,
            danger=True,
        )
    
    def _save(self):
        """保存代理配置。"""
        proxy = self._env.proxy_config
        
        if proxy and proxy.mode == ProxyMode.STATIC:
            new_value = self.proxy_input.text().strip()
            if new_value and new_value != proxy.static_value:
                if not self._confirm_high_risk(
                    "确认修改代理地址",
                    "确定将环境切换为输入的新代理地址吗？\n修改代理可能影响当前登录状态和账号风控结果。",
                    "确认修改",
                ):
                    return
                self._run_action("update_proxy", proxy_value=new_value)
                return

        if self.proxy_entry_combo.isEnabled():
            entry_id = str(self.proxy_entry_combo.currentData() or "")
            current_entry_id = str(proxy.ip_entry_id or "") if proxy else ""
            if entry_id and entry_id != current_entry_id:
                if not self._confirm_high_risk(
                    "确认修改代理 IP",
                    f"确定将环境代理切换为 {self.proxy_entry_combo.currentText()} 吗？\n"
                    "修改代理可能影响当前登录状态和账号风控结果。",
                    "确认修改",
                ):
                    return
                self._run_action("update_proxy_entry", proxy_entry_id=entry_id)
                return
        
        self.accept()
    
    def _refresh_proxy(self):
        """刷新代理 IP。"""
        proxy = self._env.proxy_config
        pool_id = proxy.pool_id if proxy else None
        if not self._confirm_high_risk(
            "确认随机更换代理 IP",
            "系统将从当前 IP 池随机分配并立即应用新代理。\n"
            "修改代理可能影响当前登录状态和账号风控结果。",
            "确认更换",
        ):
            return
        self._run_action("refresh_proxy", proxy_pool_id=pool_id)
    
    def _refresh_fingerprint(self):
        """刷新指纹。"""
        if not self._confirm_high_risk(
            "确认刷新环境指纹",
            "系统将随机化指纹、修正不合格参数并重新检测。\n"
            "刷新指纹可能影响当前登录状态和账号风控结果。",
            "确认刷新",
        ):
            return
        self._run_action("refresh_fingerprint")
    
    def _run_action(
        self,
        action: str,
        proxy_value: str | None = None,
        proxy_pool_id: str | None = None,
        proxy_entry_id: str | None = None,
    ):
        """执行异步操作。"""
        self._set_buttons_enabled(False)
        
        self._worker = EditEnvWorker(
            self._env.id, 
            action,
            proxy_value=proxy_value,
            proxy_pool_id=proxy_pool_id,
            proxy_entry_id=proxy_entry_id,
        )
        self._worker.finished.connect(self._on_action_finished)
        self._worker.start()
    
    def _on_action_finished(self, success: bool, message: str):
        """操作完成回调。"""
        self._set_buttons_enabled(True)
        
        if success:
            MessageDialog.information(self, "成功", message)
            self.accept()
        else:
            MessageDialog.warning(self, "失败", message)
    
    def _set_buttons_enabled(self, enabled: bool):
        """设置按钮启用状态。"""
        proxy = self._env.proxy_config
        has_pool = bool(proxy and proxy.mode == ProxyMode.POOL and proxy.pool_id)
        has_entries = self.proxy_entry_combo.count() > 0
        self.proxy_entry_combo.setEnabled(enabled and has_entries)
        self.apply_proxy_btn.setEnabled(enabled and has_entries)
        self.refresh_ip_btn.setEnabled(enabled and has_pool)
        self.refresh_fp_btn.setEnabled(enabled)

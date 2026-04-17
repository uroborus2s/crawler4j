"""IP 池管理对话框。

设计参考: docs/03-solution/reference-design/module-01-runtime-environment.md §5.5

提供 IP 池相关的对话框：
    - AddPoolDialog: 新建 IP 池对话框
    - AddIPDialog: 单个添加 IP 对话框
    - BatchImportDialog: 批量导入 IP 对话框
"""

import time
from typing import Any

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from src.core.rem.ip_pool import IPEntry, IPPool, IPStrategy
from src.ui.components.combo_box import StyledComboBox as QComboBox
from src.ui.components.spin_box import StyledSpinBox as QSpinBox


class AddPoolDialog(QDialog):
    """新建 IP 池对话框。"""
    
    STRATEGY_OPTIONS = [
        ("最少绑定数量", IPStrategy.LEAST_BOUND),
        ("最高安全度", IPStrategy.HIGHEST_SAFETY),
        ("最长有效期", IPStrategy.LONGEST_TTL),
        ("系统代理", IPStrategy.SYSTEM_PROXY),
        ("无代理", IPStrategy.NONE),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建 IP 池")
        self.setMinimumWidth(350)
        self._apply_dark_theme()
        self._setup_ui()
    
    def _apply_dark_theme(self) -> None:
        """应用深色主题样式。"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
            }
            QLabel {
                color: #cdd6f4;
                background-color: transparent;
            }
            QLineEdit, QSpinBox, QPlainTextEdit {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px 12px;
                color: #cdd6f4;
            }
            QLineEdit:focus, QSpinBox:focus, QPlainTextEdit:focus {
                border-color: #89b4fa;
            }
            QPushButton {
                background-color: #45475a;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: #cdd6f4;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
            QDialogButtonBox QPushButton[text="OK"] {
                background-color: #89b4fa;
                color: #1e1e2e;
            }
        """)
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        # 池名称
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("如: 默认池、高安全池")
        form.addRow("池名称:", self.name_input)
        
        # 分配策略
        self.strategy_combo = QComboBox()
        for label, _ in self.STRATEGY_OPTIONS:
            self.strategy_combo.addItem(label)
        form.addRow("分配策略:", self.strategy_combo)
        
        layout.addLayout(form)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_values(self) -> IPPool:
        """获取输入值并创建 IPPool 对象。"""
        name = self.name_input.text().strip() or "未命名池"
        strategy = self.STRATEGY_OPTIONS[self.strategy_combo.currentIndex()][1]
        
        return IPPool(
            name=name,
            strategy=strategy,
        )


class AddIPDialog(QDialog):
    """单个添加 IP 对话框。"""
    
    PROTOCOL_OPTIONS = ["http", "socks4", "socks5"]
    
    def __init__(self, pool_id: str, parent=None):
        super().__init__(parent)
        self._pool_id = pool_id
        self.setWindowTitle("添加 IP")
        self.setMinimumWidth(350)
        self._apply_dark_theme()
        self._setup_ui()
    
    def _apply_dark_theme(self) -> None:
        """应用深色主题样式。"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
            }
            QLabel {
                color: #cdd6f4;
                background-color: transparent;
            }
            QLineEdit, QSpinBox {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px 12px;
                color: #cdd6f4;
            }
            QLineEdit:focus, QSpinBox:focus {
                border-color: #89b4fa;
            }
            QPushButton {
                background-color: #45475a;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: #cdd6f4;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
            QDialogButtonBox QPushButton[text="OK"] {
                background-color: #89b4fa;
                color: #1e1e2e;
            }
        """)
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        # IP 地址
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("如: 192.168.1.1")
        form.addRow("IP 地址:", self.address_input)
        
        # 端口
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(8080)
        form.addRow("端口:", self.port_input)
        
        # 协议
        self.protocol_combo = QComboBox()
        self.protocol_combo.addItems(self.PROTOCOL_OPTIONS)
        form.addRow("协议:", self.protocol_combo)
        
        # 用户名
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("可选")
        form.addRow("用户名:", self.username_input)
        
        # 密码
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("可选")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("密码:", self.password_input)
        
        # 过期天数
        self.expire_days_input = QSpinBox()
        self.expire_days_input.setRange(1, 365)
        self.expire_days_input.setValue(30)
        self.expire_days_input.setSuffix(" 天")
        form.addRow("过期天数:", self.expire_days_input)
        
        layout.addLayout(form)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def get_values(self) -> IPEntry:
        """获取输入值并创建 IPEntry 对象。"""
        address = self.address_input.text().strip()
        port = self.port_input.value()
        protocol = self.PROTOCOL_OPTIONS[self.protocol_combo.currentIndex()]
        username = self.username_input.text().strip() or None
        password = self.password_input.text() or None
        expire_days = self.expire_days_input.value()
        
        expires_at = int(time.time()) + (expire_days * 24 * 60 * 60)
        
        return IPEntry(
            pool_id=self._pool_id,
            address=address,
            protocol=protocol,
            port=port,
            username=username,
            password=password,
            expires_at=expires_at,
        )


class BatchImportDialog(QDialog):
    """批量导入 IP 对话框。"""
    
    SUPPORTED_PROTOCOLS = {"http", "https", "socks4", "socks5"}
    
    def __init__(self, pool_id: str, parent=None):
        super().__init__(parent)
        self._pool_id = pool_id
        self.setWindowTitle("批量导入 IP")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)
        self._apply_dark_theme()
        self._setup_ui()
    
    def _apply_dark_theme(self) -> None:
        """应用深色主题样式。"""
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
            }
            QLabel {
                color: #cdd6f4;
                background-color: transparent;
            }
            QLineEdit, QSpinBox, QPlainTextEdit {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px 12px;
                color: #cdd6f4;
            }
            QLineEdit:focus, QSpinBox:focus, QPlainTextEdit:focus {
                border-color: #89b4fa;
            }
            QPushButton {
                background-color: #45475a;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                color: #cdd6f4;
            }
            QPushButton:hover {
                background-color: #585b70;
            }
            QDialogButtonBox QPushButton[text="导入"] {
                background-color: #89b4fa;
                color: #1e1e2e;
            }
        """)
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        # 顶部设置
        top_layout = QHBoxLayout()
        
        top_layout.addWidget(QLabel("过期天数:"))
        self.expire_days_input = QSpinBox()
        self.expire_days_input.setRange(1, 365)
        self.expire_days_input.setValue(30)
        self.expire_days_input.setSuffix(" 天")
        top_layout.addWidget(self.expire_days_input)
        
        top_layout.addStretch()
        layout.addLayout(top_layout)
        
        # 文本输入区
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText(
            "每行一个 IP，格式:\n"
            "protocol://ip:port 或 protocol://user:pass@ip:port\n\n"
            "支持协议: http, https, socks4, socks5\n\n"
            "示例:\n"
            "http://192.168.1.1:8080\n"
            "socks5://admin:123456@10.0.0.5:1080"
        )
        self.text_edit.textChanged.connect(self._update_count)
        layout.addWidget(self.text_edit)
        
        # 底部操作
        bottom_layout = QHBoxLayout()
        
        import_btn = QPushButton("从文件导入...")
        import_btn.clicked.connect(self._import_from_file)
        bottom_layout.addWidget(import_btn)
        
        self.count_label = QLabel("解析到: 0 条")
        bottom_layout.addWidget(self.count_label)
        
        bottom_layout.addStretch()
        layout.addLayout(bottom_layout)
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("导入")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _import_from_file(self) -> None:
        """从文件导入。"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择 IP 列表文件",
            "",
            "文本文件 (*.txt);;所有文件 (*.*)"
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.text_edit.setPlainText(content)
            except Exception as e:
                self.text_edit.setPlainText(f"读取文件失败: {e}")
    
    def _update_count(self) -> None:
        """更新解析计数。"""
        entries = self._parse_entries()
        self.count_label.setText(f"解析到: {len(entries)} 条")
    
    def _parse_entries(self) -> list[dict[str, Any]]:
        """解析文本内容。
        
        支持格式: protocol://user:pass@ip:port 或 protocol://ip:port
        """
        import re
        entries = []
        text = self.text_edit.toPlainText()
        
        # URL 格式正则: protocol://[user:pass@]ip:port
        pattern = re.compile(
            r'^(?P<protocol>https?|socks[45])://'
            r'(?:(?P<user>[^:@]+):(?P<pass>[^@]+)@)?'
            r'(?P<ip>[^:]+):(?P<port>\d+)$'
        )
        
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            match = pattern.match(line)
            if match:
                try:
                    entry = {
                        "protocol": match.group("protocol"),
                        "address": match.group("ip"),
                        "port": int(match.group("port")),
                    }
                    if match.group("user"):
                        entry["username"] = match.group("user")
                        entry["password"] = match.group("pass")
                    entries.append(entry)
                except (ValueError, IndexError):
                    continue
        
        return entries
    
    def get_values(self) -> list[IPEntry]:
        """获取解析后的 IPEntry 列表。"""
        expire_days = self.expire_days_input.value()
        expires_at = int(time.time()) + (expire_days * 24 * 60 * 60)
        
        entries = []
        for data in self._parse_entries():
            entry = IPEntry(
                pool_id=self._pool_id,
                address=data["address"],
                protocol=data["protocol"],
                port=data["port"],
                username=data.get("username"),
                password=data.get("password"),
                expires_at=expires_at,
            )
            entries.append(entry)
        
        return entries

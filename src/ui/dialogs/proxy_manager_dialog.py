"""Proxy IP Manager Dialog.

Allows adding, deleting IP addresses and viewing their usage stats.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from src.ui.widgets.toast import Toast
from src.utils.storage import ProxyIPRepository


class ProxyManagerDialog(QDialog):
    """Dialog for managing Proxy IP Pool."""

    COLUMNS = ["ID", "协议", "IP", "端口", "账号/密码", "使用数", "状态"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IP 池管理")
        self.setMinimumSize(800, 500)
        self.repo = ProxyIPRepository()

        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 1. Add Area
        add_group = QGroupBox("添加 IP")
        add_layout = QHBoxLayout(add_group)
        add_layout.setSpacing(10)

        self.proto_input = QComboBox()
        self.proto_input.addItems(["http", "socks5", "socks4"])
        self.proto_input.setFixedWidth(80)
        add_layout.addWidget(QLabel("协议:"))
        add_layout.addWidget(self.proto_input)

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("IP地址")
        add_layout.addWidget(QLabel("IP:"))
        add_layout.addWidget(self.ip_input)

        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("端口")
        self.port_input.setFixedWidth(60)
        add_layout.addWidget(QLabel("Port:"))
        add_layout.addWidget(self.port_input)

        self.user_input = QLineEdit()
        self.user_input.setPlaceholderText("账号(选填)")
        add_layout.addWidget(QLabel("User:"))
        add_layout.addWidget(self.user_input)

        self.pass_input = QLineEdit()
        self.pass_input.setPlaceholderText("密码(选填)")
        add_layout.addWidget(QLabel("Pass:"))
        add_layout.addWidget(self.pass_input)

        add_btn = QPushButton("➕ 添加")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self._on_add)
        add_layout.addWidget(add_btn)

        layout.addWidget(add_group)

        # 2. List Area
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.table)

        # 3. Actions
        action_layout = QHBoxLayout()
        refresh_btn = QPushButton("🔄 刷新列表")
        refresh_btn.clicked.connect(self._load_data)
        action_layout.addWidget(refresh_btn)

        import_btn = QPushButton("📥 批量导入")
        import_btn.clicked.connect(self._on_batch_import)
        action_layout.addWidget(import_btn)

        action_layout.addStretch()

        delete_btn = QPushButton("🗑 删除选中")
        delete_btn.setObjectName("danger")
        delete_btn.clicked.connect(self._on_delete)
        action_layout.addWidget(delete_btn)

        layout.addLayout(action_layout)

    def _load_data(self):
        self.table.setRowCount(0)
        # Get all IPs (we might need a get_all method in repo, or use base get_all)
        ips = self.repo.get_all(limit=1000)

        self.table.setRowCount(len(ips))
        for row, item in enumerate(ips):
            # ID
            self.table.setItem(row, 0, QTableWidgetItem(str(item["id"])))

            # Protocol
            self.table.setItem(row, 1, QTableWidgetItem(item["protocol"]))

            # IP
            self.table.setItem(row, 2, QTableWidgetItem(item["ip"]))

            # Port
            self.table.setItem(row, 3, QTableWidgetItem(item["port"]))

            # Auth
            auth_str = "-"
            if item["user"]:
                auth_str = f"{item['user']}:***"
            self.table.setItem(row, 4, QTableWidgetItem(auth_str))

            # Usage
            usage_item = QTableWidgetItem(str(item["usage_count"]))
            usage_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 5, usage_item)

            # Status
            status = item["status"]
            status_item = QTableWidgetItem(
                "✅ 活跃" if status == "active" else "🔴 禁用"
            )
            self.table.setItem(row, 6, status_item)

    def _on_add(self):
        ip = self.ip_input.text().strip()
        port = self.port_input.text().strip()

        if not ip or not port:
            Toast.error(self, "IP 和 端口不能为空")
            return

        try:
            self.repo.create(
                ip=ip,
                port=port,
                user=self.user_input.text().strip() or None,
                password=self.pass_input.text().strip() or None,
                protocol=self.proto_input.currentText(),
            )
            Toast.success(self, "添加成功")
            self.ip_input.clear()
            self.port_input.clear()
            self.user_input.clear()
            self.pass_input.clear()
            self._load_data()
        except Exception as e:
            Toast.error(self, f"添加失败: {e}")

    def _on_delete(self):
        rows = sorted(
            set(index.row() for index in self.table.selectedIndexes()), reverse=True
        )
        if not rows:
            return

        if (
            QMessageBox.question(
                self, "确认删除", f"确定删除选中 {len(rows)} 个 IP 吗？"
            )
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            for row in rows:
                item = self.table.item(row, 0)
                if not item:
                    continue
                ip_id = int(item.text())
                self.repo.delete(ip_id)

            Toast.success(self, "删除成功")
            self._load_data()
        except Exception as e:
            Toast.error(self, f"删除失败: {e}")

    def _on_batch_import(self):
        """Open batch import dialog."""
        dialog = BatchImportDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.lines:
            success_count = 0
            fail_count = 0
            default_proto = dialog.protocol.lower()

            for raw_line in dialog.lines:
                try:
                    result = self._parse_proxy_line(raw_line, default_proto)
                    if result:
                        self.repo.create(**result)
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception:
                    fail_count += 1

            Toast.success(
                self, f"导入完成: 成功 {success_count} 个, 失败 {fail_count} 个"
            )
            self._load_data()

    def _parse_proxy_line(self, raw_line: str, default_proto: str) -> dict | None:
        """解析一行代理配置。

        支持格式：
        1. protocol://username:password@ip:port
        2. protocol://ip:port
        3. username:password@ip:port
        4. ip:port

        Returns:
            解析成功返回 dict，失败返回 None
        """
        import re

        line = raw_line.strip()
        if not line:
            return None

        protocol = default_proto
        user = None
        password = None
        ip = None
        port = None

        # Step 1: 提取协议前缀
        if "://" in line:
            proto_part, rest = line.split("://", 1)
            protocol = proto_part.lower()
            line = rest

        # Step 2: 检查是否有认证信息 (user:pass@)
        if "@" in line:
            auth_part, host_part = line.rsplit("@", 1)
            # 解析 user:pass
            if ":" in auth_part:
                user, password = auth_part.split(":", 1)
            else:
                user = auth_part
            line = host_part

        # Step 3: 解析 ip:port
        # 支持 IPv6 格式 [ip]:port
        if line.startswith("["):
            # IPv6
            match = re.match(r"\[([^\]]+)\]:(\d+)", line)
            if match:
                ip = match.group(1)
                port = match.group(2)
        else:
            # IPv4 或域名
            parts = line.rsplit(":", 1)
            if len(parts) == 2:
                ip = parts[0]
                port = parts[1]

        if not ip or not port:
            return None

        return {
            "ip": ip.strip(),
            "port": port.strip(),
            "user": user.strip() if user else None,
            "password": password.strip() if password else None,
            "protocol": protocol,
        }


class BatchImportDialog(QDialog):
    """Dialog for bulk proxy import."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("批量导入 IP")
        self.setMinimumSize(500, 400)
        self.lines = []
        self.protocol = "http"

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Guide
        guide = QLabel(
            "支持格式 (每行一个):\n"
            "1. protocol://user:pass@ip:port\n"
            "2. protocol://ip:port\n"
            "3. user:pass@ip:port\n"
            "4. ip:port\n"
            "例如: socks5://admin:123456@1.2.3.4:1080"
        )
        layout.addWidget(guide)

        # Protocol Selection
        proto_layout = QHBoxLayout()
        proto_layout.addWidget(QLabel("默认协议:"))
        self.proto_combo = QComboBox()
        self.proto_combo.addItems(["http", "socks5", "socks4"])
        proto_layout.addWidget(self.proto_combo)
        proto_layout.addStretch()
        layout.addLayout(proto_layout)

        # Text Area
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "socks5://slyt31i1:slyt31i1@221.211.17.52:2008\n"
            "socks5://slyt31i2:slyt31i2@112.195.177.185:5200\n"
            "192.168.1.1:8080\n"
            "admin:pass@10.0.0.1:3128"
        )
        layout.addWidget(self.text_edit)

        # Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        import_btn = QPushButton("开始导入")
        import_btn.setObjectName("primary")
        import_btn.clicked.connect(self._on_import)
        btn_layout.addWidget(import_btn)

        layout.addLayout(btn_layout)

    def _on_import(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            self.reject()
            return

        self.lines = [line.strip() for line in text.splitlines() if line.strip()]
        self.protocol = self.proto_combo.currentText()
        self.accept()

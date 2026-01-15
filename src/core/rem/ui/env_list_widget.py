"""环境列表组件。

显示所有运行环境及其状态，支持创建/销毁操作。
"""

import asyncio

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.rem import EnvKind, EnvStatus
from src.core.rem.pool import EnvPool
from src.ui.components.combo_box import StyledComboBox as QComboBox


class CreateEnvDialog(QDialog):
    """创建环境对话框。"""
    
    # 需要代理/指纹配置的 Provider
    FINGERPRINT_PROVIDERS = {"bitbrowser", "virtualbrowser"}
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("创建环境")
        self.setMinimumWidth(400)
        
        # 应用深色主题样式
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e2e;
            }
            QLabel {
                color: #cdd6f4;
                background-color: transparent;
            }
            QLineEdit {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px 12px;
                color: #cdd6f4;
            }
            QLineEdit:focus {
                border-color: #89b4fa;
            }
            QComboBox {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 6px;
                padding: 8px 12px;
                color: #cdd6f4;
            }
            QComboBox::drop-down {
                border: none;
                width: 24px;
            }
            QComboBox QAbstractItemView {
                background-color: #313244;
                border: 1px solid #45475a;
                selection-background-color: #89b4fa;
                selection-color: #1e1e2e;
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
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        # 环境类型
        self.kind_combo = QComboBox()
        for kind in EnvKind:
            self.kind_combo.addItem(kind.value, kind)
        form.addRow("环境类型:", self.kind_combo)
        
        # Provider 选择
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["playwright_local", "bitbrowser", "virtualbrowser"])
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        form.addRow("Provider:", self.provider_combo)
        
        layout.addLayout(form)
        
        # 指纹浏览器专用配置区
        self.fingerprint_group = QWidget()
        fp_layout = QFormLayout(self.fingerprint_group)
        fp_layout.setContentsMargins(0, 10, 0, 0)
        
        # 代理配置
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("如: socks5://127.0.0.1:1080 或留空")
        fp_layout.addRow("代理地址:", self.proxy_input)
        
        # 指纹模式
        self.fingerprint_combo = QComboBox()
        self.fingerprint_combo.addItems(["随机生成", "自定义"])
        fp_layout.addRow("指纹模式:", self.fingerprint_combo)
        
        # 环境名称
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("可选，留空则自动生成")
        fp_layout.addRow("环境名称:", self.name_input)
        
        layout.addWidget(self.fingerprint_group)
        self.fingerprint_group.hide()  # 默认隐藏
        
        # 按钮
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # 初始化显示状态
        self._on_provider_changed(self.provider_combo.currentText())
    
    def _on_provider_changed(self, provider: str):
        """Provider 变更时切换配置显示。"""
        show_fp = provider in self.FINGERPRINT_PROVIDERS
        self.fingerprint_group.setVisible(show_fp)
        self.adjustSize()
    
    def get_values(self) -> tuple[EnvKind, str, dict]:
        """获取对话框输入值。
        
        Returns:
            (环境类型, Provider名称, 配置字典)
        """
        config = {}
        provider = self.provider_combo.currentText()
        
        if provider in self.FINGERPRINT_PROVIDERS:
            proxy_text = self.proxy_input.text().strip()
            if proxy_text:
                config["proxy"] = {"mode": 2, "value": proxy_text}
            
            name = self.name_input.text().strip()
            if name:
                config["creation_params"] = {"name_prefix": name}
            
            # 指纹模式: 随机生成时无需额外配置
        
        return (
            self.kind_combo.currentData(),
            provider,
            config,
        )


class DataLoaderThread(QThread):
    """数据加载线程。"""
    
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, pool: EnvPool):
        super().__init__()
        self._pool = pool
    
    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            envs = loop.run_until_complete(self._pool.list_all())
            loop.close()
            self.finished.emit(envs)
        except Exception as e:
            self.error.emit(str(e))


class EnvWorkerThread(QThread):
    """环境操作工作线程。"""
    
    finished = pyqtSignal(object)  # 成功时发射结果
    error = pyqtSignal(str)
    
    def __init__(self, action: str, **kwargs):
        super().__init__()
        self._action = action
        self._kwargs = kwargs
    
    def run(self):
        from src.core.rem.manager import get_environment_manager
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            manager = get_environment_manager()
            
            if self._action == "create":
                env = loop.run_until_complete(
                    manager.create_env(
                        self._kwargs["provider"],
                        self._kwargs.get("config"),
                    )
                )
                self.finished.emit(env)
            elif self._action == "destroy":
                success = loop.run_until_complete(
                    manager.destroy_env(self._kwargs["env_id"])
                )
                self.finished.emit(success)
            
            loop.close()
        except Exception as e:
            self.error.emit(str(e))


class EnvListWidget(QWidget):
    """环境列表组件。"""
    
    env_selected = pyqtSignal(str)
    
    COLUMNS = ["ID", "类型", "Provider", "状态", "任务", "操作"]
    STATUS_COLORS = {
        EnvStatus.READY: "#4ade80",
        EnvStatus.BUSY: "#facc15",
        EnvStatus.UNHEALTHY: "#f87171",
        EnvStatus.CREATING: "#60a5fa",
    }
    STATUS_TEXT = {
        EnvStatus.READY: "就绪",
        EnvStatus.BUSY: "忙碌",
        EnvStatus.UNHEALTHY: "异常",
        EnvStatus.CREATING: "创建中",
        EnvStatus.PAUSED: "暂停",
        EnvStatus.TERMINATING: "终止中",
        EnvStatus.DEAD: "已销毁",
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pool = EnvPool()
        self._loader_thread = None
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 标题栏
        header = QHBoxLayout()
        title = QLabel("运行环境")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        header.addWidget(title)
        header.addStretch()
        
        # 创建环境按钮
        self.create_btn = QPushButton("➕ 创建环境")
        self.create_btn.setStyleSheet("""
            QPushButton {
                background: rgba(74, 222, 128, 0.8);
                color: black;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(74, 222, 128, 1); }
        """)
        self.create_btn.clicked.connect(self._create_env)
        header.addWidget(self.create_btn)
        
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
            QPushButton:disabled { background: rgba(99, 102, 241, 0.3); }
        """)
        self.refresh_btn.clicked.connect(self.load_data)
        header.addWidget(self.refresh_btn)
        
        layout.addLayout(header)
        
        # Loading 指示器
        self.loading_bar = QProgressBar()
        self.loading_bar.setMaximum(0)
        self.loading_bar.setTextVisible(False)
        self.loading_bar.setFixedHeight(3)
        self.loading_bar.hide()
        layout.addWidget(self.loading_bar)
        
        # 错误提示
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #f87171; padding: 8px;")
        self.error_label.hide()
        layout.addWidget(self.error_label)
        
        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        header_view = self.table.horizontalHeader()
        if header_view:
            header_view.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(5, 100)
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: rgba(30, 30, 40, 0.8);
                color: white;
                border: none;
                gridline-color: rgba(255, 255, 255, 0.1);
            }
            QTableWidget::item { padding: 8px; }
            QHeaderView::section {
                background-color: rgba(50, 50, 60, 0.9);
                color: white;
                padding: 10px;
                border: none;
            }
        """)
        
        layout.addWidget(self.table)
        
        # 统计栏
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.7);")
        layout.addWidget(self.stats_label)
    
    def load_data(self):
        """加载环境数据。"""
        self._show_loading(True)
        self.error_label.hide()
        self.refresh_btn.setEnabled(False)
        
        self._loader_thread = DataLoaderThread(self._pool)
        self._loader_thread.finished.connect(self._on_data_loaded)
        self._loader_thread.error.connect(self._on_load_error)
        self._loader_thread.start()
    
    def _on_data_loaded(self, envs: list):
        """数据加载完成。"""
        self._show_loading(False)
        self.refresh_btn.setEnabled(True)
        
        self.table.setRowCount(0)
        
        ready_count = 0
        busy_count = 0
        
        for env in envs:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # ID
            id_item = QTableWidgetItem(env.id[:8] + "...")
            id_item.setData(Qt.ItemDataRole.UserRole, env.id)
            self.table.setItem(row, 0, id_item)
            
            # 类型
            self.table.setItem(row, 1, QTableWidgetItem(env.kind.value))
            
            # Provider
            self.table.setItem(row, 2, QTableWidgetItem(env.provider))
            
            # 状态
            status_text = self.STATUS_TEXT.get(env.status, env.status.value)
            status_item = QTableWidgetItem(status_text)
            if env.status in self.STATUS_COLORS:
                status_item.setForeground(QColor(self.STATUS_COLORS[env.status]))
            self.table.setItem(row, 3, status_item)
            
            # 任务
            task_id = env.task_run_id[:8] + "..." if env.task_run_id else "-"
            self.table.setItem(row, 4, QTableWidgetItem(task_id))
            
            # 操作按钮
            action_widget = QWidget()
            action_layout = QHBoxLayout(action_widget)
            action_layout.setContentsMargins(4, 2, 4, 2)
            
            if env.status in {EnvStatus.READY, EnvStatus.UNHEALTHY}:
                destroy_btn = QPushButton("🗑️ 销毁")
                destroy_btn.setStyleSheet("background: #f87171; color: white; border: none; padding: 4px 8px; border-radius: 2px;")
                destroy_btn.clicked.connect(lambda _, eid=env.id: self._destroy_env(eid))
                action_layout.addWidget(destroy_btn)
            else:
                action_layout.addWidget(QLabel("-"))
            
            self.table.setCellWidget(row, 5, action_widget)
            
            if env.status == EnvStatus.READY:
                ready_count += 1
            elif env.status == EnvStatus.BUSY:
                busy_count += 1
        
        self._update_stats(len(envs), ready_count, busy_count)
    
    def _on_load_error(self, error: str):
        """加载出错。"""
        self._show_loading(False)
        self.refresh_btn.setEnabled(True)
        self.error_label.setText(f"❌ 加载失败: {error}")
        self.error_label.show()
    
    def _create_env(self):
        """创建环境。"""
        dialog = CreateEnvDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            kind, provider, config = dialog.get_values()
            
            self.create_btn.setEnabled(False)
            self._show_loading(True)
            
            self._worker = EnvWorkerThread(
                action="create",
                provider=provider,
                config=config,
            )
            self._worker.finished.connect(self._on_create_finished)
            self._worker.error.connect(self._on_worker_error)
            self._worker.start()
    
    def _on_create_finished(self, env):
        """创建完成。"""
        self._show_loading(False)
        self.create_btn.setEnabled(True)
        QMessageBox.information(self, "成功", f"环境创建成功: {env.id[:8]}...")
        self.load_data()
    
    def _on_worker_error(self, error: str):
        """工作线程出错。"""
        self._show_loading(False)
        self.create_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        QMessageBox.critical(self, "错误", f"操作失败: {error}")
    
    def _destroy_env(self, env_id: str):
        """销毁环境。"""
        reply = QMessageBox.question(
            self, "确认", f"确定要销毁环境 {env_id[:8]}... ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._show_loading(True)
            
            self._worker = EnvWorkerThread(
                action="destroy",
                env_id=env_id,
            )
            self._worker.finished.connect(self._on_destroy_finished)
            self._worker.error.connect(self._on_worker_error)
            self._worker.start()
    
    def _on_destroy_finished(self, success: bool):
        """销毁完成。"""
        self._show_loading(False)
        if success:
            QMessageBox.information(self, "成功", "环境已销毁")
        else:
            QMessageBox.warning(self, "警告", "环境不存在或已被销毁")
        self.load_data()
    
    def _show_loading(self, show: bool):
        if show:
            self.loading_bar.show()
        else:
            self.loading_bar.hide()
    
    def _update_stats(self, total: int, ready: int, busy: int):
        self.stats_label.setText(f"总计: {total} | 就绪: {ready} | 忙碌: {busy}")
    
    def _on_cell_clicked(self, row: int, col: int):
        id_item = self.table.item(row, 0)
        if id_item:
            env_id = id_item.data(Qt.ItemDataRole.UserRole)
            self.env_selected.emit(env_id)

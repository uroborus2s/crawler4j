"""环境列表组件。

显示所有运行环境及其状态，支持创建/销毁操作。
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.rem import EnvKind, EnvStatus
from src.core.rem.ip_pool import get_ip_pool_manager
from src.core.rem.pool import EnvPool
from src.ui.components.combo_box import StyledComboBox as QComboBox


def get_create_env_default_name() -> str:
    """读取创建环境表单默认展示的环境名。"""
    from src.core.rem.manager import peek_next_env_name

    return peek_next_env_name()


class CreateEnvDialog(QDialog):
    """创建环境对话框。"""
    
    # 需要代理/指纹配置的 Provider
    FINGERPRINT_PROVIDERS = {"bitbrowser", "virtualbrowser"}
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._suggested_name = ""
        self.setWindowTitle("创建环境")
        self.setMinimumWidth(450)
        
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
            QGroupBox {
                border: 1px solid #45475a;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
                color: #bac2de;
            }
        """)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.form = QFormLayout()
        # 保持默认对齐 (通常是 AlignRight)，不要强制 AlignLeft
        
        # A. 基本配置
        # 环境类型
        self.kind_combo = QComboBox()
        for kind in EnvKind:
            self.kind_combo.addItem(kind.value, kind)
        self.form.addRow("环境类型:", self.kind_combo)
        
        # Provider 选择
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["playwright_local", "bitbrowser", "virtualbrowser"])
        self.provider_combo.setCurrentText("virtualbrowser")
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.form.addRow("Provider:", self.provider_combo)
        
        # 环境名称
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("默认使用自动创建名称，可修改")
        self.form.addRow("环境名称:", self.name_input)
        
        # B. 代理配置 (由 Provider 决定显隐)
        
        # 1. 代理模式
        from src.core.rem.models import ProxyMode
        self.proxy_mode_combo = QComboBox()
        self.proxy_mode_combo.addItem("不使用代理", ProxyMode.NONE)
        self.proxy_mode_combo.addItem("自定义代理 (自动/手动)", "custom") 
        self.proxy_mode_combo.addItem("使用系统代理", ProxyMode.SYSTEM)
        self.proxy_mode_combo.currentIndexChanged.connect(self._on_proxy_mode_changed)
        self.form.addRow("代理模式:", self.proxy_mode_combo)
        
        # 2. 自定义代理详细设置
        # 直接使用主布局以保证 Input 对齐，通过 Label 空格缩进体现层级
        
        # 2.1 来源选择
        self.proxy_source_combo = QComboBox()
        self.proxy_source_combo.addItem("自动获取 (从 IP 池)", "pool")
        self.proxy_source_combo.addItem("手动输入", "manual")
        self.proxy_source_combo.currentIndexChanged.connect(self._on_proxy_source_changed)
        
        # 2.1 来源选择
        self.proxy_source_combo = QComboBox()
        self.proxy_source_combo.addItem("自动获取 (从 IP 池)", "pool")
        self.proxy_source_combo.addItem("手动输入", "manual")
        self.proxy_source_combo.currentIndexChanged.connect(self._on_proxy_source_changed)
        
        self.form.addRow("代理来源:", self.proxy_source_combo)
        
        # 2.1.1 IP 池选择 (仅当 source=pool 时显示)
        self.pool_combo = QComboBox()
        # 加载 IP 池列表
        pool_manager = get_ip_pool_manager()
        pools = pool_manager.list_pools()
        for pool in pools:
            self.pool_combo.addItem(f"{pool.name} ({pool.id[:8]})", pool.id)
            
        if not pools:
            self.pool_combo.addItem("无可用 IP 池", "")
            self.pool_combo.setEnabled(False)
            
        self.form.addRow("选择 IP 池:", self.pool_combo)
        
        # 2.2 手动输入框
        self.proxy_manual_input = QLineEdit()
        self.proxy_manual_input.setPlaceholderText("socks5://user:pass@host:port")
        self.form.addRow("代理地址:", self.proxy_manual_input)
        
        layout.addLayout(self.form)
        
        # 按钮区
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # 初始化显示状态
        self._sync_suggested_name()
        self._on_provider_changed(self.provider_combo.currentText())

    def _sync_suggested_name(self):
        """同步当前默认环境名到输入框展示。"""
        self._suggested_name = get_create_env_default_name()
        self.name_input.setText(self._suggested_name)
        self.name_input.setCursorPosition(len(self._suggested_name))
        
    def _set_row_visible(self, widget: QWidget, visible: bool):
        """设置 Form 行的显隐 (包括标签)。"""
        label = self.form.labelForField(widget)
        if label:
            label.setVisible(visible)
        widget.setVisible(visible)
    
    def _on_provider_changed(self, provider: str):
        """Provider 变更时切换配置显示。"""
        is_fp_browser = provider in self.FINGERPRINT_PROVIDERS
        
        # 显隐代理模式行
        self._set_row_visible(self.proxy_mode_combo, is_fp_browser)
        
        # 更新自定义区域显隐 (依赖于 mode 和 provider)
        if is_fp_browser:
            self._on_proxy_mode_changed(self.proxy_mode_combo.currentIndex())
        else:
            self._set_row_visible(self.proxy_source_combo, False)
            self._set_row_visible(self.proxy_manual_input, False)
            
        self.adjustSize()
    
    def _on_proxy_mode_changed(self, index: int):
        """代理模式变更逻辑。"""
        # 如果当前根本不显示代理组 (Provider 不支持)，则不处理
        if not self.proxy_mode_combo.isVisible():
             self._set_row_visible(self.proxy_source_combo, False)
             self._set_row_visible(self.proxy_manual_input, False)
             return

        mode = self.proxy_mode_combo.currentData()
        
        # 只有在自定义模式下才显示详细配置
        show_custom_opts = (mode == "custom")
        self._set_row_visible(self.proxy_source_combo, show_custom_opts)
        
        if show_custom_opts:
            self._on_proxy_source_changed(self.proxy_source_combo.currentIndex())
        else:
            self._set_row_visible(self.proxy_manual_input, False)
        
        self.adjustSize()

    def _on_proxy_source_changed(self, index: int):
        """代理来源变更逻辑。"""
        source = self.proxy_source_combo.currentData()
        
        # 只有在 source combo 可见时才处理 input 显隐
        if self.proxy_source_combo.isVisible():
            self._set_row_visible(self.pool_combo, source == "pool")
            self._set_row_visible(self.proxy_manual_input, source == "manual")

    def get_values(self) -> tuple[EnvKind, str, dict]:
        """获取对话框输入值。
        
        Returns:
            (环境类型, Provider名称, 配置字典)
        """
        from src.core.rem.models import ProxyMode
        
        config = {}
        provider = self.provider_combo.currentText()
        
        # 处理名称
        name = self.name_input.text().strip()
        if name and name != self._suggested_name:
            config["env_name"] = name
        
        if provider in self.FINGERPRINT_PROVIDERS:
            # 1. 代理配置
            proxy_mode_enum = self.proxy_mode_combo.currentData()
            
            proxy_conf = {}
            
            if proxy_mode_enum == ProxyMode.NONE:
                proxy_conf = {"mode": ProxyMode.NONE}
                
            elif proxy_mode_enum == ProxyMode.SYSTEM:
                proxy_conf = {"mode": ProxyMode.SYSTEM}
                
            else: # Custom ("custom")
                source = self.proxy_source_combo.currentData()
                if source == "pool":
                    pool_id = self.pool_combo.currentData()
                    proxy_conf = {
                        "mode": ProxyMode.POOL,
                        "pool_id": pool_id
                    }
                else: # manual
                    raw_val = self.proxy_manual_input.text().strip()
                    proxy_conf = {
                        "mode": ProxyMode.STATIC,
                        "static_value": raw_val
                    }
            
            config["proxy"] = proxy_conf
            
            # 2. 指纹配置 (去除输入，默认为随机或由Provider处理)
        
        return (
            self.kind_combo.currentData(),
            provider,
            config,
        )


class DataLoaderThread(QThread):
    """数据加载线程。"""
    
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, pool: EnvPool, run_gc: bool = False):
        super().__init__()
        self._pool = pool
        self._run_gc = run_gc
    
    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 仅在需要时执行 GC
            if self._run_gc:
                from src.core.rem.manager import get_environment_manager
                manager = get_environment_manager()
                loop.run_until_complete(manager.run_gc())

            # 使用共享的 pool，无需重新加载
            envs = loop.run_until_complete(self._pool.list_all())
            loop.close()
            self.finished.emit(envs)
        except Exception as e:
            self.error.emit(str(e))


class EnvWorkerThread(QThread):
    """环境操作工作线程。
    
    注意：Playwright 的 WebSocket 连接绑定到创建它的事件循环。
    为避免连接失效，start 操作使用主线程的 qasync 事件循环。
    """
    
    finished = pyqtSignal(object)  # 成功时发射结果
    error = pyqtSignal(str)
    
    # 共享的事件循环（用于保持 Playwright 连接）
    _shared_loop: asyncio.AbstractEventLoop | None = None
    
    def __init__(self, action: str, **kwargs):
        super().__init__()
        self._action = action
        self._kwargs = kwargs
    
    @classmethod
    def _get_shared_loop(cls) -> asyncio.AbstractEventLoop:
        """获取或创建共享事件循环。"""
        if cls._shared_loop is None or cls._shared_loop.is_closed():
            cls._shared_loop = asyncio.new_event_loop()
        return cls._shared_loop
    
    def run(self):
        from src.core.rem.manager import get_environment_manager
        
        try:
            # 对于需要保持连接的操作，使用共享循环
            # 对于其他操作，使用临时循环
            if self._action in ("start", "stop"):
                loop = self._get_shared_loop()
                asyncio.set_event_loop(loop)
                should_close_loop = False
            else:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                should_close_loop = True
            
            manager = get_environment_manager()
            
            if self._action == "create":
                # Ensure provider name is a string
                provider_obj = self._kwargs["provider"]
                provider_name = provider_obj.name if hasattr(provider_obj, "name") else str(provider_obj)
                
                env = loop.run_until_complete(
                    manager.create_env(
                        provider_name=provider_name,
                        config=self._kwargs.get("config"),
                        requirement=self._kwargs.get("requirement"),
                    )
                )
                self.finished.emit(env)
            elif self._action == "destroy":
                success = loop.run_until_complete(
                    manager.destroy_env(self._kwargs["env_id"])
                )
                self.finished.emit(success)
            elif self._action == "start":
                success = loop.run_until_complete(
                    manager.start_env(self._kwargs["env_id"])
                )
                self.finished.emit(success)
            elif self._action == "stop":
                success = loop.run_until_complete(
                    manager.stop_env(self._kwargs["env_id"])
                )
                self.finished.emit(success)
            elif self._action == "pause":
                success = loop.run_until_complete(
                    manager.pause_env(self._kwargs["env_id"])
                )
                self.finished.emit(success)
            elif self._action == "resume":
                success = loop.run_until_complete(
                    manager.resume_env(self._kwargs["env_id"])
                )
                self.finished.emit(success)
            
            # 只关闭临时循环，共享循环保持打开
            if should_close_loop:
                loop.close()
        except Exception as e:
            self.error.emit(str(e))


@dataclass
class EnvDisplayItem:
    """环境显示项包装。"""
    raw: Any # EnvInfo
    display_status_text: str

class EnvListWidget(QWidget):
    """环境列表组件。"""
    
    env_selected = pyqtSignal(str)
    
    COLUMNS = ["ID", "名称", "类型", "Provider", "状态", "任务", "操作"]
    STATUS_COLORS = {
        EnvStatus.READY: "#4ade80",
        EnvStatus.BUSY: "#facc15",
        EnvStatus.RUNNING: "#22c55e",  # 运行中 - 绿色
        EnvStatus.ERROR: "#f87171",
        EnvStatus.CREATING: "#60a5fa",
    }
    STATUS_TEXT = {
        EnvStatus.READY: "就绪",
        EnvStatus.BUSY: "启动中",      # 窗口已开启，尚未连接
        EnvStatus.RUNNING: "运行中",   # 已连接 Playwright
        EnvStatus.ERROR: "错误",
        EnvStatus.CREATING: "创建中",
        EnvStatus.PAUSED: "暂停",
        EnvStatus.TERMINATING: "终止中",
        EnvStatus.DEAD: "已销毁",
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        # 使用全局 EnvironmentManager 的共享 pool 实例
        from src.core.rem.manager import get_environment_manager
        self._manager = get_environment_manager()
        self._pool = self._manager.pool
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
        
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setFixedSize(32, 32)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 16px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
            QPushButton:disabled { background: rgba(99, 102, 241, 0.3); }
        """)
        self.refresh_btn.clicked.connect(lambda: self.load_data(run_gc=True))
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
        
        # 表格 (SkyDataTable)
        from src.ui.components.data_table import SkyDataTable
        
        columns = [
            ("id", "ID", 120),
            ("name", "名称", 160),
            ("kind", "类型", 100),
            ("provider", "节点类型", 110),
            ("status", "状态", 90),
            ("task", "任务", 160),
            ("actions", "操作", None),
        ]
        
        self.table = SkyDataTable(columns=columns)
        self.table.set_render_callback(self._render_row)
        layout.addWidget(self.table)
        
        # 统计栏
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.7);")
        layout.addWidget(self.stats_label)
    
    def load_data(self, run_gc: bool = False):
        """加载环境数据。"""
        self.table.set_loading(True)
        self.error_label.hide()
        self.refresh_btn.setEnabled(False)
        
        self._loader_thread = DataLoaderThread(self._pool, run_gc=run_gc)
        self._loader_thread.finished.connect(self._on_data_loaded)
        self._loader_thread.error.connect(self._on_load_error)
        self._loader_thread.start()
    
    def _on_data_loaded(self, envs: list):
        """数据加载完成。"""
        self.table.set_loading(False)
        self.refresh_btn.setEnabled(True)
        
        ready_count = 0
        busy_count = 0
        
        display_items = []
        for env in envs:
            status_text = self.STATUS_TEXT.get(env.status, str(env.status.value))
            display_items.append(EnvDisplayItem(
                raw=env,
                display_status_text=str(status_text)
            ))
            
            if env.status == EnvStatus.READY:
                ready_count += 1
            elif env.status == EnvStatus.BUSY:
                busy_count += 1
                
        self.table.set_data(display_items)
        self._display_items = display_items  # 保存引用供编辑对话框使用
        self._update_stats(len(envs), ready_count, busy_count)
        
    def _render_row(self, row: int, item: EnvDisplayItem, table):
        """渲染单行。"""
        env = item.raw
        
        # 0: ID
        id_item = QTableWidgetItem(str(env.id))
        id_item.setData(Qt.ItemDataRole.UserRole, env.id)
        table.setItem(row, 0, id_item)
        
        # 1: 名称
        name_text = env.name if env.name else "-"
        table.setItem(row, 1, QTableWidgetItem(name_text))
        
        # 2: 类型
        table.setItem(row, 2, QTableWidgetItem(env.kind.value))
        
        # 3: Provider
        table.setItem(row, 3, QTableWidgetItem(env.provider))
        
        # 4: 状态
        status_text = item.display_status_text
        status_item = QTableWidgetItem(status_text)
        if env.status in self.STATUS_COLORS:
            status_item.setForeground(QColor(self.STATUS_COLORS[env.status]))
        table.setItem(row, 4, status_item)
        
        # 5: 任务
        task_id = env.task_run_id[:8] + "..." if env.task_run_id else "-"
        table.setItem(row, 5, QTableWidgetItem(task_id))
        
        # 6: 操作按钮
        action_widget = self._create_action_widget(env)
        table.setCellWidget(row, 6, action_widget)
        
    def _create_action_widget(self, env) -> QWidget:
        """创建操作按钮组。
        
        按钮布局:
        - READY: [▶运行] [⏸暂停] [✏编辑] [🗑销毁]
        - BUSY: [⏹停止]
        - PAUSED: [▶启动] [✏编辑] [🗑销毁]
        """
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)
        
        btn_style = """
            QPushButton {
                padding: 4px 8px;
                border: none;
                border-radius: 4px;
                font-size: 12px;
                min-width: 24px;
                min-height: 24px;
            }
            QPushButton:hover { opacity: 0.85; }
        """
                
        if env.status == EnvStatus.READY:
            # [▶运行]
            run_btn = QPushButton("▶")
            run_btn.setToolTip("运行")
            run_btn.setStyleSheet(btn_style + "QPushButton { background: #4ade80; color: black; }")
            run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            run_btn.clicked.connect(lambda _, eid=env.id: self._start_env(eid))
            layout.addWidget(run_btn)
            
            # [⏸暂停]
            pause_btn = QPushButton("⏸")
            pause_btn.setToolTip("暂停")
            pause_btn.setStyleSheet(btn_style + "QPushButton { background: #facc15; color: black; }")
            pause_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            pause_btn.clicked.connect(lambda _, eid=env.id: self._pause_env(eid))
            layout.addWidget(pause_btn)
            
            # [✏编辑]
            edit_btn = QPushButton("✏")
            edit_btn.setToolTip("编辑")
            edit_btn.setStyleSheet(btn_style + "QPushButton { background: #60a5fa; color: white; }")
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.clicked.connect(lambda _, eid=env.id: self._edit_env(eid))
            layout.addWidget(edit_btn)
            
            # [🗑销毁]
            destroy_btn = QPushButton("🗑")
            destroy_btn.setToolTip("销毁")
            destroy_btn.setStyleSheet(btn_style + "QPushButton { background: #f87171; color: white; }")
            destroy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            destroy_btn.clicked.connect(lambda _, eid=env.id: self._destroy_env(eid))
            layout.addWidget(destroy_btn)
            
        elif env.status in (EnvStatus.RUNNING,EnvStatus.BUSY):
            # [⏹停止]
            stop_btn = QPushButton("⏹ 停止")
            stop_btn.setStyleSheet(btn_style + "QPushButton { background: #f87171; color: white; }")
            stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            stop_btn.clicked.connect(lambda _, eid=env.id: self._stop_env(eid))
            layout.addWidget(stop_btn)
            
        elif env.status == EnvStatus.PAUSED:
            # [▶启动]
            resume_btn = QPushButton("▶")
            resume_btn.setToolTip("启动")
            resume_btn.setStyleSheet(btn_style + "QPushButton { background: #4ade80; color: black; }")
            resume_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            resume_btn.clicked.connect(lambda _, eid=env.id: self._resume_env(eid))
            layout.addWidget(resume_btn)
            
            # [✏编辑]
            edit_btn = QPushButton("✏")
            edit_btn.setToolTip("编辑")
            edit_btn.setStyleSheet(btn_style + "QPushButton { background: #60a5fa; color: white; }")
            edit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            edit_btn.clicked.connect(lambda _, eid=env.id: self._edit_env(eid))
            layout.addWidget(edit_btn)
            
            # [🗑销毁]
            destroy_btn = QPushButton("🗑")
            destroy_btn.setToolTip("销毁")
            destroy_btn.setStyleSheet(btn_style + "QPushButton { background: #f87171; color: white; }")
            destroy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            destroy_btn.clicked.connect(lambda _, eid=env.id: self._destroy_env(eid))
            layout.addWidget(destroy_btn)
            
        else:
            # 其他状态：无操作
            label = QLabel("-")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            
        layout.addStretch()
        return widget
    
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
            
            # Construct EnvRequirement to pass proxy_config correctly
            from src.core.rem.models import EnvRequirement, ProxyConfig
            
            requirement = EnvRequirement(kind=kind)
            if "proxy" in config:
                requirement.proxy_config = ProxyConfig.from_dict(config["proxy"])
            
            self._worker = EnvWorkerThread(
                action="create",
                provider=provider,
                config=config,
                requirement=requirement,
            )
            self._worker.finished.connect(self._on_create_finished)
            self._worker.error.connect(self._on_worker_error)
            self._worker.start()
    
    def _on_create_finished(self, env):
        """创建完成。"""
        self._show_loading(False)
        self.create_btn.setEnabled(True)
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
            self, "确认", f"确定要销毁环境 {env_id} ?",
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
            QMessageBox.warning(
                self,
                "警告",
                "环境销毁失败，数据库记录已保留。请检查指纹浏览器连接后重试。",
            )
        self.load_data()
    
    def _start_env(self, env_id: str):
        """启动环境（打开窗口）。"""
        self._show_loading(True)
        self._worker = EnvWorkerThread(action="start", env_id=env_id)
        self._worker.finished.connect(self._on_action_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()
    
    def _stop_env(self, env_id: str):
        """停止环境（关闭窗口）。"""
        self._show_loading(True)
        self._worker = EnvWorkerThread(action="stop", env_id=env_id)
        self._worker.finished.connect(self._on_action_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()
    
    def _pause_env(self, env_id: str):
        """暂停环境。"""
        self._show_loading(True)
        self._worker = EnvWorkerThread(action="pause", env_id=env_id)
        self._worker.finished.connect(self._on_action_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()
    
    def _resume_env(self, env_id: str):
        """恢复环境。"""
        self._show_loading(True)
        self._worker = EnvWorkerThread(action="resume", env_id=env_id)
        self._worker.finished.connect(self._on_action_finished)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()
    
    def _edit_env(self, env_id: str):
        """编辑环境（弹出对话框）。"""
        from src.core.rem.ui.edit_env_dialog import EditEnvDialog
        
        # 从表格数据中查找环境
        env = None
        for i in range(self.table.rowCount()):
            id_item = self.table.item(i, 0)
            if id_item and id_item.data(Qt.ItemDataRole.UserRole) == env_id:
                # 从 display_items 获取原始环境对象
                items = getattr(self, "_display_items", [])
                if i < len(items):
                    env = items[i].raw
                break
        
        if not env:
            # 如果找不到，从 pool 异步加载
            QMessageBox.warning(self, "错误", f"未找到环境: {env_id}...")
            return
        
        dialog = EditEnvDialog(env, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_data()  # 刷新列表
    
    def _on_action_finished(self, success: bool):
        """通用操作完成回调。
        
        注意: 失败时错误信息由 Shell 通过 Toast 显示，
        详见 ENV_OPERATION_FAILED 事件处理。
        """
        self._show_loading(False)
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

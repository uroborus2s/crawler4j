"""Environments page.

Manages browser environment bindings and synchronization with fingerprint browsers.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.ui.widgets.confirm_dialog import ConfirmDialog
from src.ui.widgets.data_table import DataTable
from src.ui.widgets.toast import Toast
from src.utils.storage import (
    CtripAccountRepository,
    EnvironmentRepository,
    LaborAccountRepository,
    ProxyIPRepository,
)


class EnvironmentsPage(QWidget):
    """Environment management page.

    Synchronizes browser profiles and manages system bindings.
    """

    COLUMNS = [
        ("seq", "序号", 50),
        ("name", "名称", 150),
        ("group", "分组", 100),
        ("proxy_ip", "代理IP", 120),
        ("system_type", "类型", 120),
        ("local_status", "账号占用", 100),
        ("browser_status", "状态", 80),
        ("created_at", "创建时间", 150),
        ("actions", "操作账户", 150),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)

        self.env_repo = EnvironmentRepository()
        self.ctrip_repo = CtripAccountRepository()
        self.labor_repo = LaborAccountRepository()
        self.proxy_repo = ProxyIPRepository()

        # Threads
        self._refresh_thread = None
        self._launcher_thread = None

        self._setup_ui()
        self.table.set_row_height(48)

        # 监听事件
        from src.core.events import get_event_bus

        bus = get_event_bus()
        bus.environment_created.connect(lambda _: self._load_data())
        bus.environment_status_changed.connect(
            lambda _env_id, _status: self._load_data()
        )

        # Initial full sync on app start with cleanup
        self._load_data(sync=True, cleanup=True)

    def _setup_ui(self):
        """Setup the page UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        header = QHBoxLayout()

        title = QLabel("环境管理")
        title.setObjectName("h1")
        header.addWidget(title)

        header.addStretch()

        self.stats_label = QLabel("就绪")
        self.stats_label.setStyleSheet("color: #a6adc8;")
        header.addWidget(self.stats_label)

        layout.addLayout(header)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        refresh_btn = QPushButton("🔄 同步状态")
        refresh_btn.clicked.connect(lambda: self._load_data(sync=True))
        toolbar.addWidget(refresh_btn)

        pool_btn = QPushButton("🌐 IP池管理")
        pool_btn.clicked.connect(self._on_ip_pool)
        toolbar.addWidget(pool_btn)

        create_btn = QPushButton("+ 创建新环境")
        create_btn.setObjectName("primary")
        create_btn.clicked.connect(self._on_create)
        toolbar.addWidget(create_btn)

        toolbar.addStretch()

        # Batch Delete Removed as per request

        layout.addLayout(toolbar)

        # Table
        self.table = DataTable(self.COLUMNS)
        # Selection logic is less relevant now as we use per-row actions
        layout.addWidget(self.table, 1)

    def _load_data(self, sync=False, cleanup=False):
        """Load data, optionally syncing from remote API."""
        if cleanup:
            self.stats_label.setText("正在清理残留进程...")
        elif sync:
            self.stats_label.setText("正在同步...")
        else:
            self.stats_label.setText("正在加载...")

        from src.ui.threads.data_thread import DataRefreshThread

        if self._refresh_thread and self._refresh_thread.isRunning():
            return

        self._refresh_thread = DataRefreshThread(
            env_repo=self.env_repo,
            ctrip_repo=self.ctrip_repo,
            labor_repo=self.labor_repo,
            proxy_repo=self.proxy_repo,
            cleanup=cleanup,
        )
        self._refresh_thread.data_loaded.connect(self._on_data_loaded)
        self._refresh_thread.error_occurred.connect(self._on_data_error)
        self._refresh_thread.start()

    def _on_data_loaded(self, display_data):
        self._update_table(display_data)
        self.stats_label.setText(f"共 {len(display_data)} 个环境 (实时)")

    def _on_data_error(self, error):
        # Don't show toast on silent errors to avoid spam
        self.stats_label.setText("同步异常")
        # Only log if debugging, but here we just update status label

    def _update_table(self, display_data):
        """Update table items while preserving selection if possible (though table Reset usually clears it)."""
        # Inject renderer
        for row in display_data:
            row["actions_renderer"] = self._render_actions

        self.table.set_data(display_data)

    def _render_actions(self, row_data) -> QWidget:
        """Create actions widget for a row with a primary button and a dropdown."""
        container = QWidget()
        # Use a horizontal layout with minimal margins
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        sys_type = row_data["system_type"]
        remote_exists = row_data["raw_remote"] is not None

        # 1. Open Button (Primary Action) or Status Label
        browser_status = str(row_data.get("browser_status", "")).lower()
        is_running = browser_status in ["running", "active", "open", "opened"]

        if is_running:
            # Show "Already Open" Label
            status_btn = QPushButton("✅ 已打开")
            status_btn.setMinimumWidth(75)
            status_btn.setMinimumHeight(28)
            status_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ecfdf5; 
                    color: #059669;
                    border: 1px solid #a7f3d0;
                    border_radius: 4px;
                    padding: 4px 8px;
                    font-weight: 500;
                    font-size: 13px;
                }
            """)
            status_btn.setEnabled(False)  # Already open, no action
            layout.addWidget(status_btn)
        else:
            # Open Button
            open_btn = QPushButton("🚀 打开")
            open_btn.setMinimumWidth(75)
            open_btn.setMinimumHeight(28)

            # Enhanced styling to ensure text is visible and button looks professional
            open_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563eb;
                    color: #ffffff;
                    border: none;
                    border_radius: 4px;
                    padding: 4px 8px;
                    font-weight: 500;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: #1d4ed8;
                }
                QPushButton:disabled {
                    background-color: #94a3b8;
                    color: #e2e8f0;
                }
            """)
            open_btn.setEnabled(remote_exists)
            open_btn.clicked.connect(lambda: self._on_open_browser(row_data))
            layout.addWidget(open_btn)

        # 2. More Menu Button (⋮)
        more_btn = QPushButton("⋮")
        more_btn.setFixedSize(28, 28)
        more_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #e2e8f0;
                border_radius: 4px;
                color: #64748b;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f8fafc;
                color: #334155;
                border-color: #cbd5e1;
            }
            QPushButton::menu-indicator { image: none; }
        """)

        # Create Menu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #e2e8f0;
                border_radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px 6px 12px;
                border_radius: 4px;
                color: #334155;
            }
            QMenu::item:selected {
                background-color: #f1f5f9;
                color: #2563eb;
            }
            QMenu::item:disabled {
                color: #94a3b8;
            }
        """)

        # Edit Action
        edit_act = QAction("✏️ 修改配置", self)
        edit_act.triggered.connect(
            lambda: Toast.info(self, "编辑指纹功能请登录浏览器端操作。")
        )
        menu.addAction(edit_act)

        # Clone Action
        clone_act = QAction("📋 克隆窗口", self)
        clone_act.setEnabled(False)
        menu.addAction(clone_act)

        menu.addSeparator()

        # Delete Action
        del_act = QAction("🗑 删除窗口", self)
        can_delete = sys_type in ["crawler4j系统", "error"]
        del_act.setEnabled(can_delete)
        if not can_delete:
            del_act.setText("🗑 删除 (非系统环境)")
            del_act.setIconText("🗑 删除 (非系统环境)")

        del_act.triggered.connect(lambda: self._on_delete_env(row_data))
        menu.addAction(del_act)

        # Set Menu to Button
        more_btn.setMenu(menu)
        layout.addWidget(more_btn)

        layout.addStretch()
        return container

    def _on_selection_changed(self, indices: list):
        pass  # No longer needed for actions

    def _on_ip_pool(self):
        """Open IP Pool Manager."""
        from src.ui.dialogs.proxy_manager_dialog import ProxyManagerDialog

        ProxyManagerDialog(self).exec()

    def _on_create(self):
        """Handle environment creation."""
        from src.core.environment_manager import (
            CreateEnvironmentParams,
            EnvironmentManager,
        )
        from src.ui.dialogs.create_env_dialog import CreateEnvDialog

        result = CreateEnvDialog.create_env(self)
        if not result:
            return

        # 构建创建参数
        proxy_ip_id = None
        proxy_config = None

        if result.get("proxy_mode") == "auto":
            least_used = self.proxy_repo.get_least_used()
            if not least_used:
                Toast.error(self, "IP 池中没有可用的活跃 IP，创建失败")
                return

            proxy_ip_id = least_used["id"]
            proxy_config = {
                "type": least_used["protocol"],
                "host": least_used["ip"],
                "port": least_used["port"],
                "user": least_used["user"],
                "pass": least_used["password"],
            }

        params = CreateEnvironmentParams(
            name=result.get("name"),
            ctrip_account_id=result.get("ctrip_account_id"),
            labor_account_id=result.get("labor_account_id"),
            proxy_ip_id=proxy_ip_id,
            proxy_config=proxy_config or result.get("proxy_config"),
            fingerprint_config=result.get("fingerprint_config"),
            group_id=result.get("group_id"),
            daily_open_limit=result.get("daily_open_limit", 0),
            remark=f"Created by Crawler4j [{result.get('platform', 'Ctrip')}]",
        )

        try:
            manager = EnvironmentManager()
            env = manager.create_environment(params)

            if env:
                Toast.success(self, "环境创建并绑定成功")
                self._load_data()
            else:
                Toast.error(self, "环境创建失败")

        except Exception as e:
            Toast.error(self, f"环境创建失败: {e}")

    def _on_delete_env(self, item: dict):
        """Handle deletion strategy."""
        from src.core.environment_manager import DestroyReason, EnvironmentManager

        sys_type = item["system_type"]

        if sys_type == "无":
            Toast.warning(self, "非系统创建环境，不可删除")
            return

        if not ConfirmDialog.confirm(
            self, "删除环境", "确定要删除此环境吗？", danger=True
        ):
            return

        try:
            local_env = item.get("raw_local")

            if not local_env or not local_env.get("id"):
                Toast.error(self, "无法获取环境信息")
                return

            manager = EnvironmentManager()
            reason = (
                DestroyReason.ERROR if sys_type == "error" else DestroyReason.MANUAL
            )

            if manager.destroy_environment(local_env["id"], reason):
                Toast.success(self, "删除成功")
                self._load_data()
            else:
                Toast.error(self, "删除失败")

        except Exception as e:
            Toast.error(self, f"删除失败: {e}")

    def _on_open_browser(self, item: dict):
        """Open browser and trigger auto-login if bound."""
        pid = item["id"]
        local_env = item.get("raw_local")
        ctrip_id = local_env.get("ctrip_account_id") if local_env else None
        labor_id = local_env.get("labor_account_id") if local_env else None
        env_id = local_env.get("id") if local_env else None

        # Disable button to prevent double click
        btn = self.sender()
        if isinstance(btn, QPushButton):
            btn.setEnabled(False)
            btn.setText("启动中...")

        try:
            # 1. 每日打开限制检查
            if env_id:
                if not self.env_repo.check_and_increment_daily_usage(env_id):
                    Toast.error(self, "今日打开次数已达上限")
                    # Restore button
                    if isinstance(btn, QPushButton):
                        btn.setEnabled(True)
                        btn.setText("启动")
                    return

                # Update status to running locally
                from datetime import datetime

                self.env_repo.update_status(
                    env_id, "running", datetime.now().isoformat()
                )

            from src.ui.threads.browser_thread import BrowserLauncherThread

            Toast.info(self, "正在启动浏览器...")

            # Keep thread reference to prevent GC
            self._launcher_thread = BrowserLauncherThread(
                profile_id=pid,
                ctrip_account_id=ctrip_id,
                labor_account_id=labor_id,
                env_id=env_id,
            )
            self._launcher_thread.finished_signal.connect(self._on_browser_opened)
            self._launcher_thread.input_signal.connect(self._on_worker_input_request)
            self._launcher_thread.start()

        except Exception as e:
            print(f"Start Error: {e}")
            Toast.error(self, f"启动异常: {e}")
            # Restore button state on error
            if isinstance(btn, QPushButton):
                btn.setEnabled(True)
                btn.setText("启动")
            # Revert status if needed
            if env_id:
                self.env_repo.update_status(env_id, "idle")
            self._load_data()

    def _on_worker_input_request(self, container: dict, event):
        """Handle background thread input request via blocking dialog."""
        title = container.get("title", "输入")
        label = container.get("label", "请输入:")
        default_text = container.get("text", "")

        from PyQt6.QtWidgets import QInputDialog, QLineEdit

        try:
            text, ok = QInputDialog.getText(
                self, title, label, QLineEdit.EchoMode.Normal, default_text
            )

            if ok and text:
                container["value"] = text.strip()
            else:
                container["value"] = None
        except Exception as e:
            print(f"Input dialog error: {e}")
            container["value"] = None
        finally:
            # Signal the waiting thread to continue
            event.set()

    def _on_browser_opened(self, success: bool, msg: str):
        """Handle browser launch result."""
        if success:
            Toast.success(self, msg)
        else:
            Toast.error(self, f"启动失败: {msg}")
        # 无论成功失败都刷新状态
        self._load_data()

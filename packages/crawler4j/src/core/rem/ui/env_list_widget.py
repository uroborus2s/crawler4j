"""环境列表组件。

显示所有运行环境及其状态，支持创建/销毁操作。
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.core.foundation.logging import logger
from src.core.rem.import_job_service import get_existing_env_import_job_service
from src.core.rem import EnvKind, EnvStatus
from src.core.rem.manager import RESOURCE_POOL_METADATA_NAMESPACE
from src.core.rem.ip_pool import get_ip_pool_manager
from src.core.rem.pool import EnvPool
from src.core.rem.ui.import_existing_env_dialog import ImportExistingEnvDialog
from src.ui.components.button import StyledButton
from src.ui.components.combo_box import StyledComboBox as QComboBox
from src.ui.components.confirm_dialog import ConfirmDialog
from src.ui.components.data_table import SkyDataTable
from src.ui.components.data_table_query import resolve_local_data_table_result
from src.ui.components.dialog_async import open_dialog_async
from src.ui.components.dialog_window import configure_titled_dialog
from src.ui.components.line_edit import StyledLineEdit as QLineEdit
from src.ui.components.message_dialog import MessageDialog, MessageKind
from src.ui.components.progress_dialog import ProgressDialog


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
        configure_titled_dialog(self)
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
        cancel_btn.setObjectName("createEnvCancelButton")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)

        create_btn = StyledButton(
            "创建",
            variant="success",
            min_height=40,
            min_width=92,
            horizontal_padding=20,
        )
        create_btn.setObjectName("createEnvSubmitButton")
        create_btn.clicked.connect(self.accept)
        button_row.addWidget(create_btn)
        layout.addLayout(button_row)
        
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
    
    def __init__(self, pool: EnvPool, run_gc: bool = False, reload_from_db: bool = False):
        super().__init__()
        self._pool = pool
        self._run_gc = run_gc
        self._reload_from_db = reload_from_db
    
    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            if self._reload_from_db:
                reload_pool = getattr(self._pool, "reload_from_db", None)
                if callable(reload_pool):
                    loop.run_until_complete(reload_pool())

            # 仅在需要时执行 GC
            if self._run_gc:
                from src.core.rem.manager import get_environment_manager
                manager = get_environment_manager()
                loop.run_until_complete(manager.run_gc())

            # 使用共享的 pool，无需重新加载
            envs = loop.run_until_complete(self._pool.list_all())
            records = [
                EnvLoadedRecord(env=env, env_metadata=self._load_env_metadata(env))
                for env in envs
            ]
            loop.close()
            self.finished.emit(records)
        except Exception as e:
            self.error.emit(str(e))

    def _load_env_metadata(self, env: Any) -> dict[str, Any]:
        list_metadata = getattr(self._pool, "list_metadata", None)
        if not callable(list_metadata):
            return {}
        try:
            metadata = list_metadata(env.id)
        except Exception as exc:
            logger.warning(f"[REM] 读取环境元数据失败: env_id={getattr(env, 'id', '')} error={exc}")
            return {}
        return metadata if isinstance(metadata, dict) else {}


@dataclass(frozen=True)
class EnvLoadedRecord:
    """环境列表加载结果。"""

    env: Any
    env_metadata: dict[str, Any]


@dataclass
class EnvDisplayItem:
    """环境显示项包装。"""
    raw: Any # EnvInfo
    display_status_text: str
    env_metadata: dict[str, Any]
    availability: dict[str, Any]

class EnvListWidget(QWidget):
    """环境列表组件。"""
    
    env_selected = pyqtSignal(str)
    TABLE_SCHEMA = {
        "columns": [
            {"key": "id", "label": "ID", "type": "text", "width": 120},
            {"key": "name", "label": "名称", "type": "text", "width": 160},
            {"key": "kind", "label": "类型", "type": "text", "width": 100},
            {"key": "provider", "label": "节点类型", "type": "text", "width": 110},
            {"key": "status", "label": "状态", "type": "text", "width": 90},
            {"key": "availability", "label": "可用状态", "type": "text", "width": 150},
            {"key": "task", "label": "任务", "type": "text", "width": 160},
            {"key": "actions", "label": "操作", "type": "actions", "stretch": True},
        ],
        "features": {
            "search": {"enabled": True, "placeholder": "搜索环境、Provider 或任务"},
            "sort": {
                "enabled": True,
                "default": [{"field": "name", "direction": "asc"}],
            },
            "pagination": {"enabled": True, "page_size": 20, "page_size_options": [10, 20, 50, 100]},
        },
    }
    
    COLUMNS = ["ID", "名称", "类型", "Provider", "状态", "可用状态", "任务", "操作"]
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
        self._import_job_service = get_existing_env_import_job_service()
        self._pool = self._manager.pool
        self._loader_thread = None
        self._display_items: list[EnvDisplayItem] = []
        self._load_in_progress = False
        self._reload_requested = False
        self._reload_run_gc = False
        self._reload_from_db = False
        self._operation_in_progress = False
        self._operation_task: asyncio.Task[Any] | None = None
        self._pending_tasks: set[asyncio.Task[Any]] = set()
        self._table_rows: list[dict[str, Any]] = []
        self._progress_dialog: ProgressDialog | None = None
        self._setup_ui()
        self.destroyed.connect(lambda *_args: (self._cancel_pending_tasks(), self._close_progress_dialog()))
    
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
        self.create_btn = StyledButton("创建环境", variant="success", min_height=36)
        self.create_btn.clicked.connect(self._create_env)
        header.addWidget(self.create_btn)

        self.import_existing_btn = StyledButton("从已有环境导入", variant="warning", min_height=36)
        self.import_existing_btn.clicked.connect(self._import_existing_env)
        header.addWidget(self.import_existing_btn)
        
        self.refresh_btn = StyledButton("刷新", variant="primary", min_height=36)
        self.refresh_btn.setMinimumWidth(64)
        self.refresh_btn.clicked.connect(lambda: self.load_data(run_gc=True, reload_from_db=True))
        header.addWidget(self.refresh_btn)
        
        layout.addLayout(header)
        
        # 错误提示
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #f87171; padding: 8px;")
        self.error_label.hide()
        layout.addWidget(self.error_label)
        
        self.table = SkyDataTable(schema=self.TABLE_SCHEMA)
        self.table.query_requested.connect(self._on_table_query_requested)
        self.table.row_clicked.connect(self._on_table_row_clicked)
        self.table.row_action_requested.connect(self._on_table_action_requested)
        layout.addWidget(self.table)
        
        # 统计栏
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("color: rgba(255, 255, 255, 0.7);")
        layout.addWidget(self.stats_label)
    
    def load_data(self, run_gc: bool = False, reload_from_db: bool = False):
        """加载环境数据。"""
        if self._load_in_progress:
            self._reload_requested = True
            self._reload_run_gc = self._reload_run_gc or run_gc
            self._reload_from_db = self._reload_from_db or reload_from_db
            return
        self._load_in_progress = True
        self.error_label.hide()
        self._apply_busy_state()
        
        self._loader_thread = DataLoaderThread(self._pool, run_gc=run_gc, reload_from_db=reload_from_db)
        self._loader_thread.finished.connect(self._on_data_loaded)
        self._loader_thread.error.connect(self._on_load_error)
        self._loader_thread.start()
    
    def _on_data_loaded(self, envs: list):
        """数据加载完成。"""
        self._load_in_progress = False
        self._loader_thread = None
        self._apply_busy_state()
        
        ready_count = 0
        busy_count = 0
        
        display_items = []
        for loaded in envs:
            env, env_metadata = self._unpack_loaded_env(loaded)
            status_text = self.STATUS_TEXT.get(env.status, str(env.status.value))
            display_items.append(EnvDisplayItem(
                raw=env,
                display_status_text=str(status_text),
                env_metadata=env_metadata,
                availability=self._build_availability_cell(env_metadata),
            ))
            
            if env.status == EnvStatus.READY:
                ready_count += 1
            elif env.status == EnvStatus.BUSY:
                busy_count += 1
                
        self._display_items = display_items
        self._refresh_table()
        self._update_stats(len(envs), ready_count, busy_count)
        self._run_queued_reload_if_needed()

    def _refresh_table(self) -> None:
        self._table_rows = [self._build_table_row(item) for item in self._display_items]
        self.table.request_refresh()

    def _build_table_row(self, item: EnvDisplayItem) -> dict[str, Any]:
        env = item.raw
        task_text = f"{env.task_run_id[:8]}..." if env.task_run_id else "-"
        return {
            "env": env,
            "env_metadata": item.env_metadata,
            "env_id": str(env.id),
            "id": str(env.id),
            "name": env.name if env.name else "-",
            "kind": env.kind.value,
            "provider": env.provider,
            "status": {
                "text": item.display_status_text,
                "tone": self._status_tone(env.status),
            },
            "availability": item.availability,
            "task": task_text,
            "actions": self._build_row_actions(env),
        }

    def _unpack_loaded_env(self, loaded: Any) -> tuple[Any, dict[str, Any]]:
        if isinstance(loaded, EnvLoadedRecord):
            return loaded.env, dict(loaded.env_metadata)
        if isinstance(loaded, tuple) and len(loaded) == 2:
            env, metadata = loaded
            return env, metadata if isinstance(metadata, dict) else {}
        return loaded, self._load_env_metadata_for_display(loaded)

    def _load_env_metadata_for_display(self, env: Any) -> dict[str, Any]:
        list_metadata = getattr(self._pool, "list_metadata", None)
        if not callable(list_metadata):
            return {}
        try:
            metadata = list_metadata(env.id)
        except Exception:
            return {}
        return metadata if isinstance(metadata, dict) else {}

    def _build_availability_cell(self, env_metadata: dict[str, Any]) -> dict[str, Any]:
        cards = self._resource_pool_cards(env_metadata)
        if not cards:
            return {
                "text": "未标记",
                "tone": "neutral",
                "sort_value": 0,
                "search_text": "未标记 无资源池状态",
                "tooltip": "env_metadata 中没有资源池可用状态",
            }

        total_count = len(cards)
        eligible_count = sum(1 for card in cards if bool(card.get("eligible")))
        if eligible_count == total_count:
            text = f"可用 ({eligible_count}/{total_count})"
            tone = "success"
            sort_value = 3
        elif eligible_count > 0:
            text = f"部分可用 ({eligible_count}/{total_count})"
            tone = "warning"
            sort_value = 2
        else:
            text = f"不可用 (0/{total_count})"
            tone = "danger"
            sort_value = 1

        tooltip_lines = []
        search_parts = [text]
        for card in cards:
            module_name = str(card.get("module_name") or "-")
            pool_name = str(card.get("pool_name") or "-")
            state_text = "可用" if bool(card.get("eligible")) else "不可用"
            reason = str(card.get("reason") or "").strip()
            suffix = f"：{reason}" if reason else ""
            tooltip_lines.append(f"{module_name}/{pool_name}: {state_text}{suffix}")
            search_parts.extend([module_name, pool_name, state_text, reason])

        return {
            "text": text,
            "tone": tone,
            "sort_value": sort_value,
            "search_text": " ".join(part for part in search_parts if part),
            "tooltip": "\n".join(tooltip_lines),
        }

    def _resource_pool_cards(self, env_metadata: dict[str, Any]) -> list[dict[str, Any]]:
        namespace_payload = env_metadata.get(RESOURCE_POOL_METADATA_NAMESPACE)
        if not isinstance(namespace_payload, dict):
            return []
        cards: list[dict[str, Any]] = []
        for value in namespace_payload.values():
            if isinstance(value, dict) and "eligible" in value:
                cards.append(value)
        cards.sort(
            key=lambda card: (
                str(card.get("module_name") or ""),
                str(card.get("pool_name") or ""),
            )
        )
        return cards

    def _build_row_actions(self, env) -> list[dict[str, Any]]:
        if env.status == EnvStatus.READY:
            return [
                {"id": "start", "label": "▶", "tooltip": "运行", "variant": "success"},
                {"id": "pause", "label": "⏸", "tooltip": "暂停", "variant": "warning"},
                {"id": "edit", "label": "✏", "tooltip": "编辑", "variant": "primary"},
                {"id": "destroy", "label": "🗑", "tooltip": "销毁", "variant": "danger"},
            ]
        if env.status in (EnvStatus.RUNNING, EnvStatus.BUSY):
            return [{"id": "stop", "label": "⏹ 停止", "variant": "danger"}]
        if env.status == EnvStatus.PAUSED:
            return [
                {"id": "resume", "label": "▶", "tooltip": "启动", "variant": "success"},
                {"id": "edit", "label": "✏", "tooltip": "编辑", "variant": "primary"},
                {"id": "destroy", "label": "🗑", "tooltip": "销毁", "variant": "danger"},
            ]
        return []

    def _status_tone(self, status: EnvStatus) -> str:
        return {
            EnvStatus.READY: "success",
            EnvStatus.BUSY: "warning",
            EnvStatus.RUNNING: "success",
            EnvStatus.ERROR: "danger",
            EnvStatus.CREATING: "info",
            EnvStatus.PAUSED: "neutral",
            EnvStatus.TERMINATING: "warning",
            EnvStatus.DEAD: "neutral",
        }.get(status, "neutral")

    def _on_table_query_requested(self, request_id: int, query: dict[str, Any]) -> None:
        result = resolve_local_data_table_result(
            self._table_rows,
            columns=self.TABLE_SCHEMA["columns"],
            query=query,
        )
        self.table.apply_result(request_id, result)

    def _on_table_row_clicked(self, row: dict[str, Any]) -> None:
        env_id = str(row.get("env_id") or "")
        if env_id:
            self.env_selected.emit(env_id)

    def _on_table_action_requested(self, action_id: str, row: dict[str, Any]) -> None:
        env_id = str(row.get("env_id") or "")
        if not env_id:
            return
        if action_id == "start":
            self._start_env(env_id)
        elif action_id == "pause":
            self._pause_env(env_id)
        elif action_id == "edit":
            self._edit_env(env_id)
        elif action_id == "destroy":
            self._destroy_env(env_id)
        elif action_id == "stop":
            self._stop_env(env_id)
        elif action_id == "resume":
            self._resume_env(env_id)
    
    def _on_load_error(self, error: str):
        """加载出错。"""
        self._load_in_progress = False
        self._loader_thread = None
        self._apply_busy_state()
        self.error_label.setText(f"❌ 加载失败: {error}")
        self.error_label.show()
        self._run_queued_reload_if_needed()

    def _run_queued_reload_if_needed(self) -> None:
        if not self._reload_requested:
            return
        run_gc = self._reload_run_gc
        reload_from_db = self._reload_from_db
        self._reload_requested = False
        self._reload_run_gc = False
        self._reload_from_db = False
        QTimer.singleShot(0, lambda: self.load_data(run_gc=run_gc, reload_from_db=reload_from_db))

    def _cancel_pending_tasks(self) -> None:
        for task in list(self._pending_tasks):
            if not task.done():
                task.cancel()

    def _track_task(self, coro: Any) -> None:
        try:
            task = asyncio.create_task(coro)
        except RuntimeError:
            close = getattr(coro, "close", None)
            if callable(close):
                close()
            MessageDialog.warning(self, "当前不可用", "当前界面没有可用的异步事件循环，无法执行该操作。")
            return
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _exec_dialog_async(self, dialog: QDialog) -> int:
        return await open_dialog_async(dialog)

    async def _show_message_async(
        self,
        title: str,
        text: str,
        *,
        kind: MessageKind = "info",
    ) -> None:
        await MessageDialog.show_async(self, title, text, kind=kind)

    async def _confirm_async(self, title: str, text: str) -> bool:
        return await ConfirmDialog.confirm_async(self, title, text, confirm_text="确认")

    def _apply_busy_state(self):
        """同步按钮和表格的忙碌状态。"""
        self.create_btn.setEnabled(not self._operation_in_progress)
        self.import_existing_btn.setEnabled(not self._operation_in_progress)
        self.refresh_btn.setEnabled(not self._load_in_progress and not self._operation_in_progress)
        self.table.set_loading(self._load_in_progress)
        if not self._load_in_progress:
            self.table.setEnabled(not self._operation_in_progress)

    def _begin_operation(self, message: str = "正在处理环境操作...") -> bool:
        if self._operation_in_progress:
            return False
        self._operation_in_progress = True
        self._show_loading(True, message)
        self._apply_busy_state()
        return True

    def _end_operation(self):
        self._operation_in_progress = False
        self._operation_task = None
        self._show_loading(False)
        self._apply_busy_state()

    def _schedule_operation(self, coro: Any, *, message: str = "正在处理环境操作...") -> bool:
        if not self._begin_operation(message):
            close = getattr(coro, "close", None)
            if callable(close):
                close()
            return False
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._end_operation()
            MessageDialog.error(self, "错误", "当前 UI 异步事件循环未启动，无法执行环境操作。")
            close = getattr(coro, "close", None)
            if callable(close):
                close()
            return False
        self._operation_task = loop.create_task(self._run_operation(coro))
        self._pending_tasks.add(self._operation_task)
        self._operation_task.add_done_callback(self._pending_tasks.discard)
        return True

    async def _run_operation(self, coro: Any):
        try:
            await coro
        finally:
            self._end_operation()

    async def _async_create_env(self, provider: str, config: dict[str, Any], requirement: Any):
        try:
            env = await self._manager.create_env(
                provider_name=provider,
                config=config,
                requirement=requirement,
            )
        except Exception as exc:
            await self._show_operation_error(str(exc))
            return
        self._on_create_finished(env)

    async def _async_import_existing_env_and_run(
        self,
        *,
        provider_name: str,
        env_names: list[str],
        job_id: str,
    ) -> None:
        try:
            await self._import_job_service.import_and_run_with_job(
                provider_name=provider_name,
                env_names=env_names,
                job_id=job_id,
            )
        except Exception as exc:
            await self._show_operation_error(str(exc))
            return
        self.load_data()

    async def _async_destroy_env(self, env_id: str):
        try:
            success = await self._manager.destroy_env(env_id)
        except Exception as exc:
            await self._show_operation_error(str(exc))
            return
        await self._on_destroy_finished(success)

    async def _async_env_action(self, env_id: str, action: str):
        operation = getattr(self._manager, f"{action}_env")
        try:
            success = await operation(env_id)
        except Exception as exc:
            await self._show_operation_error(str(exc))
            return
        await self._on_action_finished(success, action=action)
    
    def _create_env(self):
        """创建环境。"""
        self._track_task(self._create_env_async())

    async def _create_env_async(self) -> None:
        """创建环境。"""
        dialog = CreateEnvDialog(self)
        if await self._exec_dialog_async(dialog) != int(QDialog.DialogCode.Accepted):
            return
        kind, provider, config = dialog.get_values()

        # Construct EnvRequirement to pass proxy_config correctly
        from src.core.rem.models import EnvRequirement, ProxyConfig

        requirement = EnvRequirement(kind=kind)
        if "proxy" in config:
            requirement.proxy_config = ProxyConfig.from_dict(config["proxy"])

        self._schedule_operation(
            self._async_create_env(provider, config, requirement),
            message=self._operation_message("create", provider=provider),
        )

    def _import_existing_env(self):
        """从来源系统导入已有环境。"""
        self._track_task(self._import_existing_env_async())

    async def _import_existing_env_async(self) -> None:
        sources = self._manager.list_existing_env_import_sources()
        if not sources:
            await self._show_message_async(
                "当前不可用",
                "当前没有可用的来源环境导入入口。",
                kind="warning",
            )
            return

        from src.core.atm.models import JobType, TriggerType
        from src.core.atm.service import get_task_service
        from src.core.mms.registry import get_module_registry

        registry = get_module_registry()
        modules = registry.get_enabled_modules()
        if not modules:
            await self._show_message_async(
                "当前不可用",
                "当前没有可用的已安装模块，无法执行导入后的 workflow。",
                kind="warning",
            )
            return

        service = get_task_service()
        jobs = [
            job
            for job in await service.list_jobs()
            if job.type == JobType.BATCH and job.trigger.type == TriggerType.MANUAL
        ]
        if not jobs:
            await self._show_message_async(
                "当前不可用",
                "请先在任务监控中创建一个“执行一次”的批次任务，再导入环境并关联执行。",
                kind="warning",
            )
            return

        env_options_by_source: dict[str, list[Any]] = {}
        if not self._begin_operation(self._operation_message("list_sources")):
            return
        list_error = ""
        try:
            for item in sources:
                provider_name = str(item["provider"])
                env_options_by_source[provider_name] = (
                    await self._manager.list_unsynced_provider_envs(provider_name)
                )
        except Exception as exc:
            list_error = str(exc)
        finally:
            self._end_operation()
        if list_error:
            await self._show_operation_error(list_error)
            return

        dialog = ImportExistingEnvDialog(
            sources=sources,
            modules=modules,
            jobs=jobs,
            env_options_by_source=env_options_by_source,
            parent=self,
        )
        if await self._exec_dialog_async(dialog) != int(QDialog.DialogCode.Accepted):
            return

        values = dialog.get_values()
        self._schedule_operation(
            self._async_import_existing_env_and_run(
                provider_name=values["provider"],
                env_names=values["names"],
                job_id=values["job_id"],
            ),
            message=self._operation_message("import", provider=values["provider"]),
        )
    
    def _on_create_finished(self, env):
        """创建完成。"""
        del env
        self.load_data()
    
    async def _show_operation_error(self, error: str):
        """工作线程出错。"""
        await self._show_message_async("错误", f"操作失败: {error}", kind="error")
    
    def _destroy_env(self, env_id: str):
        """销毁环境。"""
        self._track_task(self._confirm_destroy_env_async(env_id))

    async def _confirm_destroy_env_async(self, env_id: str) -> None:
        confirmed = await self._confirm_async("确认", f"确定要销毁环境 {env_id} ?")
        if confirmed:
            self._schedule_operation(
                self._async_destroy_env(env_id),
                message=self._operation_message(
                    "destroy",
                    provider=self._env_provider_for_message(env_id),
                    env_id=env_id,
                ),
            )
    
    async def _on_destroy_finished(self, success: bool):
        """销毁完成。"""
        if success:
            await self._show_message_async("成功", "环境已销毁", kind="info")
        else:
            reason = str(getattr(self._manager, "last_destroy_error", "") or "").strip()
            message = "环境销毁失败，数据库记录已保留。请检查指纹浏览器连接后重试。"
            if reason:
                message = f"环境销毁失败，数据库记录已保留。\n原因：{reason}"
            await self._show_message_async(
                "警告",
                message,
                kind="warning",
            )
        self.load_data()
    
    def _start_env(self, env_id: str):
        """启动环境（打开窗口）。"""
        self._schedule_operation(
            self._async_env_action(env_id, "start"),
            message=self._operation_message(
                "start",
                provider=self._env_provider_for_message(env_id),
                env_id=env_id,
            ),
        )
    
    def _stop_env(self, env_id: str):
        """停止环境（关闭窗口）。"""
        self._schedule_operation(
            self._async_env_action(env_id, "stop"),
            message=self._operation_message("stop", env_id=env_id),
        )
    
    def _pause_env(self, env_id: str):
        """暂停环境。"""
        self._schedule_operation(
            self._async_env_action(env_id, "pause"),
            message=self._operation_message("pause", env_id=env_id),
        )
    
    def _resume_env(self, env_id: str):
        """恢复环境。"""
        self._schedule_operation(
            self._async_env_action(env_id, "resume"),
            message=self._operation_message("resume", env_id=env_id),
        )
    
    def _edit_env(self, env_id: str):
        """编辑环境（弹出对话框）。"""
        self._track_task(self._edit_env_async(env_id))

    async def _edit_env_async(self, env_id: str) -> None:
        """编辑环境（弹出对话框）。"""
        from src.core.rem.ui.edit_env_dialog import EditEnvDialog
        
        env = next((item.raw for item in self._display_items if str(item.raw.id) == env_id), None)
        
        if not env:
            # 如果找不到，从 pool 异步加载
            await self._show_message_async(
                "错误",
                f"未找到环境: {env_id}...",
                kind="warning",
            )
            return
        
        dialog = EditEnvDialog(env, self)
        if await self._exec_dialog_async(dialog) == int(QDialog.DialogCode.Accepted):
            self.load_data()  # 刷新列表
    
    async def _on_action_finished(self, success: bool, *, action: str):
        """通用操作完成回调。
        
        注意: 失败时错误信息由 Shell 通过 Toast 显示，
        详见 ENV_OPERATION_FAILED 事件处理。
        """
        if not success:
            await self._show_message_async(
                "操作失败",
                f"{action} 环境失败，请稍后重试。",
                kind="warning",
            )
            return
        self.load_data()
    
    def _env_provider_for_message(self, env_id: str) -> str:
        env = next((item.raw for item in self._display_items if str(item.raw.id) == env_id), None)
        return str(getattr(env, "provider", "") or "")

    def _operation_message(self, action: str, *, provider: str = "", env_id: str = "") -> str:
        action_text = {
            "create": "创建",
            "destroy": "销毁",
            "start": "启动",
            "stop": "停止",
            "pause": "暂停",
            "resume": "恢复",
            "import": "导入",
            "list_sources": "读取来源",
        }.get(action, "处理")
        env_text = f" {env_id}" if env_id else ""
        provider_label = {
            "virtualbrowser": "VirtualBrowser",
            "bitbrowser": "BitBrowser",
        }.get(provider, provider)

        if provider in CreateEnvDialog.FINGERPRINT_PROVIDERS:
            return f"正在检查 {provider_label} API 并{action_text}环境{env_text}，最长约 30 秒..."
        if action == "list_sources":
            return "正在读取来源环境列表..."
        return f"正在{action_text}环境{env_text}..."

    def _show_loading(self, show: bool, message: str = ""):
        if show:
            if self._progress_dialog is None:
                self._progress_dialog = ProgressDialog.open_progress(
                    self,
                    "环境操作中",
                    message or "正在处理环境操作...",
                )
                self._progress_dialog.finished.connect(
                    lambda *_args, dialog=self._progress_dialog: self._forget_progress_dialog(dialog)
                )
            else:
                self._progress_dialog.set_message(message or "正在处理环境操作...")
        else:
            self._close_progress_dialog()

    def _forget_progress_dialog(self, dialog: ProgressDialog) -> None:
        if self._progress_dialog is dialog:
            self._progress_dialog = None

    def _close_progress_dialog(self) -> None:
        if self._progress_dialog is None:
            return
        dialog = self._progress_dialog
        self._progress_dialog = None
        dialog.close_progress()

    def _update_stats(self, total: int, ready: int, busy: int):
        self.stats_label.setText(f"总计: {total} | 就绪: {ready} | 忙碌: {busy}")

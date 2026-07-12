"""环境列表组件。

显示所有运行环境及其状态，支持创建/销毁操作。
"""

import asyncio
import textwrap
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

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
from src.core.rem.fingerprint_validation import (
    FINGERPRINT_VALIDATION_NAMESPACE,
    FINGERPRINT_VALIDATION_PASSED,
    fingerprint_validation_from_metadata,
)
from src.core.rem.import_job_service import get_existing_env_import_job_service
from src.core.rem import EnvKind, EnvStatus
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

            # 2. VirtualBrowser 在创建时下发完整随机指纹，避免落到厂商的精简默认模板。
            if provider == "virtualbrowser":
                from src.core.rem.virtualbrowser_fingerprint import VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY

                config["creation_params"] = {
                    "virtualbrowser": {VIRTUALBROWSER_RANDOMIZE_FINGERPRINT_KEY: True}
                }
        
        return (
            self.kind_combo.currentData(),
            provider,
            config,
        )


class CleanupPreviewDialog(QDialog):
    """批量清理确认弹窗。"""

    TABLE_SCHEMA = {
        "columns": [
            {"key": "__index__", "label": "#", "type": "int", "width": 56, "align": "center"},
            {"key": "env_id", "label": "环境ID", "type": "int", "width": 84, "align": "center", "sortable": True},
            {"key": "env_name", "label": "环境名", "type": "text", "stretch": True},
            {"key": "provider", "label": "Provider", "type": "text", "width": 150},
            {"key": "sources", "label": "来源", "type": "text", "width": 240},
        ],
        "row_height": 72,
        "selection_mode": "none",
        "features": {
            "search": {"enabled": True, "placeholder": "搜索环境ID / 环境名 / 来源…"},
            "sort": {"enabled": True, "default": [{"field": "env_id", "direction": "asc"}]},
            "pagination": {"enabled": True, "page_size": 10, "page_size_options": [10, 20, 50]},
            "loading": {"inline": False, "disable_interaction": False},
        },
    }

    def __init__(
        self,
        *,
        eligible_items: list[Any],
        skipped_count: int,
        error_count: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._eligible_items = list(eligible_items)
        self._skipped_count = max(0, int(skipped_count))
        self._error_count = max(0, int(error_count))
        self.setWindowTitle("确认批量清理")
        self.setModal(True)
        self.setMinimumSize(980, 560)
        configure_titled_dialog(self)
        self.setStyleSheet(self._build_stylesheet())
        self._setup_ui()

    @staticmethod
    def _build_stylesheet() -> str:
        return """
            QDialog {
                background-color: #1e1e2e;
            }
            QLabel {
                background-color: transparent;
            }
            QLabel#cleanupConfirmTitle {
                color: #f7f7fb;
                font-size: 18px;
                font-weight: 800;
            }
            QLabel#cleanupConfirmSummary {
                color: rgba(255, 255, 255, 0.78);
                font-size: 14px;
                line-height: 1.45;
            }
            QLabel#cleanupConfirmHint {
                color: rgba(255, 255, 255, 0.56);
                font-size: 12px;
                line-height: 1.5;
            }
        """

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title_label = QLabel("确认批量清理")
        title_label.setObjectName("cleanupConfirmTitle")
        layout.addWidget(title_label)

        summary_label = QLabel(self._build_summary_text())
        summary_label.setObjectName("cleanupConfirmSummary")
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        hint_label = QLabel("下表只展示当前通过安全校验、实际会被删除的环境。")
        if self._error_count > 0:
            hint_label.setText(
                f"{hint_label.text()} 另有 {self._error_count} 个来源扫描失败，本次未纳入删除。"
            )
        hint_label.setObjectName("cleanupConfirmHint")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        self.preview_table = SkyDataTable(schema=self.TABLE_SCHEMA)
        self.preview_table.set_query(
            {
                "search_text": "",
                "sort": [{"field": "env_id", "direction": "asc"}],
                "page": 1,
                "page_size": 10,
                "params": {},
            }
        )
        rows = self._build_rows()
        result = resolve_local_data_table_result(
            rows,
            columns=list(self.TABLE_SCHEMA["columns"]),
            query=dict(self.preview_table._query),
        )
        self.preview_table.apply_result(0, result)
        self.preview_table.table.resizeRowsToContents()
        layout.addWidget(self.preview_table)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addStretch()

        cancel_btn = StyledButton(
            "取消",
            variant="secondary",
            min_height=40,
            min_width=96,
            horizontal_padding=20,
        )
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        confirm_btn = StyledButton(
            "确认",
            variant="success",
            min_height=40,
            min_width=96,
            horizontal_padding=20,
        )
        confirm_btn.clicked.connect(self.accept)
        buttons.addWidget(confirm_btn)

        layout.addLayout(buttons)

    def _build_summary_text(self) -> str:
        summary = f"将删除 {len(self._eligible_items)} 个环境，跳过 {self._skipped_count} 个不安全候选。"
        if self._error_count > 0:
            summary = f"{summary} 扫描失败来源 {self._error_count} 个。"
        return summary

    def _build_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, item in enumerate(self._eligible_items, start=1):
            env_name = str(item.env_name or "-").strip() or "-"
            provider = self._provider_label(str(item.provider or "-").strip() or "-")
            source_lines = [f"{source.module_name}.{source.cleanup_name}" for source in item.sources]
            source_text = "\n".join(source_lines) if source_lines else "-"
            rows.append(
                {
                    "__index__": index,
                    "env_id": item.env_id,
                    "env_name": self._wrapped_cell(env_name, width=42),
                    "provider": {"text": provider, "tooltip": str(item.provider or "")},
                    "sources": self._wrapped_cell(source_text, width=28),
                }
            )
        return rows

    def _wrapped_cell(self, text: str, *, width: int) -> dict[str, Any]:
        value = str(text or "-").strip() or "-"
        wrapped = self._wrap_text(value, width=width)
        return {
            "text": wrapped,
            "search_text": value.replace("\n", " "),
            "sort_value": value,
            "tooltip": value,
        }

    @staticmethod
    def _wrap_text(text: str, *, width: int) -> str:
        lines = []
        for raw_line in str(text or "").splitlines() or ["-"]:
            wrapped = textwrap.wrap(
                raw_line,
                width=width,
                break_long_words=False,
                break_on_hyphens=True,
            )
            lines.extend(wrapped or [raw_line])
        return "\n".join(lines)

    @staticmethod
    def _provider_label(provider: str) -> str:
        labels = {
            "bitbrowser": "BitBrowser",
            "playwright_local": "Playwright Local",
            "virtualbrowser": "VirtualBrowser",
        }
        return labels.get(provider, provider or "-")


class SourceProxySyncPreviewDialog(QDialog):
    """来源代理同步确认弹窗。"""

    TABLE_SCHEMA = {
        "columns": [
            {"key": "__index__", "label": "#", "type": "int", "width": 56, "align": "center"},
            {"key": "env_id", "label": "环境ID", "type": "int", "width": 84, "align": "center", "sortable": True},
            {"key": "env_name", "label": "环境名", "type": "text", "width": 180, "sortable": True},
            {"key": "provider", "label": "Provider", "type": "text", "width": 130},
            {"key": "source_proxy", "label": "来源代理", "type": "text", "width": 240, "searchable": True},
            {"key": "action", "label": "动作", "type": "text", "width": 120, "searchable": True},
            {"key": "reason", "label": "说明", "type": "text", "stretch": True, "searchable": True},
        ],
        "row_height": 72,
        "selection_mode": "none",
        "features": {
            "search": {"enabled": True, "placeholder": "搜索环境、来源代理或动作…"},
            "sort": {"enabled": True, "default": [{"field": "env_id", "direction": "asc"}]},
            "pagination": {"enabled": True, "page_size": 10, "page_size_options": [10, 20, 50]},
            "loading": {"inline": False, "disable_interaction": False},
        },
    }

    ACTION_LABELS = {
        "bind_ip_entry": "绑定 IP 条目",
        "clear_ip_binding": "清除本地绑定",
        "skip": "跳过",
    }

    def __init__(self, plan: Any, parent=None) -> None:
        super().__init__(parent)
        self._plan = plan
        self.setWindowTitle("确认同步来源代理")
        self.setModal(True)
        self.setMinimumSize(1100, 560)
        configure_titled_dialog(self)
        self.setStyleSheet(self._build_stylesheet())
        self._setup_ui()

    @staticmethod
    def _build_stylesheet() -> str:
        return """
            QDialog {
                background-color: #1e1e2e;
            }
            QLabel {
                background-color: transparent;
            }
            QLabel#sourceProxySyncTitle {
                color: #f7f7fb;
                font-size: 18px;
                font-weight: 800;
            }
            QLabel#sourceProxySyncSummary {
                color: rgba(255, 255, 255, 0.78);
                font-size: 14px;
                line-height: 1.45;
            }
            QLabel#sourceProxySyncHint {
                color: rgba(255, 255, 255, 0.56);
                font-size: 12px;
                line-height: 1.5;
            }
        """

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title_label = QLabel("确认同步来源代理")
        title_label.setObjectName("sourceProxySyncTitle")
        layout.addWidget(title_label)

        summary_label = QLabel(self._build_summary_text())
        summary_label.setObjectName("sourceProxySyncSummary")
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        hint_label = QLabel("只会更新本地环境记录，不会修改外部指纹浏览器的代理配置。")
        hint_label.setObjectName("sourceProxySyncHint")
        hint_label.setWordWrap(True)
        layout.addWidget(hint_label)

        self.preview_table = SkyDataTable(schema=self.TABLE_SCHEMA)
        self.preview_table.set_query(
            {
                "search_text": "",
                "sort": [{"field": "env_id", "direction": "asc"}],
                "page": 1,
                "page_size": 10,
                "params": {},
            }
        )
        rows = self._build_rows()
        result = resolve_local_data_table_result(
            rows,
            columns=list(self.TABLE_SCHEMA["columns"]),
            query=dict(self.preview_table._query),
        )
        self.preview_table.apply_result(0, result)
        self.preview_table.table.resizeRowsToContents()
        layout.addWidget(self.preview_table)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addStretch()

        cancel_btn = StyledButton("取消", variant="secondary", min_height=40, min_width=96, horizontal_padding=20)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        confirm_btn = StyledButton("同步", variant="success", min_height=40, min_width=96, horizontal_padding=20)
        confirm_btn.clicked.connect(self.accept)
        buttons.addWidget(confirm_btn)
        layout.addLayout(buttons)

    def _build_summary_text(self) -> str:
        items = list(getattr(self._plan, "items", []) or [])
        actionable = int(getattr(self._plan, "actionable_count", 0) or 0)
        skipped = max(0, len(items) - actionable)
        errors = len(getattr(self._plan, "errors", []) or [])
        summary = f"将同步 {actionable} 个环境，跳过 {skipped} 个环境。"
        if errors:
            summary = f"{summary} 扫描失败 {errors} 个。"
        return summary

    def _build_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for index, item in enumerate(getattr(self._plan, "items", []) or [], start=1):
            action = str(getattr(item, "action", "") or "skip")
            rows.append(
                {
                    "__index__": index,
                    "env_id": int(getattr(item, "env_id", 0) or 0),
                    "env_name": str(getattr(item, "env_name", "") or "-"),
                    "provider": str(getattr(item, "provider", "") or "-"),
                    "source_proxy": str(getattr(item, "source_proxy_url", "") or "-"),
                    "action": {
                        "text": self.ACTION_LABELS.get(action, action),
                        "tone": "info" if bool(getattr(item, "eligible", False)) else "neutral",
                    },
                    "reason": str(getattr(item, "reason", "") or "-"),
                }
            )
        return rows


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


def _format_bound_ip_cell(proxy_config: Any) -> dict[str, Any]:
    """Build the environment table cell for the currently bound proxy IP."""
    mode = _proxy_mode_value(proxy_config)
    if not proxy_config or mode == "none":
        return {
            "text": "-",
            "search_text": "",
            "sort_value": "",
            "tooltip": "未绑定代理 IP",
            "tone": "neutral",
        }
    if mode == "system":
        return {
            "text": "-",
            "search_text": "",
            "sort_value": "",
            "tooltip": "系统代理未关联 IP 表条目",
            "tone": "neutral",
        }
    ip_entry_id = str(getattr(proxy_config, "ip_entry_id", "") or "").strip()
    if not ip_entry_id:
        return {
            "text": "-",
            "search_text": "",
            "sort_value": "",
            "tooltip": "未绑定 IP 表条目",
            "tone": "neutral",
        }

    static_value = str(getattr(proxy_config, "static_value", "") or "").strip()
    current_ip = str(getattr(proxy_config, "current_ip", "") or "").strip()
    parsed = _parse_proxy_value(static_value)
    host = parsed["host"] or current_ip
    port = parsed["port"]
    display_text = _build_bound_ip_text(host, port)
    if not display_text:
        display_text = "-"

    tooltip_lines = [f"代理模式: {_proxy_mode_label(mode)}"]
    if display_text != "-":
        tooltip_lines.append(f"绑定 IP: {display_text}")
    if parsed["protocol"]:
        tooltip_lines.append(f"协议: {parsed['protocol']}")
    if parsed["username"]:
        tooltip_lines.append(f"用户名: {parsed['username']}")
    tooltip_lines.append(f"IP 条目: {ip_entry_id}")
    pool_id = str(getattr(proxy_config, "pool_id", "") or "").strip()
    if pool_id:
        tooltip_lines.append(f"IP 池: {pool_id}")
    sanitized_proxy = _sanitize_proxy_value(static_value)
    if sanitized_proxy:
        tooltip_lines.append(f"代理地址: {sanitized_proxy}")

    search_parts = [
        mode,
        _proxy_mode_label(mode),
        host,
        str(port or ""),
        parsed["protocol"],
        parsed["username"],
        ip_entry_id,
        pool_id,
        sanitized_proxy,
    ]
    return {
        "text": display_text,
        "search_text": " ".join(part for part in search_parts if part),
        "sort_value": display_text if display_text != "-" else "",
        "tooltip": "\n".join(tooltip_lines),
        "tone": "info" if display_text != "-" else "neutral",
    }


def _format_fingerprint_validation_cell(env_metadata: dict[str, Any]) -> dict[str, Any]:
    metadata = env_metadata.get(FINGERPRINT_VALIDATION_NAMESPACE, {})
    summary = fingerprint_validation_from_metadata(metadata)
    if summary.is_risk:
        reason = summary.reason or "指纹风险"
        tooltip = summary.detail or reason
        if summary.last_checked_at:
            tooltip = f"{tooltip}\n检测时间: {summary.last_checked_at}"
        return {
            "text": f"风险: {reason}",
            "search_text": f"风险 {reason} {summary.detail}",
            "sort_value": f"risk:{reason}",
            "tooltip": tooltip,
            "tone": "danger",
        }
    if summary.status == FINGERPRINT_VALIDATION_PASSED:
        tooltip = summary.detail or "最近一次指纹风险重新检测通过"
        if summary.last_checked_at:
            tooltip = f"{tooltip}\n检测时间: {summary.last_checked_at}"
        return {
            "text": "通过",
            "search_text": "通过",
            "sort_value": "passed",
            "tooltip": tooltip,
            "tone": "success",
        }
    return {
        "text": "-",
        "search_text": "",
        "sort_value": "",
        "tooltip": "未进行风险检测",
        "tone": "neutral",
    }


def _is_location_fingerprint_risk(validation: Any) -> bool:
    text = f"{getattr(validation, 'reason', '')} {getattr(validation, 'detail', '')}".lower()
    return "location" in text


def _proxy_mode_value(proxy_config: Any) -> str:
    if proxy_config is None:
        return "none"
    mode = getattr(proxy_config, "mode", "")
    return str(getattr(mode, "value", mode) or "").strip().lower()


def _proxy_mode_label(mode: str) -> str:
    return {
        "pool": "IP 池",
        "static": "静态代理",
        "system": "系统代理",
        "none": "无代理",
    }.get(mode, mode or "未知")


def _parse_proxy_value(value: str) -> dict[str, Any]:
    if not value:
        return {"protocol": "", "host": "", "port": 0, "username": ""}
    if "://" in value:
        parsed = urlsplit(value)
        try:
            port = int(parsed.port or 0)
        except ValueError:
            port = 0
        return {
            "protocol": str(parsed.scheme or "").lower(),
            "host": str(parsed.hostname or ""),
            "port": port,
            "username": str(parsed.username or ""),
        }

    host_port = value.rsplit("@", 1)[-1]
    if ":" not in host_port:
        return {"protocol": "", "host": host_port.strip(), "port": 0, "username": ""}
    host, port_text = host_port.rsplit(":", 1)
    try:
        port = int(port_text)
    except ValueError:
        port = 0
    return {"protocol": "", "host": host.strip(), "port": port, "username": ""}


def _build_bound_ip_text(host: str, port: int) -> str:
    host = str(host or "").strip()
    if not host:
        return ""
    return f"{host}:{port}" if port else host


def _sanitize_proxy_value(value: str) -> str:
    if not value:
        return ""
    if "://" not in value:
        return value.rsplit("@", 1)[-1]
    parsed = urlsplit(value)
    protocol = str(parsed.scheme or "").lower()
    host = str(parsed.hostname or "")
    if not protocol or not host:
        return value.rsplit("@", 1)[-1]
    try:
        parsed_port = int(parsed.port or 0)
    except ValueError:
        parsed_port = 0
    port = f":{parsed_port}" if parsed_port else ""
    username = str(parsed.username or "")
    auth = f"{username}:***@" if username else ""
    return f"{protocol}://{auth}{host}{port}"


class EnvListWidget(QWidget):
    """环境列表组件。"""
    
    env_selected = pyqtSignal(str)
    TABLE_SCHEMA = {
        "columns": [
            {"key": "id", "label": "ID", "type": "text", "width": 120},
            {"key": "name", "label": "名称", "type": "text", "width": 160, "sortable": True},
            {"key": "provider", "label": "节点类型", "type": "text", "width": 110},
            {"key": "created_at", "label": "创建时间", "type": "text", "width": 150, "sortable": True},
            {"key": "bound_ip", "label": "绑定 IP", "type": "text", "width": 180, "sortable": True, "searchable": True},
            {"key": "fingerprint_validation", "label": "风险", "type": "text", "width": 100, "searchable": True},
            {"key": "status", "label": "状态", "type": "text", "width": 90},
            {"key": "task", "label": "任务", "type": "text", "width": 90},
            {"key": "actions", "label": "操作", "type": "actions", "stretch": True},
        ],
        "features": {
            "search": {"enabled": True, "placeholder": "搜索环境、Provider、绑定 IP 或任务"},
            "sort": {
                "enabled": True,
                "default": [{"field": "name", "direction": "asc"}],
            },
            "pagination": {"enabled": True, "page_size": 20, "page_size_options": [10, 20, 50, 100]},
        },
    }
    
    COLUMNS = ["ID", "名称", "节点类型", "创建时间", "绑定 IP", "风险", "状态", "任务", "操作"]
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
        from src.core.rem.cleanup_service import get_env_cleanup_service

        self._cleanup_service = get_env_cleanup_service()
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

        self.sync_proxy_btn = StyledButton("同步来源代理", variant="primary", min_height=36)
        self.sync_proxy_btn.clicked.connect(self._sync_source_proxies)
        header.addWidget(self.sync_proxy_btn)

        self.cleanup_btn = StyledButton("清理环境", variant="danger", min_height=36)
        self.cleanup_btn.clicked.connect(self._cleanup_envs)
        header.addWidget(self.cleanup_btn)

        self.refresh_btn = StyledButton("刷新", variant="primary", min_height=36)
        self.refresh_btn.setMinimumWidth(64)
        self.refresh_btn.clicked.connect(lambda: self.load_data(run_gc=False, reload_from_db=True))
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
            "provider": env.provider,
            "created_at": datetime.fromtimestamp(int(env.created_at)).strftime("%Y-%m-%d %H:%M"),
            "bound_ip": _format_bound_ip_cell(getattr(env, "proxy_config", None)),
            "fingerprint_validation": _format_fingerprint_validation_cell(item.env_metadata),
            "status": {
                "text": item.display_status_text,
                "tone": self._status_tone(env.status),
            },
            "task": task_text,
            "actions": self._build_row_actions(env, item.env_metadata),
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

    def _build_row_actions(self, env, env_metadata: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        validation = fingerprint_validation_from_metadata(
            (env_metadata or {}).get(FINGERPRINT_VALIDATION_NAMESPACE, {})
        )
        recheck_action = {
            "id": "recheck_fingerprint",
            "label": "↻",
            "tooltip": "重新检测指纹风险",
            "variant": "warning",
        }
        repair_location_action = {
            "id": "repair_location",
            "label": "📍",
            "tooltip": "按 ip-api 原地修复 location",
            "variant": "primary",
        }
        if env.status == EnvStatus.READY:
            actions = []
            if validation.is_risk:
                if env.provider == "virtualbrowser" and _is_location_fingerprint_risk(validation):
                    actions.append(repair_location_action)
                actions.append(recheck_action)
            else:
                actions.append({"id": "start", "label": "▶", "tooltip": "运行", "variant": "success"})
            actions.extend([
                {"id": "pause", "label": "⏸", "tooltip": "暂停", "variant": "warning"},
                {"id": "edit", "label": "✏", "tooltip": "编辑", "variant": "primary"},
                {"id": "destroy", "label": "🗑", "tooltip": "销毁", "variant": "danger"},
            ])
            return actions
        if env.status in (EnvStatus.RUNNING, EnvStatus.BUSY):
            return [{"id": "stop", "label": "⏹ 停止", "variant": "danger"}]
        if env.status == EnvStatus.PAUSED:
            actions = []
            if validation.is_risk:
                if env.provider == "virtualbrowser" and _is_location_fingerprint_risk(validation):
                    actions.append(repair_location_action)
                actions.append(recheck_action)
            actions.extend([
                {"id": "resume", "label": "▶", "tooltip": "启动", "variant": "success"},
                {"id": "edit", "label": "✏", "tooltip": "编辑", "variant": "primary"},
                {"id": "destroy", "label": "🗑", "tooltip": "销毁", "variant": "danger"},
            ])
            return actions
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
        elif action_id == "repair_location":
            self._repair_fingerprint_location(env_id)
        elif action_id == "recheck_fingerprint":
            self._recheck_fingerprint_validation(env_id)
    
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

    async def _confirm_cleanup_plan_async(self, plan: Any) -> bool:
        eligible_items = [item for item in plan.items if item.eligible]
        dialog = CleanupPreviewDialog(
            eligible_items=eligible_items,
            skipped_count=len(plan.items) - len(eligible_items),
            error_count=len(plan.errors),
            parent=self,
        )
        return await self._exec_dialog_async(dialog) == int(QDialog.DialogCode.Accepted)

    async def _confirm_source_proxy_sync_plan_async(self, plan: Any) -> bool:
        dialog = SourceProxySyncPreviewDialog(plan, parent=self)
        return await self._exec_dialog_async(dialog) == int(QDialog.DialogCode.Accepted)

    def _apply_busy_state(self):
        """同步按钮和表格的忙碌状态。"""
        self.create_btn.setEnabled(not self._operation_in_progress)
        self.import_existing_btn.setEnabled(not self._operation_in_progress)
        self.sync_proxy_btn.setEnabled(not self._operation_in_progress)
        self.cleanup_btn.setEnabled(not self._operation_in_progress)
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

    async def _async_cleanup_envs(self):
        try:
            result = await self._cleanup_service.cleanup()
        except Exception as exc:
            await self._show_operation_error(str(exc))
            return

        message = (
            f"批量清理完成：删除 {result.deleted_count} 个，"
            f"跳过 {result.skipped_count} 个，失败 {result.failed_count} 个。"
        )
        failed = [item for item in result.items if item.outcome == "failed"]
        if failed:
            details = "\n".join(f"- {item.env_id}: {item.reason}" for item in failed[:8])
            message = f"{message}\n{details}"
        if result.errors:
            message = f"{message}\n扫描失败来源：{len(result.errors)} 个"
        await self._show_message_async("批量清理", message, kind="info" if result.failed_count == 0 else "warning")
        self.load_data(run_gc=False, reload_from_db=True)

    async def _async_sync_source_proxies(self, plan: Any):
        try:
            result = await self._manager.sync_source_proxies(plan)
        except Exception as exc:
            await self._show_operation_error(str(exc))
            return

        message = (
            f"来源代理同步完成：更新 {result.updated_count} 个，"
            f"绑定 IP 条目 {result.bound_count} 个，清除本地绑定 {getattr(result, 'cleared_count', 0)} 个，"
            f"跳过 {result.skipped_count} 个，失败 {result.failed_count} 个。"
        )
        if getattr(result, "errors", None):
            details = "\n".join(f"- {error}" for error in list(result.errors)[:8])
            message = f"{message}\n{details}"
        await self._show_message_async(
            "同步来源代理",
            message,
            kind="info" if result.failed_count == 0 else "warning",
        )
        self.load_data(run_gc=False, reload_from_db=True)

    async def _async_recheck_fingerprint_validation(self, env_id: str) -> None:
        try:
            summary = await self._manager.recheck_env_fingerprint_validation(env_id)
        except Exception as exc:
            await self._show_operation_error(str(exc))
            return
        if summary.is_risk:
            message = summary.detail or summary.reason or "重新检测后仍存在风险。"
            await self._show_message_async("重新检测", f"环境仍为风险状态。\n{message}", kind="warning")
        else:
            await self._show_message_async("重新检测", "环境指纹风险检测通过。", kind="info")
        self.load_data(run_gc=False, reload_from_db=True)

    async def _async_repair_fingerprint_location(self, env_id: str) -> None:
        try:
            summary = await self._manager.repair_env_fingerprint_location(env_id)
        except Exception as exc:
            await self._show_operation_error(str(exc))
            return
        if summary.is_risk:
            message = summary.detail or summary.reason or "修复后仍存在风险。"
            await self._show_message_async("修复位置", f"location 已更新，但环境仍为风险状态。\n{message}", kind="warning")
        else:
            await self._show_message_async("修复位置", "location 已按 ip-api 更新，风险检测通过。", kind="info")
        self.load_data(run_gc=False, reload_from_db=True)

    async def _async_env_operation(self, env_id: str, action: str):
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

    def _cleanup_envs(self):
        """清理宿主扫描出的孤岛、未认领和模块声明可清理环境。"""
        self._track_task(self._cleanup_envs_async())

    def _sync_source_proxies(self):
        """同步外部指纹浏览器来源代理到本地环境记录。"""
        self._track_task(self._sync_source_proxies_async())

    async def _cleanup_envs_async(self) -> None:
        if not self._begin_operation("正在扫描可清理环境..."):
            return
        try:
            plan = await self._cleanup_service.preview()
        except Exception as exc:
            self._end_operation()
            await self._show_operation_error(str(exc))
            return
        self._end_operation()

        if not plan.items:
            message = "暂无可清理环境。"
            if plan.errors:
                message = f"{message}\n扫描失败来源：{len(plan.errors)} 个"
            await self._show_message_async("批量清理", message, kind="warning" if plan.errors else "info")
            return

        eligible_items = [item for item in plan.items if item.eligible]
        if not eligible_items:
            reason_lines = [
                f"- {item.env_id}: {item.reason}"
                for item in plan.items[:8]
                if str(getattr(item, "reason", "") or "").strip()
            ]
            message = "当前候选环境均不满足清理安全条件。"
            if reason_lines:
                message = f"{message}\n" + "\n".join(reason_lines)
            await self._show_message_async("批量清理", message, kind="warning")
            return

        if not await self._confirm_cleanup_plan_async(plan):
            return

        self._schedule_operation(
            self._async_cleanup_envs(),
            message=self._operation_message("cleanup"),
        )

    async def _sync_source_proxies_async(self) -> None:
        if not self._begin_operation(self._operation_message("sync_source_proxy_scan")):
            return
        try:
            plan = await self._manager.preview_source_proxy_sync()
        except Exception as exc:
            self._end_operation()
            await self._show_operation_error(str(exc))
            return
        self._end_operation()

        if not getattr(plan, "items", None):
            message = "暂无可同步的指纹浏览器环境。"
            if getattr(plan, "errors", None):
                message = f"{message}\n扫描失败：{len(plan.errors)} 个"
            await self._show_message_async("同步来源代理", message, kind="warning")
            return

        if int(getattr(plan, "actionable_count", 0) or 0) <= 0:
            await self._show_message_async("同步来源代理", "当前没有需要更新的来源代理。", kind="info")
            return

        if not await self._confirm_source_proxy_sync_plan_async(plan):
            return

        self._schedule_operation(
            self._async_sync_source_proxies(plan),
            message=self._operation_message("sync_source_proxy"),
        )

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
            self._async_env_operation(env_id, "start"),
            message=self._operation_message(
                "start",
                provider=self._env_provider_for_message(env_id),
                env_id=env_id,
            ),
        )
    
    def _stop_env(self, env_id: str):
        """停止环境（关闭窗口）。"""
        self._schedule_operation(
            self._async_env_operation(env_id, "stop"),
            message=self._operation_message("stop", env_id=env_id),
        )
    
    def _pause_env(self, env_id: str):
        """暂停环境。"""
        self._schedule_operation(
            self._async_env_operation(env_id, "pause"),
            message=self._operation_message("pause", env_id=env_id),
        )
    
    def _resume_env(self, env_id: str):
        """恢复环境。"""
        self._schedule_operation(
            self._async_env_operation(env_id, "resume"),
            message=self._operation_message("resume", env_id=env_id),
        )

    def _recheck_fingerprint_validation(self, env_id: str) -> None:
        """手动重新检测风险环境。"""
        self._schedule_operation(
            self._async_recheck_fingerprint_validation(env_id),
            message=self._operation_message("recheck_fingerprint", env_id=env_id),
        )

    def _repair_fingerprint_location(self, env_id: str) -> None:
        """原地修复 VirtualBrowser location 风险。"""
        self._schedule_operation(
            self._async_repair_fingerprint_location(env_id),
            message=self._operation_message("repair_location", env_id=env_id),
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
            "cleanup": "批量清理",
            "list_sources": "读取来源",
            "sync_source_proxy": "同步来源代理",
            "sync_source_proxy_scan": "扫描来源代理",
            "repair_location": "修复 location",
            "recheck_fingerprint": "重新检测指纹风险",
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
        if action == "sync_source_proxy_scan":
            return "正在读取指纹浏览器来源代理..."
        if action == "sync_source_proxy":
            return "正在同步来源代理到本地环境记录..."
        if action == "recheck_fingerprint":
            return f"正在重新检测环境{env_text}的指纹风险..."
        if action == "repair_location":
            return f"正在按 ip-api 原地修复环境{env_text}的 location..."
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

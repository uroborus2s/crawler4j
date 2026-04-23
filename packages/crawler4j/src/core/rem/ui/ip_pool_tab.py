"""IP 池管理主页面。

设计参考: docs/03-solution/reference-design/module-01-runtime-environment.md §5.5

提供 IP 池管理的主 Tab 页面：
    - IPPoolTab: IP 池管理主页面
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from src.core.foundation.logging import logger
from src.core.rem.ip_pool import IPPool, IPStrategy, get_ip_pool_manager
from src.core.rem.ui.ip_pool_dialogs import AddIPDialog, AddPoolDialog, BatchImportDialog
from src.ui.components.data_table import SkyDataTable
from src.ui.components.data_table_query import resolve_local_data_table_result


class IPPoolWorkerThread(QThread):
    """IP 池操作工作线程。"""
    
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    
    def __init__(self, action: str, **kwargs):
        super().__init__()
        self._action = action
        self._kwargs = kwargs
    
    def run(self):
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            manager = get_ip_pool_manager()
            
            if self._action == "load":
                # 应用启动时已调用 manager.startup()，无需重复调用
                pools = manager.list_pools()
                self.finished.emit(pools)
            elif self._action == "add_pool":
                pool = self._kwargs["pool"]
                manager.add_pool(pool)
                self.finished.emit(pool)
            elif self._action == "delete_pool":
                pool_id = self._kwargs["pool_id"]
                success = manager.remove_pool(pool_id)
                self.finished.emit(success)
            elif self._action == "add_entry":
                pool_id = self._kwargs["pool_id"]
                entry = self._kwargs["entry"]
                pool = manager.get_pool(pool_id)
                if pool:
                    pool.add_entry(entry)
                    manager._persist_entry(entry)
                    self.finished.emit(entry)
                else:
                    self.error.emit("IP 池不存在")
            elif self._action == "add_entries":
                pool_id = self._kwargs["pool_id"]
                entries = self._kwargs["entries"]
                pool = manager.get_pool(pool_id)
                if pool:
                    for entry in entries:
                        pool.add_entry(entry)
                        manager._persist_entry(entry)
                    self.finished.emit(len(entries))
                else:
                    self.error.emit("IP 池不存在")
            else:
                self.error.emit(f"未知操作: {self._action}")
                
            loop.close()
        except Exception as e:
            logger.error(f"[IPPoolUI] 操作失败: {e}")
            self.error.emit(str(e))


class IPPoolTab(QWidget):
    """IP 池管理主页面。"""
    
    POOL_TABLE_SCHEMA = {
        "columns": [
            {"key": "name", "label": "名称", "type": "text", "width": 220},
            {"key": "strategy", "label": "策略", "type": "text", "width": 220},
            {"key": "ip_count", "label": "IP数量", "type": "number", "width": 160, "align": "right"},
            {"key": "in_use", "label": "在用", "type": "number", "width": 120, "align": "right"},
            {"key": "actions", "label": "操作", "type": "actions", "stretch": True},
        ],
        "features": {
            "search": {"enabled": True, "placeholder": "搜索池名称或策略"},
            "sort": {
                "enabled": True,
                "default": [{"field": "name", "direction": "asc"}],
            },
            "pagination": {"enabled": True, "page_size": 10, "page_size_options": [10, 20, 50]},
        },
    }
    ENTRY_TABLE_SCHEMA = {
        "columns": [
            {"key": "address", "label": "IP地址", "type": "text", "width": 180},
            {"key": "port", "label": "端口", "type": "number", "width": 120, "align": "right"},
            {"key": "bound_count", "label": "绑定数", "type": "number", "width": 100, "align": "right"},
            {"key": "safety_score", "label": "安全度", "type": "number", "width": 100, "align": "right"},
            {"key": "expires", "label": "过期时间", "type": "text", "width": 220},
            {"key": "actions", "label": "操作", "type": "actions", "stretch": True},
        ],
        "features": {
            "search": {"enabled": True, "placeholder": "搜索 IP 地址或过期时间"},
            "sort": {
                "enabled": True,
                "default": [{"field": "expires", "direction": "asc"}],
            },
            "pagination": {"enabled": True, "page_size": 10, "page_size_options": [10, 20, 50]},
        },
    }
    
    STRATEGY_NAMES = {
        IPStrategy.LEAST_BOUND: "最少绑定",
        IPStrategy.HIGHEST_SAFETY: "最高安全",
        IPStrategy.LONGEST_TTL: "最长有效",
        IPStrategy.SYSTEM_PROXY: "系统代理",
        IPStrategy.NONE: "无代理",
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_pool: IPPool | None = None
        self._pools: list[IPPool] = []
        self._worker: IPPoolWorkerThread | None = None
        self._pool_rows: list[dict[str, Any]] = []
        self._entry_rows: list[dict[str, Any]] = []
        self._setup_ui()
        self.load_data()
    
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # 应用深色主题样式（按钮和 Splitter）
        self.setStyleSheet("""
            QLabel {
                color: #cdd6f4;
                font-size: 14px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 8px 16px;
                color: white;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
                border-color: rgba(99, 102, 241, 0.5);
            }
            QPushButton:disabled {
                background-color: rgba(255, 255, 255, 0.05);
                color: #666666;
            }
            QPushButton#danger {
                background-color: rgba(255, 118, 117, 0.2);
                border-color: rgba(255, 118, 117, 0.3);
                color: #FF7675;
            }
            QPushButton#danger:hover {
                background-color: rgba(255, 118, 117, 0.3);
            }
            QSplitter::handle {
                background-color: rgba(255, 255, 255, 0.1);
                height: 2px;
            }
        """)
        
        # 使用 Splitter 分割上下区域
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # ===== 上半部分：IP 池列表 =====
        pool_widget = QWidget()
        pool_layout = QVBoxLayout(pool_widget)
        pool_layout.setContentsMargins(0, 0, 0, 0)
        
        # 池列表工具栏
        pool_toolbar = QHBoxLayout()
        pool_toolbar.addWidget(QLabel("IP 池列表"))
        pool_toolbar.addStretch()
        
        add_pool_btn = QPushButton("+ 新建池")
        add_pool_btn.clicked.connect(self._add_pool)
        pool_toolbar.addWidget(add_pool_btn)
        
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.load_data)
        pool_toolbar.addWidget(refresh_btn)
        
        pool_layout.addLayout(pool_toolbar)
        
        # 池列表表格
        self.pool_table = SkyDataTable(schema=self.POOL_TABLE_SCHEMA)
        self.pool_table.query_requested.connect(self._on_pool_query_requested)
        self.pool_table.row_clicked.connect(self._on_pool_selected)
        self.pool_table.row_action_requested.connect(self._on_pool_action_requested)
        pool_layout.addWidget(self.pool_table)
        
        splitter.addWidget(pool_widget)
        
        # ===== 下半部分：IP 条目列表 =====
        entry_widget = QWidget()
        entry_layout = QVBoxLayout(entry_widget)
        entry_layout.setContentsMargins(0, 0, 0, 0)
        
        # 条目列表工具栏
        entry_toolbar = QHBoxLayout()
        self.entry_title = QLabel("选中池的 IP 条目")
        entry_toolbar.addWidget(self.entry_title)
        entry_toolbar.addStretch()
        
        self.add_ip_btn = QPushButton("+ 添加 IP")
        self.add_ip_btn.clicked.connect(self._add_ip)
        self.add_ip_btn.setEnabled(False)
        entry_toolbar.addWidget(self.add_ip_btn)
        
        self.batch_import_btn = QPushButton("批量导入")
        self.batch_import_btn.clicked.connect(self._batch_import)
        self.batch_import_btn.setEnabled(False)
        entry_toolbar.addWidget(self.batch_import_btn)
        
        entry_layout.addLayout(entry_toolbar)
        
        # 条目列表表格
        self.entry_table = SkyDataTable(schema=self.ENTRY_TABLE_SCHEMA)
        self.entry_table.query_requested.connect(self._on_entry_query_requested)
        self.entry_table.row_action_requested.connect(self._on_entry_action_requested)
        entry_layout.addWidget(self.entry_table)
        
        splitter.addWidget(entry_widget)
        
        layout.addWidget(splitter)
    
    def load_data(self) -> None:
        """加载 IP 池数据。"""
        self.pool_table.set_loading(True)
        self._worker = IPPoolWorkerThread("load")
        self._worker.finished.connect(self._on_pools_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()
    
    def _on_pools_loaded(self, pools: list[IPPool]) -> None:
        """池列表加载完成。"""
        self._pools = pools
        current_pool_id = self._current_pool.id if self._current_pool else None
        self._current_pool = next((pool for pool in pools if pool.id == current_pool_id), None)
        self._refresh_pool_table()
        if self._current_pool is not None:
            self._apply_current_pool(self._current_pool)
        else:
            self._clear_current_pool()

    def _refresh_pool_table(self) -> None:
        self._pool_rows = [self._build_pool_row(pool) for pool in self._pools]
        self.pool_table.request_refresh()

    def _refresh_entry_table(self) -> None:
        entries = self._current_pool.entries if self._current_pool else []
        self._entry_rows = [self._build_entry_row(entry) for entry in entries]
        self.entry_table.request_refresh()

    def _build_pool_row(self, pool: IPPool) -> dict[str, Any]:
        in_use = sum(1 for entry in pool.entries if entry.bound_count > 0)
        return {
            "pool": pool,
            "pool_id": pool.id,
            "name": pool.name,
            "strategy": self.STRATEGY_NAMES.get(pool.strategy, str(pool.strategy)),
            "ip_count": {"text": str(len(pool.entries)), "sort_value": len(pool.entries)},
            "in_use": {"text": str(in_use), "sort_value": in_use},
            "actions": [{"id": "delete_pool", "label": "删除", "variant": "danger"}],
        }

    def _build_entry_row(self, entry) -> dict[str, Any]:
        from datetime import datetime

        if entry.expires_at:
            expire_dt = datetime.fromtimestamp(entry.expires_at)
            expire_text = expire_dt.strftime("%Y-%m-%d %H:%M")
        else:
            expire_text = "永久"
        return {
            "entry": entry,
            "entry_id": entry.id,
            "address": entry.address,
            "port": {"text": str(entry.port), "sort_value": int(entry.port)},
            "bound_count": {"text": str(entry.bound_count), "sort_value": int(entry.bound_count)},
            "safety_score": {"text": str(entry.safety_score), "sort_value": float(entry.safety_score)},
            "expires": {
                "text": expire_text,
                "sort_value": entry.expires_at if entry.expires_at else float("inf"),
            },
            "actions": [
                {"id": "edit_entry", "label": "编辑", "variant": "primary"},
                {"id": "delete_entry", "label": "删除", "variant": "danger"},
            ],
        }

    def _on_pool_query_requested(self, request_id: int, query: dict[str, Any]) -> None:
        result = resolve_local_data_table_result(
            self._pool_rows,
            columns=self.POOL_TABLE_SCHEMA["columns"],
            query=query,
        )
        self.pool_table.apply_result(request_id, result)

    def _on_entry_query_requested(self, request_id: int, query: dict[str, Any]) -> None:
        result = resolve_local_data_table_result(
            self._entry_rows,
            columns=self.ENTRY_TABLE_SCHEMA["columns"],
            query=query,
        )
        self.entry_table.apply_result(request_id, result)

    def _on_pool_selected(self, row: dict[str, Any]) -> None:
        pool = row.get("pool")
        if isinstance(pool, IPPool):
            self._apply_current_pool(pool)

    def _apply_current_pool(self, pool: IPPool) -> None:
        self._current_pool = pool
        self.add_ip_btn.setEnabled(True)
        self.batch_import_btn.setEnabled(True)
        self.entry_title.setText(f"IP 条目 - {pool.name}")
        self._refresh_entry_table()

    def _clear_current_pool(self) -> None:
        self._current_pool = None
        self.add_ip_btn.setEnabled(False)
        self.batch_import_btn.setEnabled(False)
        self.entry_title.setText("选中池的 IP 条目")
        self._entry_rows = []
        self.entry_table.request_refresh()

    def _on_pool_action_requested(self, action_id: str, row: dict[str, Any]) -> None:
        if action_id == "delete_pool":
            pool_id = str(row.get("pool_id") or "")
            if pool_id:
                self._delete_pool(pool_id)

    def _on_entry_action_requested(self, action_id: str, row: dict[str, Any]) -> None:
        entry_id = str(row.get("entry_id") or "")
        if not entry_id:
            return
        if action_id == "edit_entry":
            self._edit_entry(entry_id)
        elif action_id == "delete_entry":
            self._delete_entry(entry_id)
    
    def _add_pool(self) -> None:
        """添加 IP 池。"""
        dialog = AddPoolDialog(self)
        if dialog.exec():
            pool = dialog.get_values()
            self._worker = IPPoolWorkerThread("add_pool", pool=pool)
            self._worker.finished.connect(lambda _: self.load_data())
            self._worker.error.connect(self._on_error)
            self._worker.start()
    
    def _delete_pool(self, pool_id: str) -> None:
        """删除 IP 池。"""
        result = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除此 IP 池吗？\n池中的所有 IP 也会被删除。",
        )
        if result == QMessageBox.StandardButton.Yes:
            self._worker = IPPoolWorkerThread("delete_pool", pool_id=pool_id)
            self._worker.finished.connect(lambda _: self.load_data())
            self._worker.error.connect(self._on_error)
            self._worker.start()
    
    def _add_ip(self) -> None:
        """添加单个 IP。"""
        if not self._current_pool:
            return
        
        dialog = AddIPDialog(self._current_pool.id, self)
        if dialog.exec():
            entry = dialog.get_values()
            self._worker = IPPoolWorkerThread("add_entry", pool_id=self._current_pool.id, entry=entry)
            self._worker.finished.connect(lambda _: self._refresh_current_pool())
            self._worker.error.connect(self._on_error)
            self._worker.start()
    
    def _batch_import(self) -> None:
        """批量导入 IP。"""
        if not self._current_pool:
            return
        
        dialog = BatchImportDialog(self._current_pool.id, self)
        if dialog.exec():
            entries = dialog.get_values()
            if entries:
                self._worker = IPPoolWorkerThread("add_entries", pool_id=self._current_pool.id, entries=entries)
                self._worker.finished.connect(lambda count: self._on_batch_import_done(count))
                self._worker.error.connect(self._on_error)
                self._worker.start()
    
    def _on_batch_import_done(self, count: int) -> None:
        """批量导入完成。"""
        QMessageBox.information(self, "导入完成", f"成功导入 {count} 条 IP")
        self._refresh_current_pool()
    
    def _refresh_current_pool(self) -> None:
        """刷新当前池的条目。"""
        if self._current_pool:
            manager = get_ip_pool_manager()
            pool = manager.get_pool(self._current_pool.id)
            if pool:
                self._apply_current_pool(pool)
    
    def _on_error(self, error: str) -> None:
        """错误处理。"""
        QMessageBox.warning(self, "错误", error)
    
    def _edit_entry(self, entry_id: str) -> None:
        """编辑 IP 条目。"""
        if not self._current_pool:
            return
        
        # 查找 entry
        entry = self._current_pool.get_entry(entry_id)
        if not entry:
            QMessageBox.warning(self, "错误", "未找到该 IP 条目")
            return
        
        # 弹出编辑对话框（复用添加对话框）
        dialog = AddIPDialog(self._current_pool.id, self)
        dialog.setWindowTitle("编辑 IP")
        # 填充现有值
        dialog.address_input.setText(entry.address)
        dialog.port_input.setValue(entry.port)  # QSpinBox 使用 setValue
        dialog.protocol_combo.setCurrentText(entry.protocol)
        if entry.username:
            dialog.username_input.setText(entry.username)
        if entry.password:
            dialog.password_input.setText(entry.password)
        
        if dialog.exec():
            # 更新 entry
            new_entry = dialog.get_values()
            entry.address = new_entry.address
            entry.port = new_entry.port
            entry.protocol = new_entry.protocol
            entry.username = new_entry.username
            entry.password = new_entry.password
            entry.expires_at = new_entry.expires_at
            
            # 持久化
            manager = get_ip_pool_manager()
            manager._persist_entry(entry)
            self._refresh_current_pool()
    
    def _delete_entry(self, entry_id: str) -> None:
        """删除 IP 条目。"""
        if not self._current_pool:
            return
        
        result = QMessageBox.question(
            self,
            "确认删除",
            "确定要删除此 IP 条目吗？",
        )
        if result == QMessageBox.StandardButton.Yes:
            # 从池中移除
            self._current_pool.remove_entry(entry_id)
            
            # 从数据库删除
            from src.core.persistence.database import STATE_DB, get_connection
            with get_connection(STATE_DB) as conn:
                conn.execute("DELETE FROM ip_entries WHERE id = ?", (entry_id,))
            
            self._refresh_current_pool()

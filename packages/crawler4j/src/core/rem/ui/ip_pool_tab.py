"""IP 池管理主页面。

设计参考: docs/03-solution/reference-design/module-01-runtime-environment.md §5.5

提供 IP 池管理的主 Tab 页面：
    - IPPoolTab: IP 池管理主页面
"""

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
    
    POOL_COLUMNS = [
        ("name", "名称", 220),
        ("strategy", "策略", 220),
        ("ip_count", "IP数量", 160),
        ("in_use", "在用", 120),
        ("actions", "操作", None),
    ]
    ENTRY_COLUMNS = [
        ("address", "IP地址", 180),
        ("port", "端口", 120),
        ("bound_count", "绑定数", 100),
        ("safety_score", "安全度", 100),
        ("expires", "过期时间", 220),
        ("actions", "操作", None),
    ]
    
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
        self._worker: IPPoolWorkerThread | None = None
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
        self.pool_table = SkyDataTable(columns=self.POOL_COLUMNS)
        self.pool_table.set_render_callback(self._render_pool_row)
        self.pool_table.cell_clicked.connect(self._on_pool_selected)
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
        self.entry_table = SkyDataTable(columns=self.ENTRY_COLUMNS)
        self.entry_table.set_render_callback(self._render_entry_row)
        entry_layout.addWidget(self.entry_table)
        
        splitter.addWidget(entry_widget)
        
        layout.addWidget(splitter)
    
    def load_data(self) -> None:
        """加载 IP 池数据。"""
        self._worker = IPPoolWorkerThread("load")
        self._worker.finished.connect(self._on_pools_loaded)
        self._worker.error.connect(self._on_error)
        self._worker.start()
    
    def _on_pools_loaded(self, pools: list[IPPool]) -> None:
        """池列表加载完成。"""
        self._pools = pools
        self.pool_table.set_data(pools)
    
    def _render_pool_row(self, row: int, pool: IPPool, table) -> None:
        """渲染池表格行。"""
        from PyQt6.QtWidgets import QTableWidgetItem
        
        # 名称 (同时存储 pool 对象)
        item_name = QTableWidgetItem(pool.name)
        item_name.setData(Qt.ItemDataRole.UserRole, pool)
        table.setItem(row, 0, item_name)
        
        # 策略
        strategy_name = self.STRATEGY_NAMES.get(pool.strategy, str(pool.strategy))
        table.setItem(row, 1, QTableWidgetItem(strategy_name))
        
        # IP 数量
        table.setItem(row, 2, QTableWidgetItem(str(len(pool.entries))))
        
        # 在用数量
        in_use = sum(1 for e in pool.entries if e.bound_count > 0)
        table.setItem(row, 3, QTableWidgetItem(str(in_use)))
        
        # 操作按钮
        delete_btn = QPushButton("删除")
        delete_btn.setObjectName("danger")
        delete_btn.clicked.connect(lambda _, pid=pool.id: self._delete_pool(pid))
        table.setCellWidget(row, 4, delete_btn)
    
    def _on_pool_selected(self, row: int, col: int) -> None:
        """池被选中。"""
        item = self.pool_table.item(row, 0)
        if item:
            pool = item.data(Qt.ItemDataRole.UserRole)
            self._current_pool = pool
            self.entry_table.set_data(pool.entries)
            self.add_ip_btn.setEnabled(True)
            self.batch_import_btn.setEnabled(True)
            self.entry_title.setText(f"IP 条目 - {pool.name}")
    
    def _render_entry_row(self, row: int, entry, table) -> None:
        """渲染 IP 条目行。"""
        from datetime import datetime
        
        from PyQt6.QtWidgets import QHBoxLayout, QTableWidgetItem, QWidget
        
        # IP 地址
        table.setItem(row, 0, QTableWidgetItem(entry.address))
        
        # 端口
        table.setItem(row, 1, QTableWidgetItem(str(entry.port)))
        
        # 绑定数
        table.setItem(row, 2, QTableWidgetItem(str(entry.bound_count)))
        
        # 安全度
        table.setItem(row, 3, QTableWidgetItem(str(entry.safety_score)))
        
        # 过期时间 - 显示具体日期时间
        if entry.expires_at:
            expire_dt = datetime.fromtimestamp(entry.expires_at)
            expire_text = expire_dt.strftime("%Y-%m-%d %H:%M")
        else:
            expire_text = "永久"
        table.setItem(row, 4, QTableWidgetItem(expire_text))
        
        # 操作按钮
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(4, 2, 4, 2)
        actions_layout.setSpacing(6)
        
        edit_btn = QPushButton("编辑")
        edit_btn.setFixedWidth(80)
        edit_btn.clicked.connect(lambda _, eid=entry.id: self._edit_entry(eid))
        actions_layout.addWidget(edit_btn)
        
        delete_btn = QPushButton("删除")
        delete_btn.setObjectName("danger")
        delete_btn.setFixedWidth(80)
        delete_btn.clicked.connect(lambda _, eid=entry.id: self._delete_entry(eid))
        actions_layout.addWidget(delete_btn)
        
        table.setCellWidget(row, 5, actions_widget)
    
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
                self._current_pool = pool
                self.entry_table.set_data(pool.entries)
    
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

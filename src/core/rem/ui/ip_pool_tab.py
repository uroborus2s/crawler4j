"""IP 池管理主页面。

设计参考: docs/design/module-01-runtime-environment.md §5.5

提供 IP 池管理的主 Tab 页面：
    - IPPoolTab: IP 池管理主页面
"""

import time

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.foundation.logging import logger
from src.core.rem.ip_pool import IPPool, IPStrategy, get_ip_pool_manager
from src.core.rem.ui.ip_pool_dialogs import AddIPDialog, AddPoolDialog, BatchImportDialog
from src.ui.components.table import SkyTableWidget


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
                result = loop.run_until_complete(manager.startup())
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
    
    POOL_COLUMNS = ["名称", "策略", "IP数量", "在用", "操作"]
    ENTRY_COLUMNS = ["IP地址", "端口", "绑定数", "安全度", "过期时间", "操作"]
    
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
        self.pool_table = SkyTableWidget()
        self.pool_table.setColumnCount(len(self.POOL_COLUMNS))
        self.pool_table.setHorizontalHeaderLabels(self.POOL_COLUMNS)
        self.pool_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.pool_table.cellClicked.connect(self._on_pool_selected)
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
        self.entry_table = SkyTableWidget()
        self.entry_table.setColumnCount(len(self.ENTRY_COLUMNS))
        self.entry_table.setHorizontalHeaderLabels(self.ENTRY_COLUMNS)
        self.entry_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
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
        self.pool_table.setRowCount(len(pools))
        
        for row, pool in enumerate(pools):
            # 名称
            self.pool_table.setItem(row, 0, QTableWidgetItem(pool.name))
            
            # 策略
            strategy_name = self.STRATEGY_NAMES.get(pool.strategy, str(pool.strategy))
            self.pool_table.setItem(row, 1, QTableWidgetItem(strategy_name))
            
            # IP 数量
            self.pool_table.setItem(row, 2, QTableWidgetItem(str(len(pool.entries))))
            
            # 在用数量
            in_use = sum(1 for e in pool.entries if e.bound_count > 0)
            self.pool_table.setItem(row, 3, QTableWidgetItem(str(in_use)))
            
            # 操作按钮
            delete_btn = QPushButton("删除")
            delete_btn.setObjectName("danger")
            delete_btn.setProperty("pool_id", pool.id)
            delete_btn.clicked.connect(lambda checked, pid=pool.id: self._delete_pool(pid))
            self.pool_table.setCellWidget(row, 4, delete_btn)
            
            # 存储 pool 对象
            self.pool_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, pool)
    
    def _on_pool_selected(self, row: int, col: int) -> None:
        """池被选中。"""
        item = self.pool_table.item(row, 0)
        if item:
            pool = item.data(Qt.ItemDataRole.UserRole)
            self._current_pool = pool
            self._update_entry_table(pool)
            self.add_ip_btn.setEnabled(True)
            self.batch_import_btn.setEnabled(True)
            self.entry_title.setText(f"IP 条目 - {pool.name}")
    
    def _update_entry_table(self, pool: IPPool) -> None:
        """更新 IP 条目表格。"""
        self.entry_table.setRowCount(len(pool.entries))
        
        for row, entry in enumerate(pool.entries):
            # IP 地址
            self.entry_table.setItem(row, 0, QTableWidgetItem(entry.address))
            
            # 端口
            self.entry_table.setItem(row, 1, QTableWidgetItem(str(entry.port)))
            
            # 绑定数
            self.entry_table.setItem(row, 2, QTableWidgetItem(str(entry.bound_count)))
            
            # 安全度
            self.entry_table.setItem(row, 3, QTableWidgetItem(str(entry.safety_score)))
            
            # 过期时间
            if entry.expires_at:
                days_left = (entry.expires_at - int(time.time())) // (24 * 60 * 60)
                expire_text = f"{days_left}天后" if days_left > 0 else "已过期"
            else:
                expire_text = "永久"
            self.entry_table.setItem(row, 4, QTableWidgetItem(expire_text))
            
            # 操作（暂时留空）
            self.entry_table.setItem(row, 5, QTableWidgetItem(""))
    
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
                self._update_entry_table(pool)
    
    def _on_error(self, error: str) -> None:
        """错误处理。"""
        QMessageBox.warning(self, "错误", error)

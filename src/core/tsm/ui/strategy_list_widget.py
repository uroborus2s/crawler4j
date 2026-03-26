"""策略列表页面。

规格参考: docs/02-requirements/reference-srs/05-framework-core/05-3-task-strategy-management.md

提供策略的 CRUD 操作界面：
    - 策略列表表格
    - 新建/编辑/删除策略
"""

from dataclasses import dataclass

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.foundation.logging import logger
from src.core.tsm import TaskStrategy, get_strategy_loader
from src.ui.components.data_table import SkyDataTable


@dataclass
class StrategyDisplayItem:
    """策略显示项包装。"""
    raw: TaskStrategy
    display_name: str
    display_mode: str
    display_target: str
    display_env: str


class StrategyListWidget(QWidget):
    """策略列表页面。

    显示所有策略，支持 CRUD 操作。
    """

    strategy_selected = pyqtSignal(str)  # 发出策略 ID

    def __init__(self, parent=None):
        super().__init__(parent)
        self._strategies: list[TaskStrategy] = []
        self._setup_ui()
        self._load_strategies()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题栏
        header = QHBoxLayout()
        title = QLabel("策略管理")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: white;")
        header.addWidget(title)
        header.addStretch()

        # 新建策略按钮
        self.create_btn = QPushButton("+ 新建策略")
        self.create_btn.setStyleSheet("""
            QPushButton {
                background: rgba(99, 102, 241, 0.8);
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background: rgba(99, 102, 241, 1); }
        """)
        self.create_btn.clicked.connect(self._on_create)
        header.addWidget(self.create_btn)

        layout.addLayout(header)

        # 策略表格 (SkyDataTable)
        
        columns = [
            ("name", "名称", -1),
            ("mode", "获取模式", 100),
            ("target", "执行目标", -1),
            ("env", "环境类型", 100),
            ("actions", "操作", 220),
        ]
        
        self.table = SkyDataTable(columns=columns)
        self.table.set_render_callback(self._render_row)
        layout.addWidget(self.table)

    def _load_strategies(self):
        """加载策略列表。"""
        loader = get_strategy_loader()
        self._strategies = loader.list_all()
        # 为每行准备显示数据以便搜索
        display_data = []
        for s in self._strategies:
             # 执行目标字符串处理
            if s.execution:
                target = f"{s.execution.module}/{s.execution.workflow or 'default'}"
            else:
                target = "-"
            
            display_data.append(StrategyDisplayItem(
                raw=s,
                display_name=s.name or s.id[:8],
                display_mode=s.resource.acquisition.mode.value,
                display_target=target,
                display_env=s.resource.acquisition.selector.env_type.value,
            ))
            
        self.table.set_data(display_data)

    def _render_row(self, row: int, item: StrategyDisplayItem, table):
        """渲染单行。"""
        strategy = item.raw
        
        # 名称
        name_item = QTableWidgetItem(item.display_name)
        name_item.setData(Qt.ItemDataRole.UserRole, strategy.id)
        table.setItem(row, 0, name_item)

        # 获取模式
        mode_item = QTableWidgetItem(item.display_mode)
        mode_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, 1, mode_item)

        # 执行目标
        target = item.display_target
        table.setItem(row, 2, QTableWidgetItem(target))

        # 环境类型
        env_item = QTableWidgetItem(item.display_env)
        env_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, 3, env_item)

        # 操作按钮
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(4, 4, 4, 4)
        action_layout.setSpacing(8)

        view_btn = QPushButton("查看")
        view_btn.setStyleSheet("""
            QPushButton {
                background: rgba(100, 116, 139, 0.8);
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(100, 116, 139, 1); }
        """)
        view_btn.clicked.connect(lambda checked, sid=strategy.id: self._on_view(sid))
        action_layout.addWidget(view_btn)

        edit_btn = QPushButton("编辑")
        edit_btn.setStyleSheet("""
            QPushButton {
                background: rgba(59, 130, 246, 0.8);
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(59, 130, 246, 1); }
        """)
        action_layout.addWidget(edit_btn)
        edit_btn.clicked.connect(lambda checked, sid=strategy.id: self._on_edit(sid))

        delete_btn = QPushButton("删除")
        delete_btn.setStyleSheet("""
            QPushButton {
                background: rgba(239, 68, 68, 0.8);
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background: rgba(239, 68, 68, 1); }
        """)
        delete_btn.clicked.connect(lambda checked, sid=strategy.id: self._on_delete(sid))
        action_layout.addWidget(delete_btn)

        table.setCellWidget(row, 4, action_widget)

    def _on_view(self, strategy_id: str):
        """查看策略。"""
        from src.core.tsm.ui.strategy_detail_dialog import StrategyDetailDialog

        # 查找策略
        strategy = next((s for s in self._strategies if s.id == strategy_id), None)
        if not strategy:
            return

        dialog = StrategyDetailDialog(strategy=strategy, parent=self, read_only=True)
        dialog.exec()

    def _on_create(self):
        """新建策略。"""
        from src.core.tsm.ui.strategy_detail_dialog import StrategyDetailDialog

        dialog = StrategyDetailDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            strategy = dialog.get_strategy()
            loader = get_strategy_loader()
            loader.save(strategy)
            
            logger.info(f"[TSM] 新建策略: {strategy.name}")
            self._load_strategies() # Reload to refresh

    def _on_edit(self, strategy_id: str):
        """编辑策略。"""
        from src.core.tsm.ui.strategy_detail_dialog import StrategyDetailDialog

        # 查找策略
        strategy = next((s for s in self._strategies if s.id == strategy_id), None)
        if not strategy:
            return

        dialog = StrategyDetailDialog(strategy=strategy, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_strategy = dialog.get_strategy()
            loader = get_strategy_loader()
            loader.save(updated_strategy)
            
            logger.info(f"[TSM] 更新策略: {updated_strategy.name}")
            self._load_strategies()

    def _on_delete(self, strategy_id: str):
        """删除策略。"""
        strategy = next((s for s in self._strategies if s.id == strategy_id), None)
        if not strategy:
            return

        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除策略 \"{strategy.name}\" 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            loader = get_strategy_loader()
            loader.delete(strategy_id)
            logger.info(f"[TSM] 删除策略: {strategy.name}")
            self._load_strategies()

    def get_strategies(self) -> list[TaskStrategy]:
        """获取策略列表 (供 ATM 使用)。"""
        return self._strategies.copy()

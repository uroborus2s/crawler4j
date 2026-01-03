"""任务流编排页面。

提供简化的串行任务链编排界面。
"""

import json
import uuid

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.plugins import (
    TaskConfig,
    TaskConfigRepository,
    TaskFlow,
    TaskFlowNode,
    TaskFlowRepository,
)
from src.ui.widgets.toast import Toast


class TaskFlowPage(QWidget):
    """任务流编排页面。

    功能：
    1. 左侧：可用任务配置列表
    2. 右侧：当前任务流的节点列表
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._flow_repo = TaskFlowRepository()
        self._config_repo = TaskConfigRepository()
        self._current_flow: TaskFlow | None = None
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        """设置页面UI。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # 标题
        header = QHBoxLayout()
        title = QLabel("🔗 任务编排")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        # 任务流选择
        header.addWidget(QLabel("当前流程:"))
        self.flow_combo = QListWidget()
        self.flow_combo.setMaximumHeight(30)
        self.flow_combo.setFlow(QListWidget.Flow.LeftToRight)
        self.flow_combo.currentItemChanged.connect(self._on_flow_selected)
        header.addWidget(self.flow_combo, 1)

        new_flow_btn = QPushButton("+ 新建流程")
        new_flow_btn.clicked.connect(self._on_new_flow)
        header.addWidget(new_flow_btn)

        layout.addLayout(header)

        # 主内容区域
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ===== 左侧：可用任务 =====
        left_panel = QGroupBox("可用任务")
        left_layout = QVBoxLayout(left_panel)

        self.available_list = QListWidget()
        self.available_list.setMinimumWidth(250)
        left_layout.addWidget(self.available_list)

        add_btn = QPushButton("添加到流程 →")
        add_btn.clicked.connect(self._add_to_flow)
        left_layout.addWidget(add_btn)

        splitter.addWidget(left_panel)

        # ===== 右侧：流程节点 =====
        right_panel = QGroupBox("流程节点")
        right_layout = QVBoxLayout(right_panel)

        self.flow_nodes_list = QListWidget()
        self.flow_nodes_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.flow_nodes_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.flow_nodes_list.customContextMenuRequested.connect(self._show_node_menu)
        self.flow_nodes_list.model().rowsMoved.connect(self._on_nodes_reordered)
        right_layout.addWidget(self.flow_nodes_list)

        # 操作按钮
        btn_layout = QHBoxLayout()
        
        remove_btn = QPushButton("← 移除")
        remove_btn.clicked.connect(self._remove_from_flow)
        btn_layout.addWidget(remove_btn)

        btn_layout.addStretch()

        save_btn = QPushButton("💾 保存流程")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self._save_flow)
        btn_layout.addWidget(save_btn)

        right_layout.addLayout(btn_layout)

        splitter.addWidget(right_panel)
        splitter.setSizes([300, 500])

        layout.addWidget(splitter, 1)

        # 流程信息
        info_group = QGroupBox("流程信息")
        info_layout = QFormLayout(info_group)
        
        self.flow_name_label = QLabel("-")
        self.flow_desc_label = QLabel("-")
        self.flow_desc_label.setWordWrap(True)
        
        info_layout.addRow("名称:", self.flow_name_label)
        info_layout.addRow("描述:", self.flow_desc_label)
        
        layout.addWidget(info_group)

    def _load_data(self):
        """加载数据。"""
        # 加载可用任务配置
        self.available_list.clear()
        configs = self._config_repo.get_enabled()
        
        for c in configs:
            config = TaskConfig.from_dict(c)
            item = QListWidgetItem(f"📋 {config.name}")
            item.setData(Qt.ItemDataRole.UserRole, config)
            self.available_list.addItem(item)

        # 加载任务流列表
        self.flow_combo.clear()
        flows = self._flow_repo.get_enabled()
        
        for f in flows:
            flow = TaskFlow.from_dict(f)
            item = QListWidgetItem(flow.name)
            item.setData(Qt.ItemDataRole.UserRole, flow)
            self.flow_combo.addItem(item)

    def _on_flow_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        """任务流选择变化。"""
        if not current:
            self._current_flow = None
            self.flow_nodes_list.clear()
            self.flow_name_label.setText("-")
            self.flow_desc_label.setText("-")
            return

        self._current_flow = current.data(Qt.ItemDataRole.UserRole)
        self._refresh_flow_nodes()
        
        self.flow_name_label.setText(self._current_flow.name)
        self.flow_desc_label.setText(self._current_flow.description or "无描述")

    def _refresh_flow_nodes(self):
        """刷新流程节点列表。"""
        self.flow_nodes_list.clear()
        if not self._current_flow:
            return

        # 按顺序显示节点
        node_map = {n.id: n for n in self._current_flow.nodes}
        current_id = self._current_flow.start_node_id
        visited = set()

        while current_id and current_id not in visited:
            visited.add(current_id)
            node = node_map.get(current_id)
            if not node:
                break

            # 获取任务配置名称
            config_data = self._config_repo.get_by_id(node.task_config_id)
            config_name = config_data.get("name", "未知") if config_data else "未知"

            item = QListWidgetItem(f"🔹 {config_name} (重试: {node.retry_count})")
            item.setData(Qt.ItemDataRole.UserRole, node)
            self.flow_nodes_list.addItem(item)

            current_id = node.next_on_success

    def _add_to_flow(self):
        """添加任务到流程。"""
        if not self._current_flow:
            Toast.error(self, "请先选择或创建一个流程")
            return

        current = self.available_list.currentItem()
        if not current:
            Toast.error(self, "请选择要添加的任务")
            return

        config: TaskConfig = current.data(Qt.ItemDataRole.UserRole)
        
        # 创建新节点
        new_node = TaskFlowNode(
            id=str(uuid.uuid4())[:8],
            task_config_id=config.id,
            retry_count=3,
        )

        # 添加到节点列表末尾
        if self._current_flow.nodes:
            # 链接到最后一个节点
            last_node = self._current_flow.nodes[-1]
            last_node.next_on_success = new_node.id
        else:
            # 设为起始节点
            self._current_flow.start_node_id = new_node.id

        self._current_flow.nodes.append(new_node)
        self._refresh_flow_nodes()
        Toast.success(self, f"已添加: {config.name}")

    def _remove_from_flow(self):
        """从流程移除任务。"""
        current = self.flow_nodes_list.currentItem()
        if not current or not self._current_flow:
            return

        node: TaskFlowNode = current.data(Qt.ItemDataRole.UserRole)
        
        # 更新链接
        for n in self._current_flow.nodes:
            if n.next_on_success == node.id:
                n.next_on_success = node.next_on_success

        # 如果是起始节点
        if self._current_flow.start_node_id == node.id:
            self._current_flow.start_node_id = node.next_on_success

        # 移除节点
        self._current_flow.nodes = [n for n in self._current_flow.nodes if n.id != node.id]
        self._refresh_flow_nodes()

    def _show_node_menu(self, pos):
        """显示节点右键菜单。"""
        item = self.flow_nodes_list.itemAt(pos)
        if not item:
            return

        node: TaskFlowNode = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        
        edit_action = menu.addAction("✏️ 编辑重试次数")
        edit_action.triggered.connect(lambda: self._edit_node_retry(node))
        
        menu.addSeparator()
        
        remove_action = menu.addAction("🗑️ 移除")
        remove_action.triggered.connect(self._remove_from_flow)

        menu.exec(self.flow_nodes_list.mapToGlobal(pos))

    def _edit_node_retry(self, node: TaskFlowNode):
        """编辑节点重试次数。"""
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑节点")
        layout = QFormLayout(dialog)

        retry_spin = QSpinBox()
        retry_spin.setRange(0, 10)
        retry_spin.setValue(node.retry_count)
        layout.addRow("重试次数:", retry_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            node.retry_count = retry_spin.value()
            self._refresh_flow_nodes()

    def _on_nodes_reordered(self):
        """节点拖拽重排后更新链接。"""
        if not self._current_flow:
            return

        # 按UI顺序重建节点链接
        new_nodes = []
        for i in range(self.flow_nodes_list.count()):
            item = self.flow_nodes_list.item(i)
            node: TaskFlowNode = item.data(Qt.ItemDataRole.UserRole)
            node.next_on_success = None
            new_nodes.append(node)

        # 重建链接
        for i, node in enumerate(new_nodes):
            if i < len(new_nodes) - 1:
                node.next_on_success = new_nodes[i + 1].id

        # 更新起始节点
        if new_nodes:
            self._current_flow.start_node_id = new_nodes[0].id
            self._current_flow.nodes = new_nodes

    def _on_new_flow(self):
        """新建流程。"""
        dialog = QDialog(self)
        dialog.setWindowTitle("新建任务流程")
        dialog.setMinimumWidth(400)
        layout = QFormLayout(dialog)

        name_input = QLineEdit()
        name_input.setPlaceholderText("流程名称")
        layout.addRow("名称:", name_input)

        desc_input = QTextEdit()
        desc_input.setPlaceholderText("流程描述")
        desc_input.setMaximumHeight(80)
        layout.addRow("描述:", desc_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = name_input.text().strip()
            if not name:
                Toast.error(self, "请输入流程名称")
                return

            flow_id = self._flow_repo.create(
                name=name,
                description=desc_input.toPlainText().strip(),
            )
            Toast.success(self, "流程已创建")
            self._load_data()

            # 选中新创建的流程
            for i in range(self.flow_combo.count()):
                item = self.flow_combo.item(i)
                flow: TaskFlow = item.data(Qt.ItemDataRole.UserRole)
                if flow.id == flow_id:
                    self.flow_combo.setCurrentItem(item)
                    break

    def _save_flow(self):
        """保存当前流程。"""
        if not self._current_flow:
            Toast.error(self, "没有选中的流程")
            return

        flow_data = {
            "nodes": [n.to_dict() for n in self._current_flow.nodes],
            "start_node_id": self._current_flow.start_node_id,
        }

        self._flow_repo.update(self._current_flow.id, {
            "flow_data": flow_data,
        })

        Toast.success(self, "流程已保存")

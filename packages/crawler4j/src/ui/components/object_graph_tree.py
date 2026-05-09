"""Shared object graph tree component."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QTreeWidget, QTreeWidgetItem, QWidget


class ObjectGraphTree(QTreeWidget):
    """Two-column tree for object graphs with inline configuration widgets."""

    def __init__(
        self,
        *,
        headers: tuple[str, str] = ("对象图", "配置"),
        min_height: int = 220,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setColumnCount(2)
        self.setHeaderLabels(list(headers))
        self.setRootIsDecorated(True)
        self.setIndentation(18)
        self.setMinimumHeight(min_height)
        self.header().setStretchLastSection(True)
        self.setStyleSheet(
            """
            QTreeWidget {
                background-color: rgba(255, 255, 255, 0.035);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 4px;
                outline: none;
            }
            QTreeWidget::item {
                min-height: 30px;
                color: rgba(255, 255, 255, 0.82);
            }
            QTreeWidget::item:hover {
                background: rgba(255, 255, 255, 0.045);
            }
            QTreeWidget::item:selected {
                background: rgba(99, 102, 241, 0.25);
                color: white;
            }
            QHeaderView::section {
                background: rgba(255, 255, 255, 0.06);
                color: rgba(255, 255, 255, 0.72);
                border: none;
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                padding: 6px 8px;
                font-weight: bold;
            }
            """
        )

    def add_node(
        self,
        label: str,
        *,
        value: str = "",
        parent: QTreeWidgetItem | None = None,
        role: str = "",
        tooltip: str = "",
    ) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label, value])
        if role:
            item.setData(0, Qt.ItemDataRole.UserRole, role)
        if tooltip:
            item.setToolTip(0, tooltip)
        if parent is None:
            self.addTopLevelItem(item)
        else:
            parent.addChild(item)
        return item

    def set_config_widget(self, item: QTreeWidgetItem, widget: QWidget) -> None:
        self.setItemWidget(item, 1, widget)

    def finalize(self) -> None:
        self.expandAll()
        self.resizeColumnToContents(0)

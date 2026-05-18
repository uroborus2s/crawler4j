"""Shared object graph tree component."""

from __future__ import annotations

from collections.abc import Iterator

from PyQt6.QtCore import QModelIndex, QPointF, QRect, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QTreeWidget, QTreeWidgetItem, QWidget


class ObjectGraphTree(QTreeWidget):
    """Two-column tree for object graphs with inline configuration widgets."""

    def __init__(
        self,
        *,
        headers: tuple[str, str] = ("对象图", "配置"),
        min_height: int = 96,
        max_height: int = 360,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._min_tree_height = min_height
        self._max_tree_height = max(min_height, max_height)
        self.setColumnCount(2)
        self.setHeaderLabels(list(headers))
        self.setRootIsDecorated(True)
        self.setIndentation(18)
        self.setMinimumHeight(self._min_tree_height)
        self.setMaximumHeight(self._max_tree_height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.header().setStretchLastSection(True)
        self.itemExpanded.connect(lambda _item: self.sync_height_to_contents())
        self.itemCollapsed.connect(lambda _item: self.sync_height_to_contents())
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
            QTreeWidget::branch {
                background: transparent;
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
        self.sync_height_to_contents()

    def sync_height_to_contents(self) -> None:
        height = self._visible_content_height()
        self.setMinimumHeight(height)
        self.setMaximumHeight(height)
        self.updateGeometry()

    def drawBranches(self, painter: QPainter, rect: QRect, index: QModelIndex) -> None:
        if not index.isValid():
            return
        item = self.itemFromIndex(index)
        if item is None or item.childCount() <= 0:
            return

        color = "#ffffff" if item.isSelected() else "#e5e7eb"
        direction = "down" if self.isExpanded(index) else "right"
        _draw_branch_chevron(painter, rect, direction=direction, color=color)

    def _visible_content_height(self) -> int:
        visible_items = tuple(self._iter_visible_items())
        header_height = 0 if self.header().isHidden() else self.header().sizeHint().height()
        content_height = header_height + len(visible_items) * self._row_height_hint() + self.frameWidth() * 2 + 8
        return max(self._min_tree_height, min(content_height, self._max_tree_height))

    def _row_height_hint(self) -> int:
        height = max(34, self.fontMetrics().height() + 16)
        for item in self._iter_visible_items():
            for column in range(self.columnCount()):
                widget = self.itemWidget(item, column)
                if widget is None:
                    continue
                height = max(height, widget.sizeHint().height() + 6, widget.minimumHeight() + 6)
        return height

    def _iter_visible_items(self) -> Iterator[QTreeWidgetItem]:
        for index in range(self.topLevelItemCount()):
            yield from self._iter_visible_subtree(self.topLevelItem(index))

    def _iter_visible_subtree(self, item: QTreeWidgetItem) -> Iterator[QTreeWidgetItem]:
        yield item
        if not item.isExpanded():
            return
        for index in range(item.childCount()):
            yield from self._iter_visible_subtree(item.child(index))


def _draw_branch_chevron(painter: QPainter, rect: QRect, *, direction: str, color: str) -> None:
    if rect.isNull():
        return

    size = min(max(8.0, min(rect.width(), rect.height()) * 0.48), 12.0)
    half_width = size * 0.34
    half_height = size * 0.26
    center_x = rect.center().x()
    center_y = rect.center().y()

    if direction == "right":
        points = (
            QPointF(center_x - half_height, center_y - half_width),
            QPointF(center_x + half_height, center_y),
            QPointF(center_x - half_height, center_y + half_width),
        )
    else:
        points = (
            QPointF(center_x - half_width, center_y - half_height),
            QPointF(center_x, center_y + half_height),
            QPointF(center_x + half_width, center_y - half_height),
        )

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color))
    pen.setWidthF(1.9)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawLine(points[0], points[1])
    painter.drawLine(points[1], points[2])
    painter.restore()

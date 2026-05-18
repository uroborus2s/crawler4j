from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap

from src.ui.components.line_edit import StyledLineEdit
from src.ui.components.object_graph_tree import ObjectGraphTree


def test_object_graph_tree_adds_nested_nodes_and_config_widgets(qtbot):
    tree = ObjectGraphTree(headers=("结构", "设置"))
    qtbot.addWidget(tree)

    root = tree.add_node("工作流: 同步流程", role="workflow")
    component = tree.add_node("账号组件 (account_client)", parent=root, role="component")
    parameter = tree.add_node("参数: Base URL *", parent=component, role="parameter")
    editor = StyledLineEdit()
    tree.set_config_widget(parameter, editor)
    tree.finalize()

    assert tree.headerItem().text(0) == "结构"
    assert tree.headerItem().text(1) == "设置"
    assert tree.topLevelItem(0) is root
    assert root.data(0, Qt.ItemDataRole.UserRole) == "workflow"
    assert root.child(0) is component
    assert component.data(0, Qt.ItemDataRole.UserRole) == "component"
    assert component.child(0) is parameter
    assert parameter.data(0, Qt.ItemDataRole.UserRole) == "parameter"
    assert tree.itemWidget(parameter, 1) is editor
    assert root.isExpanded()


def test_object_graph_tree_height_tracks_visible_rows(qtbot):
    tree = ObjectGraphTree(headers=("结构", "设置"), min_height=80, max_height=240)
    qtbot.addWidget(tree)

    root = tree.add_node("工作流: 同步流程", role="workflow")
    for index in range(4):
        tree.add_node(f"对象 {index}", parent=root, role="component")
    tree.finalize()

    expanded_height = tree.maximumHeight()
    root.setExpanded(False)
    tree.sync_height_to_contents()

    assert tree.maximumHeight() == tree.minimumHeight()
    assert tree.maximumHeight() < expanded_height


def test_object_graph_tree_draws_visible_branch_chevron(qtbot):
    tree = ObjectGraphTree(headers=("结构", "设置"))
    qtbot.addWidget(tree)
    root = tree.add_node("工作流: 同步流程", role="workflow")
    tree.add_node("账号组件", parent=root, role="component")
    tree.finalize()

    pixmap = QPixmap(24, 24)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    tree.drawBranches(painter, QRect(0, 0, 24, 24), tree.indexFromItem(root, 0))
    painter.end()

    image = pixmap.toImage()
    painted_pixels = 0
    for x in range(image.width()):
        for y in range(image.height()):
            if image.pixelColor(x, y).alpha() > 0:
                painted_pixels += 1

    assert painted_pixels > 0

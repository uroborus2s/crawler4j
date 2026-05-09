from PyQt6.QtCore import Qt

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

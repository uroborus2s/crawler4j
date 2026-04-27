from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView

from src.ui.components.button import StyledButton
from src.ui.components.data_table import SkyDataTable


def _build_table() -> SkyDataTable:
    return SkyDataTable(
        {
            "columns": [
                {"key": "name", "label": "名称", "sortable": True, "stretch": True},
                {"key": "status", "label": "状态", "type": "badge", "sortable": True, "width": 120},
                {"key": "actions", "label": "操作", "type": "actions", "width": 160},
            ],
            "features": {
                "search": {"enabled": True, "placeholder": "搜索名称"},
                "sort": {"enabled": True},
                "pagination": {"enabled": True, "page_size": 2, "page_size_options": [2, 5]},
            },
        }
    )


def test_sky_data_table_emits_query_with_search_sort_and_pagination(qtbot):
    table = _build_table()
    qtbot.addWidget(table)

    queries: list[tuple[int, dict]] = []
    table.query_requested.connect(lambda request_id, query: queries.append((request_id, dict(query))))

    table.request_refresh()
    table.apply_result(
        queries[-1][0],
        {
            "rows": [{"name": "alpha"}, {"name": "beta"}],
            "total": 4,
            "page": 1,
            "page_size": 2,
        },
    )
    table.search_input.setText("alpha")
    table.apply_result(
        queries[-1][0],
        {
            "rows": [{"name": "alpha"}, {"name": "alphabet"}],
            "total": 4,
            "page": 1,
            "page_size": 2,
        },
    )
    table.table.horizontalHeader().sectionClicked.emit(0)
    table.apply_result(
        queries[-1][0],
        {
            "rows": [{"name": "alpha"}, {"name": "alphabet"}],
            "total": 4,
            "page": 1,
            "page_size": 2,
            "sort": [{"field": "name", "direction": "asc"}],
        },
    )
    table.next_btn.click()

    assert queries[0][1]["page"] == 1
    assert queries[0][1]["page_size"] == 2
    assert queries[1][1]["search_text"] == "alpha"
    assert queries[2][1]["sort"] == [{"field": "name", "direction": "asc"}]
    assert queries[3][1]["page"] == 2


def test_sky_data_table_hides_qt_vertical_header(qtbot):
    table = _build_table()
    qtbot.addWidget(table)

    assert table.table.verticalHeader().isVisible() is False


def test_sky_data_table_hides_scrollbars(qtbot):
    table = _build_table()
    qtbot.addWidget(table)

    assert table.table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert table.table.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_sky_data_table_supports_multi_selection_schema(qtbot):
    table = SkyDataTable(
        {
            "selection_mode": "multi",
            "columns": [{"key": "name", "label": "名称"}],
            "features": {"pagination": {"enabled": False}},
        }
    )
    qtbot.addWidget(table)

    assert table.table.selectionMode() == QAbstractItemView.SelectionMode.ExtendedSelection


def test_sky_data_table_ignores_stale_results_and_keeps_latest_rows(qtbot):
    table = _build_table()
    qtbot.addWidget(table)

    captured: list[int] = []

    def _on_query(request_id: int, query: dict) -> None:
        captured.append(request_id)
        if request_id == 1:
            table.apply_result(
                request_id,
                {
                    "rows": [{"name": "stale", "status": {"text": "旧"}}],
                    "total": 1,
                    "page": 1,
                    "page_size": 2,
                },
            )

    table.query_requested.connect(_on_query)
    table.request_refresh()
    table.request_refresh()
    table.apply_result(
        captured[-1],
        {
            "rows": [{"name": "fresh", "status": {"text": "新"}}],
            "total": 1,
            "page": 1,
            "page_size": 2,
        },
    )

    assert table.table.item(0, 0).text() == "fresh"
    assert table.info_label.text() == "共 1 条"


def test_sky_data_table_emits_row_and_action_events(qtbot):
    table = _build_table()
    qtbot.addWidget(table)
    table.apply_result(
        0,
        {
            "rows": [
                {
                    "name": "alpha",
                    "status": {"text": "启用", "tone": "success"},
                    "actions": [{"id": "detail", "label": "详情", "variant": "primary"}],
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 2,
        },
    )

    clicked_rows: list[dict] = []
    action_rows: list[tuple[str, dict]] = []
    table.row_clicked.connect(lambda row: clicked_rows.append(dict(row)))
    table.row_action_requested.connect(lambda action_id, row: action_rows.append((action_id, dict(row))))

    table.table.cellClicked.emit(0, 0)
    assert table.table.rowHeight(0) == 52
    action_button = table.table.cellWidget(0, 2).findChildren(StyledButton)[0]
    assert isinstance(action_button, StyledButton)
    assert action_button.minimumHeight() == 34
    assert action_button.maximumHeight() == 34
    qtbot.mouseClick(action_button, Qt.MouseButton.LeftButton)

    assert clicked_rows[0]["name"] == "alpha"
    assert action_rows == [("detail", {"name": "alpha", "status": {"text": "启用", "tone": "success"}, "actions": [{"id": "detail", "label": "详情", "variant": "primary"}]})]


def test_sky_data_table_action_cell_row_budget_fits_buttons(qtbot):
    table = _build_table()
    qtbot.addWidget(table)
    table.apply_result(
        0,
        {
            "rows": [
                {
                    "name": "alpha",
                    "status": {"text": "启用", "tone": "success"},
                    "actions": [
                        {"id": "run_once", "label": "▶ 执行一次", "variant": "primary"},
                        {"id": "debug", "label": "🐞 调试", "variant": "warning"},
                        {"id": "edit", "label": "✏️", "variant": "secondary"},
                        {"id": "delete", "label": "🗑", "variant": "secondary"},
                    ],
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 2,
        },
    )

    action_widget = table.table.cellWidget(0, 2)
    action_buttons = action_widget.findChildren(StyledButton)

    assert table.table.rowHeight(0) == 52
    assert action_buttons
    assert action_widget.sizeHint().height() >= max(button.height() for button in action_buttons) + 4
    assert table.table.rowHeight(0) >= action_widget.sizeHint().height() + 12


def test_sky_data_table_can_disable_inline_loading_bar(qtbot):
    table = SkyDataTable(
        {
            "columns": [{"key": "name", "label": "名称"}],
            "features": {
                "pagination": {"enabled": False},
                "loading": {"inline": False, "disable_interaction": False},
            },
        }
    )
    qtbot.addWidget(table)

    table.set_loading(True)

    assert table.loading_bar.isHidden() is True
    assert table.table.isEnabled() is True

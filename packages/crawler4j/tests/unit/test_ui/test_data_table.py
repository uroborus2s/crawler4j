from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QAbstractItemView

from src.ui.components.button import StyledButton
from src.ui.components.data_table import SkyDataTable
from src.ui.components.data_table_query import resolve_local_data_table_result


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


def test_sky_data_table_sort_requires_explicit_sortable_column(qtbot):
    table = SkyDataTable(
        {
            "columns": [
                {"key": "name", "label": "名称"},
                {"key": "status", "label": "状态", "sortable": True},
            ],
            "features": {"sort": {"enabled": True}, "pagination": {"enabled": False}},
        }
    )
    qtbot.addWidget(table)

    queries: list[tuple[int, dict]] = []
    table.query_requested.connect(lambda request_id, query: queries.append((request_id, dict(query))))
    table.request_refresh()

    table.table.horizontalHeader().sectionClicked.emit(0)
    assert len(queries) == 1

    table.table.horizontalHeader().sectionClicked.emit(1)
    assert queries[-1][1]["sort"] == [{"field": "status", "direction": "asc"}]


def test_sky_data_table_renders_select_column_filter_and_emits_params(qtbot):
    table = SkyDataTable(
        {
            "columns": [
                {
                    "key": "record_status",
                    "label": "账号状态",
                    "type": "select",
                    "options": ["不限", "正常", "黑号"],
                    "searchable": True,
                },
                {"key": "phone", "label": "手机号", "searchable": True},
            ],
            "features": {"pagination": {"enabled": False}},
        }
    )
    qtbot.addWidget(table)

    queries: list[dict] = []
    table.query_requested.connect(lambda _request_id, query: queries.append(dict(query)))

    combo = table._filter_combos["record_status"]
    assert [combo.itemText(index) for index in range(combo.count())] == ["不限", "正常", "黑号"]

    combo.setCurrentText("黑号")
    assert queries[-1]["page"] == 1
    assert queries[-1]["params"] == {"record_status": "黑号"}

    combo.setCurrentText("不限")
    assert queries[-1]["page"] == 1
    assert queries[-1]["params"] == {}


def test_sky_data_table_renders_visible_sort_controls_and_emits_sort(qtbot):
    table = SkyDataTable(
        {
            "columns": [
                {"key": "created_at", "label": "创建时间", "sortable": True},
                {"key": "updated_at", "label": "更新时间", "sortable": True},
            ],
            "features": {"sort": {"enabled": True}, "pagination": {"enabled": False}},
        }
    )
    qtbot.addWidget(table)

    queries: list[dict] = []
    table.query_requested.connect(lambda _request_id, query: queries.append(dict(query)))

    assert table.sort_field_combo.isHidden() is False
    assert table.sort_field_combo.findData("created_at") >= 0
    assert table.sort_field_combo.findData("updated_at") >= 0

    table.sort_direction_combo.setCurrentIndex(table.sort_direction_combo.findData("desc"))
    table.sort_field_combo.setCurrentIndex(table.sort_field_combo.findData("updated_at"))
    assert queries[-1]["sort"] == [{"field": "updated_at", "direction": "desc"}]

    table.sort_field_combo.setCurrentIndex(table.sort_field_combo.findData(""))
    assert queries[-1]["sort"] == []


def test_sky_data_table_header_sort_syncs_visible_sort_controls(qtbot):
    table = SkyDataTable(
        {
            "columns": [
                {"key": "created_at", "label": "创建时间", "sortable": True},
                {"key": "updated_at", "label": "更新时间", "sortable": True},
            ],
            "features": {"sort": {"enabled": True}, "pagination": {"enabled": False}},
        }
    )
    qtbot.addWidget(table)

    queries: list[dict] = []
    table.query_requested.connect(lambda _request_id, query: queries.append(dict(query)))

    table.table.horizontalHeader().sectionClicked.emit(1)
    assert queries[-1]["sort"] == [{"field": "updated_at", "direction": "asc"}]
    assert table.sort_field_combo.currentData() == "updated_at"
    assert table.sort_direction_combo.currentData() == "asc"

    table.table.horizontalHeader().sectionClicked.emit(1)
    assert queries[-1]["sort"] == [{"field": "updated_at", "direction": "desc"}]
    assert table.sort_field_combo.currentData() == "updated_at"
    assert table.sort_direction_combo.currentData() == "desc"

    table.table.horizontalHeader().sectionClicked.emit(1)
    assert queries[-1]["sort"] == []
    assert table.sort_field_combo.currentData() == ""


def test_resolve_local_data_table_search_requires_explicit_searchable_column():
    result = resolve_local_data_table_result(
        [
            {"name": "alpha", "status": "ready"},
            {"name": "beta", "status": "pending"},
        ],
        columns=[
            {"key": "name", "label": "名称"},
            {"key": "status", "label": "状态", "searchable": True},
        ],
        query={"search_text": "alpha", "page": 1, "page_size": 20},
    )

    assert result["rows"] == []

    result = resolve_local_data_table_result(
        [
            {"name": "alpha", "status": "ready"},
            {"name": "beta", "status": "pending"},
        ],
        columns=[
            {"key": "name", "label": "名称"},
            {"key": "status", "label": "状态", "searchable": True},
        ],
        query={"search_text": "ready", "page": 1, "page_size": 20},
    )

    assert result["rows"] == [{"name": "alpha", "status": "ready"}]


def test_resolve_local_data_table_sort_requires_explicit_sortable_column():
    rows = [
        {"name": "alpha", "status": "ready"},
        {"name": "beta", "status": "pending"},
    ]

    result = resolve_local_data_table_result(
        rows,
        columns=[
            {"key": "name", "label": "名称"},
            {"key": "status", "label": "状态", "sortable": True},
        ],
        query={"sort": [{"field": "name", "direction": "desc"}], "page": 1, "page_size": 20},
    )

    assert result["rows"] == rows

    result = resolve_local_data_table_result(
        rows,
        columns=[
            {"key": "name", "label": "名称"},
            {"key": "status", "label": "状态", "sortable": True},
        ],
        query={"sort": [{"field": "status", "direction": "asc"}], "page": 1, "page_size": 20},
    )

    assert [row["status"] for row in result["rows"]] == ["pending", "ready"]


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

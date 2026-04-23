from src.core.rem.ip_pool import IPEntry, IPPool, IPStrategy


def _build_pool() -> IPPool:
    pool = IPPool(id="pool-1", name="主池", strategy=IPStrategy.LEAST_BOUND)
    pool.entries = [
        IPEntry(
            id="entry-1",
            pool_id=pool.id,
            address="1.1.1.1",
            port=8080,
            bound_count=2,
            safety_score=95,
        )
    ]
    return pool


def test_ip_pool_tab_pool_row_click_populates_entry_table(qtbot, monkeypatch):
    import src.core.rem.ui.ip_pool_tab as ip_pool_tab

    monkeypatch.setattr(ip_pool_tab.IPPoolTab, "load_data", lambda self: None)

    widget = ip_pool_tab.IPPoolTab()
    qtbot.addWidget(widget)
    pool = _build_pool()

    widget._pools = [pool]
    widget._refresh_pool_table()
    pool_row = widget.pool_table.displayed_rows()[0]

    widget._on_pool_selected(pool_row)
    entry_row = widget.entry_table.displayed_rows()[0]

    assert pool_row["name"] == "主池"
    assert widget.entry_title.text() == "IP 条目 - 主池"
    assert entry_row["address"] == "1.1.1.1"
    assert [action["id"] for action in entry_row["actions"]] == ["edit_entry", "delete_entry"]


def test_ip_pool_tab_pool_action_routes_delete(qtbot, monkeypatch):
    import src.core.rem.ui.ip_pool_tab as ip_pool_tab

    monkeypatch.setattr(ip_pool_tab.IPPoolTab, "load_data", lambda self: None)

    widget = ip_pool_tab.IPPoolTab()
    qtbot.addWidget(widget)
    deleted: list[str] = []
    monkeypatch.setattr(widget, "_delete_pool", lambda pool_id: deleted.append(pool_id))

    widget._on_pool_action_requested("delete_pool", {"pool_id": "pool-1"})

    assert deleted == ["pool-1"]

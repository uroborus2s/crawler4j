from src.core.rem.ip_pool import IPEntry, IPPool, IPStrategy
from src.core.rem.proxy_probe import ProxyProbeResult


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
    assert [action["id"] for action in entry_row["actions"]] == ["test_entry", "edit_entry", "delete_entry"]


def test_ip_pool_tab_pool_action_routes_delete(qtbot, monkeypatch):
    import src.core.rem.ui.ip_pool_tab as ip_pool_tab

    monkeypatch.setattr(ip_pool_tab.IPPoolTab, "load_data", lambda self: None)

    widget = ip_pool_tab.IPPoolTab()
    qtbot.addWidget(widget)
    deleted: list[str] = []
    monkeypatch.setattr(widget, "_delete_pool", lambda pool_id: deleted.append(pool_id))

    widget._on_pool_action_requested("delete_pool", {"pool_id": "pool-1"})

    assert deleted == ["pool-1"]


def test_ip_pool_tab_entry_action_routes_probe(qtbot, monkeypatch):
    import src.core.rem.ui.ip_pool_tab as ip_pool_tab

    monkeypatch.setattr(ip_pool_tab.IPPoolTab, "load_data", lambda self: None)

    widget = ip_pool_tab.IPPoolTab()
    qtbot.addWidget(widget)
    tested: list[str] = []
    monkeypatch.setattr(widget, "_test_entry", lambda entry_id: tested.append(entry_id))

    widget._on_entry_action_requested("test_entry", {"entry_id": "entry-1"})

    assert tested == ["entry-1"]


def test_ip_pool_tab_builds_probe_result_message(qtbot, monkeypatch):
    import src.core.rem.ui.ip_pool_tab as ip_pool_tab

    monkeypatch.setattr(ip_pool_tab.IPPoolTab, "load_data", lambda self: None)

    widget = ip_pool_tab.IPPoolTab()
    qtbot.addWidget(widget)

    payload = widget._build_probe_result_dialog(
        ProxyProbeResult(
            ok=True,
            stage="probe",
            protocol="socks5",
            masked_proxy_url="socks5://demo:***@10.0.0.9:1080",
            latency_ms=512,
            exit_ip="1.2.3.4",
            http_status=200,
            detail="探针请求成功",
            error_type=None,
        )
    )

    assert payload.title == "代理测试成功"
    assert "出口 IP: 1.2.3.4" in payload.summary
    assert "masked_proxy_url: socks5://demo:***@10.0.0.9:1080" in payload.details


def test_ip_pool_tab_probe_result_dialog_uses_dark_style(qtbot, monkeypatch):
    import src.core.rem.ui.ip_pool_tab as ip_pool_tab

    monkeypatch.setattr(ip_pool_tab.IPPoolTab, "load_data", lambda self: None)

    widget = ip_pool_tab.IPPoolTab()
    qtbot.addWidget(widget)
    captured: dict[str, str] = {}

    def fake_exec(dialog):
        captured["style"] = dialog.styleSheet()
        captured["text"] = dialog.text()
        captured["details"] = dialog.detailedText()
        return 0

    monkeypatch.setattr(ip_pool_tab.QMessageBox, "exec", fake_exec)

    widget._show_probe_result(
        ProxyProbeResult(
            ok=True,
            stage="probe",
            protocol="socks5",
            masked_proxy_url="socks5://demo:***@10.0.0.9:1080",
            latency_ms=512,
            exit_ip="1.2.3.4",
            http_status=200,
            detail="探针请求成功",
            error_type=None,
        )
    )

    assert "#0f172a" in captured["style"]
    assert "QMessageBox QTextEdit" in captured["style"]
    assert "出口 IP: 1.2.3.4" in captured["text"]
    assert "masked_proxy_url: socks5://demo:***@10.0.0.9:1080" in captured["details"]

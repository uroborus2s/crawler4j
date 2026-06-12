from datetime import datetime

from src.core.rem.ip_pool import IPEntry, IPEntryStatus, IPPool, IPStrategy
from src.core.rem.proxy_probe import ProxyProbeResult
from src.ui.components.button import StyledButton


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
            last_used_at=1_746_000_000,
            status=IPEntryStatus.AVAILABLE,
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
    assert entry_row["status"]["text"] == "可用"
    assert entry_row["last_used_at"]["text"] == datetime.fromtimestamp(1_746_000_000).strftime("%Y-%m-%d %H:%M")
    assert [action["id"] for action in entry_row["actions"]] == [
        "test_entry",
        "disable_entry",
        "edit_entry",
        "delete_entry",
    ]


def test_ip_pool_tab_disabled_entry_row_shows_enable_action(qtbot, monkeypatch):
    import src.core.rem.ui.ip_pool_tab as ip_pool_tab

    monkeypatch.setattr(ip_pool_tab.IPPoolTab, "load_data", lambda self: None)

    widget = ip_pool_tab.IPPoolTab()
    qtbot.addWidget(widget)
    pool = _build_pool()
    pool.entries[0].status = IPEntryStatus.DISABLED

    widget._apply_current_pool(pool)
    entry_row = widget.entry_table.displayed_rows()[0]

    assert entry_row["status"]["text"] == "不可用"
    assert [action["id"] for action in entry_row["actions"]] == [
        "test_entry",
        "enable_entry",
        "edit_entry",
        "delete_entry",
    ]


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


def test_ip_pool_tab_entry_action_routes_status_toggle(qtbot, monkeypatch):
    import src.core.rem.ui.ip_pool_tab as ip_pool_tab

    monkeypatch.setattr(ip_pool_tab.IPPoolTab, "load_data", lambda self: None)

    widget = ip_pool_tab.IPPoolTab()
    qtbot.addWidget(widget)
    toggled: list[tuple[str, IPEntryStatus]] = []
    monkeypatch.setattr(widget, "_set_entry_status", lambda entry_id, status: toggled.append((entry_id, status)))

    widget._on_entry_action_requested("disable_entry", {"entry_id": "entry-1"})
    widget._on_entry_action_requested("enable_entry", {"entry_id": "entry-2"})

    assert toggled == [
        ("entry-1", IPEntryStatus.DISABLED),
        ("entry-2", IPEntryStatus.AVAILABLE),
    ]


def test_ip_pool_tab_uses_public_toolbar_buttons(qtbot, monkeypatch):
    import src.core.rem.ui.ip_pool_tab as ip_pool_tab

    monkeypatch.setattr(ip_pool_tab.IPPoolTab, "load_data", lambda self: None)

    widget = ip_pool_tab.IPPoolTab()
    qtbot.addWidget(widget)

    buttons = widget.findChildren(StyledButton)
    texts = {button.text() for button in buttons}

    assert "+ 新建池" in texts
    assert "刷新" in texts
    assert "+ 添加 IP" in texts
    assert "批量导入" in texts


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
    assert payload.kind == "info"
    assert "出口 IP: 1.2.3.4" in payload.summary
    assert "masked_proxy_url: socks5://demo:***@10.0.0.9:1080" in payload.details


def test_ip_pool_tab_probe_result_uses_public_message_dialog(qtbot, monkeypatch):
    import src.core.rem.ui.ip_pool_tab as ip_pool_tab

    monkeypatch.setattr(ip_pool_tab.IPPoolTab, "load_data", lambda self: None)

    widget = ip_pool_tab.IPPoolTab()
    qtbot.addWidget(widget)
    captured: dict[str, object] = {}

    def fake_exec(dialog):
        captured["dialog_type"] = type(dialog).__name__
        captured["title"] = dialog.title
        captured["message"] = dialog.message
        captured["details"] = dialog.details
        captured["kind"] = dialog.kind
        return 0

    monkeypatch.setattr(ip_pool_tab.MessageDialog, "exec", fake_exec)

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

    assert captured["dialog_type"] == "MessageDialog"
    assert captured["title"] == "代理测试成功"
    assert captured["kind"] == "info"
    assert "出口 IP: 1.2.3.4" in captured["message"]
    assert "masked_proxy_url: socks5://demo:***@10.0.0.9:1080" in captured["details"]


def test_ip_pool_tab_test_entry_uses_public_progress_dialog(qtbot, monkeypatch):
    import src.core.rem.ui.ip_pool_tab as ip_pool_tab

    monkeypatch.setattr(ip_pool_tab.IPPoolTab, "load_data", lambda self: None)

    widget = ip_pool_tab.IPPoolTab()
    qtbot.addWidget(widget)
    pool = _build_pool()
    widget._current_pool = pool

    opened: list[tuple[str, str, bool]] = []
    closed: list[str] = []

    class FakeProgressDialog:
        def close_progress(self):
            closed.append("closed")

    def fake_open_progress(parent, title, message, *, modal=False):
        assert parent is widget
        opened.append((title, message, modal))
        return FakeProgressDialog()

    monkeypatch.setattr(ip_pool_tab.ProgressDialog, "open_progress", staticmethod(fake_open_progress))
    monkeypatch.setattr(widget, "_show_probe_result", lambda _result: None)

    widget._test_entry("entry-1")

    assert opened == [("代理测试中", "正在测试 1.1.1.1:8080，请稍候...", False)]
    assert widget._progress_dialog is not None

    widget._on_entry_test_finished(
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

    assert closed == ["closed"]
    assert widget._progress_dialog is None

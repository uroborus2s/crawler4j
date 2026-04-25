from types import SimpleNamespace

from PyQt6.QtCore import Qt

from src.core.rem.ui.import_existing_env_dialog import ImportExistingEnvDialog


def _make_workflow(name: str, *, supported: bool):
    return SimpleNamespace(
        name=name,
        display_name=name.replace("_", " ").title(),
        host_scenarios=["existing_env_import"] if supported else [],
    )


def _make_module():
    return SimpleNamespace(
        name="demo_module",
        manifest=SimpleNamespace(
            display_name="Demo Module",
            workflows=[
                _make_workflow("unsafe_flow", supported=False),
                _make_workflow("safe_flow", supported=True),
            ],
        ),
    )


def _make_provider_env():
    return SimpleNamespace(
        external_id="vb-101",
        name="VB Env 101",
        remark="demo",
        proxy_summary_text="SOCKS5 127.0.0.1:1080",
        running_status="运行中",
        last_used_at=1_746_000_000,
    )


def test_import_existing_env_dialog_updates_warning_and_returns_selection(qtbot):
    dialog = ImportExistingEnvDialog(
        sources=[{"provider": "virtualbrowser", "label": "Virtual Browser"}],
        modules=[_make_module()],
        env_options_by_source={"virtualbrowser": [_make_provider_env()]},
    )
    qtbot.addWidget(dialog)
    dialog.resize(1200, 800)
    dialog.show()

    qtbot.waitUntil(lambda: len(dialog.table.displayed_rows()) == 1, timeout=500)
    assert dialog.warning_label.text() == dialog.RISK_WARNING_TEXT
    margins = dialog.warning_card.layout().contentsMargins()
    assert margins.top() == 10
    assert margins.bottom() == 10
    assert "border: none" in dialog.warning_label.styleSheet()
    assert "background: transparent" in dialog.warning_label.styleSheet()
    qtbot.waitUntil(
        lambda: dialog.warning_label.height()
        >= dialog.warning_label.heightForWidth(dialog.warning_card.contentsRect().width()),
        timeout=500,
    )
    assert dialog.warning_card.height() >= (
        dialog.warning_label.heightForWidth(dialog.warning_card.contentsRect().width())
        + margins.top()
        + margins.bottom()
    )
    assert dialog.submit_btn.isEnabled() is False

    dialog.workflow_combo.setCurrentIndex(1)
    assert dialog.warning_label.text() == dialog.RISK_SAFE_TEXT

    qtbot.waitUntil(lambda: len(dialog.table.displayed_rows()) == 1, timeout=500)
    row = dialog.table.displayed_rows()[0]
    dialog._on_table_row_clicked(row)

    values = dialog.get_values()
    assert values == {
        "provider": "virtualbrowser",
        "module_name": "demo_module",
        "workflow_name": "safe_flow",
        "name": "VB Env 101",
    }
    assert dialog.submit_btn.isEnabled() is True


def test_import_existing_env_dialog_keeps_native_title_bar(qtbot):
    dialog = ImportExistingEnvDialog(
        sources=[{"provider": "virtualbrowser", "label": "Virtual Browser"}],
        modules=[_make_module()],
        env_options_by_source={"virtualbrowser": [_make_provider_env()]},
    )
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "从已有环境导入"
    assert dialog.windowFlags() & Qt.WindowType.Window
    assert dialog.windowFlags() & Qt.WindowType.WindowTitleHint
    assert not dialog.windowFlags() & Qt.WindowType.FramelessWindowHint

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


def _make_job(job_id: str, workflow_name: str):
    return SimpleNamespace(
        id=job_id,
        name=job_id.replace("-", " ").title(),
        concurrency_target=2,
        run_profile=SimpleNamespace(
            execution=SimpleNamespace(module="demo_module", workflow=workflow_name)
        ),
    )


def _make_provider_env(name: str = "VB Env 101", external_id: str = "vb-101"):
    return SimpleNamespace(
        external_id=external_id,
        name=name,
        remark="demo",
        proxy_summary_text="SOCKS5 127.0.0.1:1080",
        running_status="运行中",
        last_used_at=1_746_000_000,
    )


def test_import_existing_env_dialog_updates_warning_and_returns_selection(qtbot):
    dialog = ImportExistingEnvDialog(
        sources=[{"provider": "virtualbrowser", "label": "Virtual Browser"}],
        modules=[_make_module()],
        jobs=[
            _make_job("job-unsafe", "unsafe_flow"),
            _make_job("job-safe", "safe_flow"),
        ],
        env_options_by_source={"virtualbrowser": [_make_provider_env()]},
    )
    qtbot.addWidget(dialog)
    dialog.resize(1200, 800)
    dialog.show()

    assert dialog.job_combo.count() == 1
    assert dialog.job_combo.currentData() == "job-safe"
    qtbot.waitUntil(lambda: len(dialog.table.displayed_rows()) == 1, timeout=500)
    assert dialog.warning_label.text() == dialog.RISK_SAFE_TEXT
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

    qtbot.waitUntil(lambda: len(dialog.table.displayed_rows()) == 1, timeout=500)
    row = dialog.table.displayed_rows()[0]
    dialog._on_table_row_clicked(row)

    values = dialog.get_values()
    assert values == {
        "provider": "virtualbrowser",
        "job_id": "job-safe",
        "names": ["VB Env 101"],
    }
    assert dialog.submit_btn.isEnabled() is True


def test_import_existing_env_dialog_filters_out_non_import_workflow_jobs(qtbot):
    dialog = ImportExistingEnvDialog(
        sources=[{"provider": "virtualbrowser", "label": "Virtual Browser"}],
        modules=[_make_module()],
        jobs=[_make_job("job-unsafe", "unsafe_flow")],
        env_options_by_source={"virtualbrowser": [_make_provider_env()]},
    )
    qtbot.addWidget(dialog)

    assert dialog.job_combo.count() == 0
    qtbot.waitUntil(lambda: len(dialog.table.displayed_rows()) == 1, timeout=500)
    row = dialog.table.displayed_rows()[0]
    dialog._on_table_row_clicked(row)

    assert dialog.get_values()["job_id"] == ""
    assert dialog.submit_btn.isEnabled() is False


def test_import_existing_env_dialog_row_click_preserves_multi_selection(qtbot, monkeypatch):
    dialog = ImportExistingEnvDialog(
        sources=[{"provider": "virtualbrowser", "label": "Virtual Browser"}],
        modules=[_make_module()],
        jobs=[_make_job("job-safe", "safe_flow")],
        env_options_by_source={
            "virtualbrowser": [
                _make_provider_env(),
                _make_provider_env(name="VB Env 102", external_id="vb-102"),
            ]
        },
    )
    qtbot.addWidget(dialog)

    qtbot.waitUntil(lambda: len(dialog.table.displayed_rows()) == 2, timeout=500)
    rows = dialog.table.displayed_rows()
    monkeypatch.setattr(dialog.table, "selected_rows", lambda: rows)

    dialog._on_table_row_clicked(rows[0])

    assert dialog.get_values()["names"] == ["VB Env 101", "VB Env 102"]
    assert dialog.selection_label.text() == "未同步环境列表：已选择 2 个环境"


def test_import_existing_env_dialog_keeps_native_title_bar(qtbot):
    dialog = ImportExistingEnvDialog(
        sources=[{"provider": "virtualbrowser", "label": "Virtual Browser"}],
        modules=[_make_module()],
        jobs=[_make_job("job-safe", "safe_flow")],
        env_options_by_source={"virtualbrowser": [_make_provider_env()]},
    )
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "从已有环境导入"
    assert dialog.windowFlags() & Qt.WindowType.Window
    assert dialog.windowFlags() & Qt.WindowType.WindowTitleHint
    assert not dialog.windowFlags() & Qt.WindowType.FramelessWindowHint

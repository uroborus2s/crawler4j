from types import SimpleNamespace

from src.core.atm.run_profile import (
    AcquisitionMode,
    ComparisonOp,
    LogicOp,
    MatchCondition,
)


def _patch_dialog_dependencies(monkeypatch):
    import src.core.atm.ui.run_profile_dialog as dialog_module

    module = SimpleNamespace(
        name="demo_module",
        manifest=SimpleNamespace(
            workflows=[
                SimpleNamespace(name="repair"),
                SimpleNamespace(name="collect"),
            ]
        ),
    )
    registry = SimpleNamespace(
        list_modules=lambda: [module],
        get_module=lambda name: module if name == "demo_module" else None,
        refresh=lambda: None,
    )
    pool = SimpleNamespace(id="pool-1", name="主池")

    monkeypatch.setattr(dialog_module, "get_module_registry", lambda: registry)
    monkeypatch.setattr(
        dialog_module,
        "get_ip_pool_manager",
        lambda: SimpleNamespace(list_pools=lambda: [pool]),
    )


def test_run_profile_dialog_builds_create_mode_profile(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.module_link_combo.setCurrentIndex(dialog.module_link_combo.findData("demo_module"))
    dialog.resource_mode_combo.setCurrentIndex(dialog.resource_mode_combo.findData(AcquisitionMode.CREATE))
    dialog.resource_provider_combo.setCurrentText("virtualbrowser")
    dialog.fingerprint_params_edit.setPlainText("randomize_all: true")
    dialog.ip_binding_combo.setCurrentText("从 IP 池绑定")
    dialog.exec_workflow_selector.set_value("demo_module", "repair")

    profile = dialog._build_run_profile_from_form()

    assert profile.resource.acquisition.mode == AcquisitionMode.CREATE
    assert profile.resource.provider == "virtualbrowser"
    assert profile.resource.acquisition.creation.params["fingerprint"]["randomize_all"] is True
    assert profile.resource.acquisition.creation.params["proxy"] == {
        "mode": "pool",
        "pool_id": "pool-1",
    }
    assert profile.execution is not None
    assert profile.execution.module == "demo_module"
    assert profile.execution.workflow == "repair"


def test_run_profile_dialog_builds_match_mode_profile(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.resource_mode_combo.setCurrentIndex(dialog.resource_mode_combo.findData(AcquisitionMode.MATCH))
    dialog.resource_provider_combo.setCurrentText("bitbrowser")
    dialog.match_mode_combo.setCurrentIndex(dialog.match_mode_combo.findData(LogicOp.OR))
    dialog.rule_builder.root_widget._add_rule(
        MatchCondition(field="provider", op=ComparisonOp.EQ, value="bitbrowser")
    )
    dialog.rule_builder.root_widget._add_rule(
        MatchCondition(field="name", op=ComparisonOp.CONTAINS, value="shared")
    )

    profile = dialog._build_run_profile_from_form()

    assert profile.resource.acquisition.mode == AcquisitionMode.MATCH
    assert profile.resource.provider == "bitbrowser"
    assert profile.resource.acquisition.selector.match_rules is not None
    assert profile.resource.acquisition.selector.match_rules.logic == LogicOp.OR
    assert [condition.field for condition in profile.resource.acquisition.selector.match_rules.conditions] == [
        "provider",
        "name",
    ]

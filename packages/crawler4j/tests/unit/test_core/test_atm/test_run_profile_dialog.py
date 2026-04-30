import re
from types import SimpleNamespace

import pytest
from PyQt6.QtWidgets import QDialog

from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    CreationConfig,
    CreationLifecycle,
    ExecutionContext,
    EnvType,
    ResourceConfig,
    RunProfile,
)
from src.ui.components.button import StyledButton
from src.ui.components.check_box import StyledCheckBox, ToggleSwitch
from src.ui.components.combo_box import StyledComboBox
from src.ui.components.line_edit import StyledLineEdit
from src.ui.components.spin_box import StyledDoubleSpinBox, StyledSpinBox
from src.ui.components.text_edit import StyledPlainTextEdit
from src.ui.components.yaml_code_editor import YamlCodeEditor


def _candidate_descriptor(*entries: tuple[str, str]):
    return SimpleNamespace(
        env_candidates={
            name: SimpleNamespace(meta=SimpleNamespace(label=label))
            for name, label in entries
        }
    )


def _patch_dialog_dependencies(monkeypatch):
    import src.core.atm.ui.run_profile_dialog as dialog_module

    workflows = [
        SimpleNamespace(name="repair", display_name="修复流程"),
        SimpleNamespace(name="collect", display_name=""),
    ]
    module = SimpleNamespace(
        name="demo_module",
        manifest=SimpleNamespace(),
    )
    registry = SimpleNamespace(
        list_modules=lambda: [module],
        get_module=lambda name: module if name == "demo_module" else None,
        get_workflows=lambda name: workflows if name == "demo_module" else [],
        refresh=lambda: None,
    )
    pool = SimpleNamespace(id="pool-1", name="主池")

    monkeypatch.setattr(dialog_module, "get_module_registry", lambda: registry)
    monkeypatch.setattr(
        dialog_module,
        "get_module_service",
        lambda: SimpleNamespace(
            get_runtime_descriptor_v2=lambda name: _candidate_descriptor(
                ("bound_account_ready", "已绑定账号环境池")
            )
        ),
    )
    monkeypatch.setattr(
        dialog_module,
        "get_ip_pool_manager",
        lambda: SimpleNamespace(list_pools=lambda: [pool]),
    )


def _patch_ctrip_dialog_dependencies(monkeypatch):
    import src.core.atm.ui.run_profile_dialog as dialog_module

    workflows = [
        SimpleNamespace(name="web_quiz_workflow", display_name="网页做题"),
    ]
    module = SimpleNamespace(
        name="ctrip_crawler",
        manifest=SimpleNamespace(),
    )
    registry = SimpleNamespace(
        list_modules=lambda: [module],
        get_module=lambda name: module if name == "ctrip_crawler" else None,
        get_workflows=lambda name: workflows if name == "ctrip_crawler" else [],
        refresh=lambda: None,
    )
    pool = SimpleNamespace(id="pool-1", name="主池")

    monkeypatch.setattr(dialog_module, "get_module_registry", lambda: registry)
    monkeypatch.setattr(
        dialog_module,
        "get_module_service",
        lambda: SimpleNamespace(
            get_runtime_descriptor_v2=lambda name: _candidate_descriptor(
                ("bound_account_ready", "已绑定账号环境池")
            )
        ),
    )
    monkeypatch.setattr(
        dialog_module,
        "get_ip_pool_manager",
        lambda: SimpleNamespace(list_pools=lambda: [pool]),
    )


def _object_assembly_descriptor():
    def inject(name: str, inject_type: str, target: str):
        return SimpleNamespace(name=name, type=inject_type, target=target)

    def parameter(name: str, parameter_type: str, **kwargs):
        return SimpleNamespace(name=name, type=parameter_type, **kwargs)

    def option(label: str, value: object):
        return SimpleNamespace(label=label, value=value)

    def entry(
        name: str,
        *,
        kind: str,
        label: str = "",
        implements: str = "",
        inject_specs: tuple[object, ...] = (),
        parameters: tuple[object, ...] = (),
    ):
        return SimpleNamespace(
            meta=SimpleNamespace(
                kind=kind,
                name=name,
                label=label,
                implements=implements,
                inject=inject_specs,
                parameters=parameters,
            )
        )

    return SimpleNamespace(
        interfaces={
            "orchestrator": entry("orchestrator", kind="interface", label="Orchestrator"),
            "labor": entry("labor", kind="interface", label="Labor"),
        },
        components={
            "quiz_orchestrator": entry(
                "quiz_orchestrator",
                kind="component",
                label="Quiz Orchestrator",
                implements="orchestrator",
                inject_specs=(inject("labor", "interface", "labor"),),
            ),
            "api_labor": entry(
                "api_labor",
                kind="component",
                label="API Labor",
                implements="labor",
                parameters=(
                    parameter("base_url", "string", label="Base URL", required=True, default="https://api.example.com"),
                    parameter("timeout", "integer", label="Timeout", default=30, min=1, max=120, step=1),
                    parameter(
                        "mode",
                        "enum",
                        label="Mode",
                        default="sync",
                        options=(option("Sync", "sync"), option("Async", "async")),
                    ),
                    parameter("enabled", "boolean", label="Enabled", default=True),
                    parameter("notes", "text", label="Notes", default=""),
                    parameter("ratio", "number", label="Ratio", default=0.5, min=0, max=1, step=0.1),
                    parameter("raw_payload", "json", label="Raw Payload", default='{"limit": 10}'),
                ),
            ),
            "local_labor": entry(
                "local_labor",
                kind="component",
                label="Local Labor",
                implements="labor",
            ),
        },
        workflows={
            "quiz_workflow": entry(
                "quiz_workflow",
                kind="workflow",
                label="统一做题",
                inject_specs=(inject("orchestrator", "interface", "orchestrator"),),
                parameters=(
                    parameter("member_tier", "enum", label="会员类型", default="normal"),
                ),
            ),
        },
        env_candidates={
            "ctrip_account_pool": SimpleNamespace(meta=SimpleNamespace(label="携程账号环境池")),
        },
        implementations={
            "orchestrator": ("quiz_orchestrator",),
            "labor": ("api_labor", "local_labor"),
        },
    )


def _patch_parameterized_dialog_dependencies(monkeypatch):
    import src.core.atm.ui.run_profile_dialog as dialog_module

    workflow = SimpleNamespace(
        name="quiz_workflow",
        display_name="统一做题",
        parameters=[
            SimpleNamespace(
                name="member_tier",
                label="会员类型",
                type="enum",
                required=True,
                default="normal",
                options=[
                    SimpleNamespace(label="普通会员", value="normal"),
                    SimpleNamespace(label="高级会员", value="premium"),
                ],
            ),
            SimpleNamespace(
                name="min_member_days",
                label="会员天数下限",
                type="integer",
                default=30,
                min=0,
                max=365,
                step=1,
            ),
            SimpleNamespace(
                name="pass_score",
                label="通过分数",
                type="number",
                default=90.5,
                min=0,
                max=100,
                step=0.5,
            ),
            SimpleNamespace(
                name="dry_run",
                label="试运行",
                type="boolean",
                default=False,
            ),
            SimpleNamespace(
                name="remark",
                label="备注",
                type="string",
                default="普通会员30-90天",
                placeholder="模板备注",
            ),
            SimpleNamespace(
                name="instructions",
                label="执行说明",
                type="text",
                default="",
            ),
        ],
    )
    module = SimpleNamespace(
        name="ctrip_crawler",
        manifest=SimpleNamespace(),
    )
    registry = SimpleNamespace(
        list_modules=lambda: [module],
        get_module=lambda name: module if name == "ctrip_crawler" else None,
        get_workflows=lambda name: [workflow] if name == "ctrip_crawler" else [],
        refresh=lambda: None,
    )

    monkeypatch.setattr(dialog_module, "get_module_registry", lambda: registry)
    monkeypatch.setattr(
        dialog_module,
        "get_module_service",
        lambda: SimpleNamespace(
            get_runtime_descriptor_v2=lambda name: _object_assembly_descriptor()
        ),
    )
    monkeypatch.setattr(
        dialog_module,
        "get_ip_pool_manager",
        lambda: SimpleNamespace(list_pools=lambda: []),
    )



def test_run_profile_dialog_builds_create_mode_profile(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    assert dialog.form_tabs.count() == 1

    dialog.script_selector.set_value("demo_module", "repair")
    dialog.resource_mode_combo.setCurrentIndex(dialog.resource_mode_combo.findData(AcquisitionMode.CREATE))
    dialog.resource_provider_combo.setCurrentText("virtualbrowser")
    dialog.browser_version_combo.setCurrentText("144")
    dialog.randomize_fingerprint_check.setChecked(True)
    dialog.ua_custom_btn.click()
    dialog.ua_value_edit.setPlainText("Mozilla/5.0 Test")
    dialog._set_sec_ch_ua_mode("custom")
    dialog._sec_ch_ua_rows[0].brand_edit.setText("Chromium")
    dialog._sec_ch_ua_rows[0].version_edit.setText("144")
    dialog._sec_ch_ua_rows[1].brand_edit.setText("Not=A?Brand")
    dialog._sec_ch_ua_rows[1].version_edit.setText("99")
    dialog.language_follow_ip_check.setChecked(False)
    dialog.timezone_follow_ip_check.setChecked(False)
    language_index = dialog._find_combo_index(
        dialog.language_combo,
        lambda data: isinstance(data, dict) and data.get("language") == "en-US",
    )
    dialog.language_combo.setCurrentIndex(language_index)
    timezone_index = dialog._find_combo_index(
        dialog.timezone_combo,
        lambda data: isinstance(data, dict) and data.get("utc") == "Asia/Hong_Kong",
    )
    dialog.timezone_combo.setCurrentIndex(timezone_index)
    dialog._set_combo_value(dialog.fonts_mode_combo, "random")
    dialog._set_combo_value(dialog.screen_mode_combo, "custom")
    dialog._set_screen_resolution((1920, 1080))
    dialog._set_combo_value(dialog.canvas_mode_combo, "random")
    dialog._set_combo_value(dialog.webgl_mode_combo, "custom")
    dialog.webgl_vendor_combo.setCurrentText("Google Inc. (Intel Inc.)")
    dialog.webgl_renderer_combo.setCurrentText(
        "ANGLE (Intel Inc., Intel(R) Iris(TM) Plus Graphics OpenGL Engine (1x6x8 (fused) LP, OpenGL 4.1)"
    )
    dialog._set_combo_value(dialog.webgpu_mode_combo, "based_on_webgl")
    dialog.ip_binding_combo.setCurrentText("从 IP 池绑定")
    dialog.ip_pool_strategy_combo.setCurrentText("最少绑定数")

    profile = dialog._build_run_profile_from_form()

    assert profile.resource.acquisition.mode == AcquisitionMode.CREATE
    assert profile.resource.acquisition.provider == "virtualbrowser"
    assert profile.resource.acquisition.env_type == EnvType.VIRTUAL_BROWSER
    assert profile.resource.acquisition.creation.lifecycle == CreationLifecycle.PERSISTENT
    virtualbrowser = profile.resource.acquisition.creation.params["virtualbrowser"]
    assert virtualbrowser["chrome_version"] == 144
    assert virtualbrowser["__randomize_fingerprint__"] is True
    assert virtualbrowser["fonts"] == {"mode": 1}
    assert virtualbrowser["canvas"] == {"mode": 1}
    assert virtualbrowser["webgl-img"] == {"mode": 1}
    assert "ua" not in virtualbrowser
    assert "device-name" not in virtualbrowser
    assert "mac" not in virtualbrowser
    assert virtualbrowser["sec-ch-ua"]["value"] == '"Chromium";v="144", "Not=A?Brand";v="99"'
    assert virtualbrowser["webgl"] == {
        "mode": 1,
        "vendor": "Google Inc. (Intel Inc.)",
        "render": "ANGLE (Intel Inc., Intel(R) Iris(TM) Plus Graphics OpenGL Engine (1x6x8 (fused) LP, OpenGL 4.1)",
    }

    assert virtualbrowser["media"] == {"mode": 1}
    assert virtualbrowser["ua-language"] == {
        "mode": 1,
        "language": "en-US",
        "value": "en-US,en",
    }
    assert virtualbrowser["time-zone"] == {
        "mode": 1,
        "zone": "(UTC+08:00) Asia/Hong_Kong",
        "utc": "Asia/Hong_Kong",
        "locale": "en-US",
        "value": 8,
    }
    assert virtualbrowser["screen"] == {
        "mode": 1,
        "width": 1920,
        "height": 1080,
        "_value": "1920 x 1080",
    }
    assert profile.resource.acquisition.creation.params["proxy"] == {
        "mode": "pool",
        "pool_id": "pool-1",
        "bind_strategy": "least_bound",
    }
    assert profile.execution is not None
    assert profile.execution.module == "demo_module"
    assert profile.execution.workflow == "repair"


def test_run_profile_dialog_yaml_tab_uses_shared_yaml_editor(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    assert isinstance(dialog.yaml_editor, YamlCodeEditor)
    assert dialog.yaml_editor.styleSheet() == ""


def test_run_profile_dialog_removes_creation_lifecycle_control(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    assert hasattr(dialog, "creation_lifecycle_combo") is False


def test_run_profile_dialog_requires_script_selection(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    with pytest.raises(ValueError, match="请选择执行脚本"):
        dialog._build_run_profile_from_form()


def test_run_profile_dialog_script_selector_shows_display_name_but_returns_name(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.script_selector.set_value("demo_module", "repair")

    assert dialog.script_selector.workflow_combo.currentText() == "修复流程"
    assert dialog.script_selector.get_value() == ("demo_module", "repair")

    dialog.script_selector.set_value("demo_module", "collect")

    assert dialog.script_selector.workflow_combo.currentText() == "collect"
    assert dialog.script_selector.get_value() == ("demo_module", "collect")


def test_run_profile_dialog_script_selector_has_no_blank_module_option(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    assert dialog.script_selector.module_combo.count() == 1
    assert dialog.script_selector.module_combo.itemText(0) == "demo_module"
    assert dialog.script_selector.module_combo.currentIndex() == -1
    assert dialog.script_selector.get_value() == ("", "")


def test_run_profile_dialog_builds_select_mode_profile(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.script_selector.set_value("demo_module", "collect")
    dialog.resource_mode_combo.setCurrentIndex(dialog.resource_mode_combo.findData(AcquisitionMode.SELECT))
    dialog.candidates_combo.setCurrentIndex(dialog.candidates_combo.findData("bound_account_ready"))

    profile = dialog._build_run_profile_from_form()

    assert profile.resource.acquisition.mode == AcquisitionMode.SELECT
    assert profile.resource.acquisition.candidates == "bound_account_ready"
    assert "selector_name" not in profile.resource.acquisition.model_dump()
    assert profile.resource.acquisition.provider == ""
    assert profile.resource.acquisition.wait_timeout == 60


def test_run_profile_dialog_separates_execution_timeout_from_wait_timeout(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.script_selector.set_value("demo_module", "collect")
    dialog.resource_mode_combo.setCurrentIndex(dialog.resource_mode_combo.findData(AcquisitionMode.SELECT))
    dialog.candidates_combo.setCurrentIndex(dialog.candidates_combo.findData("bound_account_ready"))
    dialog.wait_timeout_spin.setValue(30)
    dialog.execution_timeout_spin.setValue(0)

    profile = dialog._build_run_profile_from_form()

    assert profile.resource.acquisition.wait_timeout == 30
    assert profile.execution.timeout == 0


def test_run_profile_dialog_builds_candidate_select_profile_without_selector(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.script_selector.set_value("demo_module", "collect")
    dialog.resource_mode_combo.setCurrentIndex(dialog.resource_mode_combo.findData(AcquisitionMode.SELECT))
    dialog.candidates_combo.setCurrentIndex(dialog.candidates_combo.findData("bound_account_ready"))

    profile = dialog._build_run_profile_from_form()

    assert profile.resource.acquisition.mode == AcquisitionMode.SELECT
    assert "selector_name" not in profile.resource.acquisition.model_dump()
    assert profile.resource.acquisition.candidates == "bound_account_ready"
    assert profile.resource.acquisition.provider == ""


def test_run_profile_dialog_lists_declared_env_candidates(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.script_selector.set_value("demo_module", "collect")

    assert dialog.candidates_combo.isEnabled() is True
    assert dialog.candidates_combo.findData("") == -1
    candidate_index = dialog.candidates_combo.findData("bound_account_ready")
    assert candidate_index >= 0
    assert dialog.candidates_combo.itemText(candidate_index) == "已绑定账号环境池 (bound_account_ready)"


def test_run_profile_dialog_select_mode_has_no_selector_controls(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    assert not hasattr(dialog, "selector_name_combo")
    assert not hasattr(dialog, "selector_none_hint")
    assert not hasattr(dialog, "selector_empty_hint")


def test_run_profile_dialog_selects_declared_candidate_without_legacy_selector(qtbot, monkeypatch):
    _patch_ctrip_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.script_selector.set_value("ctrip_crawler", "web_quiz_workflow")
    dialog.resource_mode_combo.setCurrentIndex(dialog.resource_mode_combo.findData(AcquisitionMode.SELECT))

    profile = dialog._build_run_profile_from_form()

    assert profile.resource.acquisition.candidates == "bound_account_ready"
    assert "selector_name" not in profile.resource.acquisition.model_dump()


def test_run_profile_dialog_rejects_undeclared_env_candidates(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.script_selector.set_value("demo_module", "collect")
    dialog.resource_mode_combo.setCurrentIndex(dialog.resource_mode_combo.findData(AcquisitionMode.SELECT))
    dialog.candidates_combo.addItem("missing_candidates", "missing_candidates")
    dialog.candidates_combo.setCurrentIndex(dialog.candidates_combo.findData("missing_candidates"))

    with pytest.raises(ValueError, match="环境候选函数未声明"):
        dialog._build_run_profile_from_form()


def test_run_profile_dialog_randomizes_user_agent_with_selected_version(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.browser_version_combo.setCurrentText("146")
    dialog.ua_random_btn.click()

    assert dialog.ua_custom_btn.isChecked()
    assert "Chrome/146.0.0.0" in dialog.ua_value_edit.toPlainText()


def test_run_profile_dialog_uses_segmented_controls_for_virtualbrowser_modes(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog, SegmentedOptionControl

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    assert isinstance(dialog.webrtc_mode_combo, SegmentedOptionControl)
    assert isinstance(dialog.location_permission_combo, SegmentedOptionControl)
    assert isinstance(dialog.screen_mode_combo, SegmentedOptionControl)
    assert isinstance(dialog.fonts_mode_combo, SegmentedOptionControl)

    dialog.screen_mode_combo.set_current_data("custom", emit_change=True)
    assert dialog.screen_mode_combo.currentData() == "custom"
    assert dialog.screen_resolution_combo.isHidden() is False


def test_run_profile_dialog_uses_toggle_switch_for_boolean_fields(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog, ToggleSwitch

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    assert isinstance(dialog.dnt_check, ToggleSwitch)
    assert isinstance(dialog.hardware_accel_check, ToggleSwitch)
    assert dialog.dnt_check.width() == 54
    assert dialog.dnt_check.height() == 30


def test_run_profile_dialog_toggle_switch_click_updates_state(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    assert dialog.dnt_check.isChecked() is False
    assert dialog.hardware_accel_check.isChecked() is True

    dialog.dnt_check.click()
    dialog.hardware_accel_check.click()

    assert dialog.dnt_check.isChecked() is True
    assert dialog.hardware_accel_check.isChecked() is False


def test_run_profile_dialog_uses_public_buttons_and_inputs(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    assert isinstance(dialog.form_btn, StyledButton)
    assert isinstance(dialog.yaml_btn, StyledButton)
    assert isinstance(dialog.ua_default_btn, StyledButton)
    assert isinstance(dialog.ua_custom_btn, StyledButton)
    assert isinstance(dialog.ua_random_btn, StyledButton)
    assert isinstance(dialog.ua_value_edit, StyledPlainTextEdit)
    assert isinstance(dialog.launch_args_edit, StyledPlainTextEdit)
    assert isinstance(dialog.language_follow_ip_check, StyledCheckBox)
    assert isinstance(dialog.timezone_follow_ip_check, StyledCheckBox)
    assert isinstance(dialog.location_follow_ip_check, StyledCheckBox)
    assert isinstance(dialog.randomize_fingerprint_check, StyledCheckBox)


def test_run_profile_dialog_defaults_new_create_mode_to_random_fingerprint(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.wait(50)

    assert dialog.randomize_fingerprint_check.isChecked() is True
    assert dialog.ua_custom_btn.isChecked() is True
    assert dialog.ua_value_edit.height() >= 156
    assert "Chrome/145.0.0.0" in dialog.ua_value_edit.toPlainText()
    assert dialog.audio_context_mode_combo.currentData() == "random"
    assert dialog.client_rects_mode_combo.currentData() == "random"
    assert dialog.speech_voices_mode_combo.currentData() == "random"
    assert dialog.fonts_mode_combo.currentData() == "random"
    assert dialog.canvas_mode_combo.currentData() == "random"
    assert dialog.webgl_image_mode_combo.currentData() == "random"
    assert dialog.cpu_value_spin.value() == 4
    assert dialog.memory_value_spin.value() == 8
    assert dialog.device_name_mode_combo.currentData() == "custom"
    assert re.fullmatch(r"[A-Z0-9]{18}", dialog.device_name_edit.text())
    assert not dialog.device_name_input_widget.isHidden()
    assert dialog.mac_mode_combo.currentData() == "custom"
    assert dialog.mac_value_edit.text()
    assert not dialog.mac_input_widget.isHidden()
    assert dialog.dnt_check.isChecked() is False
    assert dialog.ssl_mode_combo.currentData() == "disabled"
    assert dialog.port_scan_protect_mode_combo.currentData() == "disabled"
    assert dialog.port_scan_whitelist_edit.isHidden()
    assert dialog.hardware_accel_check.isChecked() is True
    assert dialog.launch_args_mode_combo.currentData() == "default"
    assert dialog.launch_args_edit.isHidden()

    dialog.script_selector.set_value("demo_module", "repair")
    profile = dialog._build_run_profile_from_form()
    virtualbrowser = profile.resource.acquisition.creation.params["virtualbrowser"]
    assert virtualbrowser["__randomize_fingerprint__"] is True
    assert virtualbrowser["fonts"] == {"mode": 1}
    assert virtualbrowser["canvas"] == {"mode": 1}
    assert virtualbrowser["webgl-img"] == {"mode": 1}
    assert virtualbrowser["audio-context"] == {"mode": 1}
    assert virtualbrowser["client-rects"] == {"mode": 1}
    assert virtualbrowser["speech_voices"] == {"mode": 1}
    assert virtualbrowser["memory"] == {"mode": 1, "value": 8}
    assert "ua" not in virtualbrowser
    assert "device-name" not in virtualbrowser
    assert "mac" not in virtualbrowser
    assert "__randomize_after_create__" not in virtualbrowser
    assert "dnt" not in virtualbrowser
    assert "ssl" not in virtualbrowser
    assert "port-scan" not in virtualbrowser
    assert "gpu" not in virtualbrowser
    assert "launchArgs" not in virtualbrowser


def test_run_profile_dialog_loads_virtualbrowser_dropdown_values(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    run_profile = RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                provider="virtualbrowser",
                env_type=EnvType.VIRTUAL_BROWSER,
                wait_timeout=60,
                creation=CreationConfig(
                    lifecycle=CreationLifecycle.EPHEMERAL,
                    params={
                        "virtualbrowser": {
                            "chrome_version": 145,
                            "sec-ch-ua": {
                                "mode": 1,
                                "value": '"Chromium";v="145", "Not=A?Brand";v="99"',
                            },
                            "ua-language": {
                                "mode": 1,
                                "language": "en-US",
                                "value": "en-US,en",
                            },
                            "time-zone": {
                                "mode": 1,
                                "zone": "(UTC+08:00) Asia/Hong_Kong",
                                "utc": "Asia/Hong_Kong",
                                "locale": "en-US",
                                "value": 8,
                            },
                            "screen": {
                                "mode": 1,
                                "width": 1920,
                                "height": 1080,
                                "_value": "1920 x 1080",
                            },
                            "webgl": {
                                "mode": 1,
                                "vendor": "Google Inc. (Intel Inc.)",
                                "render": "ANGLE (Intel Inc., Intel(R) UHD Graphics 630, OpenGL 4.1)",
                            },
                            "fonts": {"mode": 1},
                            "canvas": {"mode": 1},
                            "webgl-img": {"mode": 1},
                            "media": {"mode": 1},
                            "audio-context": {"mode": 1},
                            "client-rects": {"mode": 1},
                            "speech_voices": {"mode": 1},
                            "memory": {"mode": 1, "value": 8},
                            "__randomize_fingerprint__": True,
                            "device-name": {"mode": 1, "value": "A1B2C3D4E55F7A9C2"},
                            "mac": {"mode": 1, "value": "26-F6-CD-8F-DE-93"},
                            "dnt": {"mode": 1, "value": 1},
                            "ssl": {"mode": 1},
                            "port-scan": {"mode": 1, "value": ["22", "443"]},
                            "launchArgs": {"mode": 1, "value": "--disable-gpu"},
                            "gpu": {"mode": 1, "value": 0},
                        }
                    },
                ),
            ),
        ),
        execution=ExecutionContext(module="demo_module", workflow="repair"),
    )

    dialog = RunProfileDialog(run_profile=run_profile)
    qtbot.addWidget(dialog)

    assert dialog.sec_ch_ua_custom_btn.isChecked()
    assert len(dialog._sec_ch_ua_rows) == 2
    assert dialog._sec_ch_ua_rows[0].brand_edit.text() == "Chromium"
    assert dialog._sec_ch_ua_rows[0].version_edit.text() == "145"
    assert dialog.language_follow_ip_check.isChecked() is False
    assert dialog.timezone_follow_ip_check.isChecked() is False
    assert dialog.language_combo.currentData()["language"] == "en-US"
    assert dialog.timezone_combo.currentData()["utc"] == "Asia/Hong_Kong"
    assert dialog.screen_mode_combo.currentData() == "custom"
    assert dialog.screen_resolution_combo.currentData() == (1920, 1080)
    assert dialog.webgl_mode_combo.currentData() == "custom"
    assert dialog.webgl_vendor_combo.currentText() == "Google Inc. (Intel Inc.)"
    assert dialog.webgl_renderer_combo.currentText() == "ANGLE (Intel Inc., Intel(R) UHD Graphics 630, OpenGL 4.1)"
    assert dialog.webgpu_mode_combo.currentData() == "based_on_webgl"
    assert dialog.fonts_mode_combo.currentData() == "random"
    assert dialog.canvas_mode_combo.currentData() == "random"
    assert dialog.webgl_image_mode_combo.currentData() == "random"
    assert dialog.audio_context_mode_combo.currentData() == "random"
    assert dialog.client_rects_mode_combo.currentData() == "random"
    assert dialog.speech_voices_mode_combo.currentData() == "random"
    assert dialog.memory_value_spin.value() == 8
    assert dialog.randomize_fingerprint_check.isChecked() is True
    assert dialog.device_name_mode_combo.currentData() == "custom"
    assert dialog.device_name_edit.text() == "A1B2C3D4E55F7A9C2"
    assert dialog.mac_mode_combo.currentData() == "custom"
    assert dialog.mac_value_edit.text() == "26-F6-CD-8F-DE-93"
    assert dialog.dnt_check.isChecked() is True
    assert dialog.ssl_mode_combo.currentData() == "enabled"
    assert dialog.port_scan_protect_mode_combo.currentData() == "enabled"
    assert dialog.port_scan_whitelist_edit.text() == "22,443"
    assert dialog.hardware_accel_check.isChecked() is False
    assert dialog.launch_args_mode_combo.currentData() == "custom"
    assert dialog.launch_args_edit.toPlainText() == "--disable-gpu"


def test_run_profile_dialog_shows_webgl_vendor_and_renderer_only_in_custom_mode(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    assert dialog.webgl_vendor_combo.isHidden()
    assert dialog.webgl_renderer_combo.isHidden()

    dialog._set_combo_value(dialog.webgl_mode_combo, "custom")
    dialog._sync_virtualbrowser_field_visibility()

    assert not dialog.webgl_vendor_combo.isHidden()
    assert not dialog.webgl_renderer_combo.isHidden()


def test_run_profile_dialog_expands_webgl_renderer_dropdown_width(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog._set_combo_value(dialog.webgl_mode_combo, "custom")
    dialog.webgl_vendor_combo.setCurrentText("Google Inc. (Intel Inc.)")
    dialog._refresh_webgl_renderer_options()

    assert dialog.webgl_renderer_combo.minimumWidth() >= 420
    assert dialog.webgl_renderer_combo.view().minimumWidth() >= 760


def test_run_profile_dialog_ignores_legacy_randomize_after_create_flag(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    run_profile = RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.CREATE,
                provider="virtualbrowser",
                env_type=EnvType.VIRTUAL_BROWSER,
                wait_timeout=60,
                creation=CreationConfig(
                    lifecycle=CreationLifecycle.EPHEMERAL,
                    params={
                        "virtualbrowser": {
                            "__randomize_after_create__": True,
                            "chrome_version": 145,
                        }
                    },
                ),
            ),
        ),
        execution=ExecutionContext(module="demo_module", workflow="repair"),
    )

    dialog = RunProfileDialog(run_profile=run_profile)
    qtbot.addWidget(dialog)

    assert dialog.randomize_fingerprint_check.isChecked() is False
    assert dialog.ua_default_btn.isChecked() is True
    assert dialog.fonts_mode_combo.currentData() == "default"
    assert dialog.canvas_mode_combo.currentData() == "default"
    assert dialog.webgl_image_mode_combo.currentData() == "default"
    assert dialog.audio_context_mode_combo.currentData() == "default"
    assert dialog.client_rects_mode_combo.currentData() == "default"
    assert dialog.speech_voices_mode_combo.currentData() == "default"


def test_run_profile_dialog_uses_60_percent_screen_width(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    import src.core.atm.ui.run_profile_dialog as dialog_module
    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    fake_geometry = SimpleNamespace(width=lambda: 2000, height=lambda: 1000)
    fake_screen = SimpleNamespace(availableGeometry=lambda: fake_geometry)
    monkeypatch.setattr(dialog_module.QApplication, "primaryScreen", lambda: fake_screen)

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    assert dialog.width() == 1200
    assert dialog.height() == 950


def test_run_profile_dialog_keeps_dialog_open_when_yaml_is_invalid_on_save(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    import src.core.atm.ui.run_profile_dialog as dialog_module
    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)
    dialog.stack.setCurrentIndex(1)
    dialog.yaml_editor.setPlainText("resource: [")
    captured: list[tuple[object, str, str]] = []

    monkeypatch.setattr(
        dialog_module.MessageDialog,
        "warning",
        lambda parent, title, message, **kwargs: captured.append((parent, title, message)),
    )

    dialog._on_save()

    assert len(captured) == 1
    assert captured[0][0] is dialog
    assert captured[0][1] == "YAML 无效"
    assert dialog.result() != int(QDialog.DialogCode.Accepted)
    assert dialog.stack.currentIndex() == 1


def test_run_profile_dialog_renders_object_assembly_and_ignores_workflow_parameters(qtbot, monkeypatch):
    _patch_parameterized_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.script_selector.set_value("ctrip_crawler", "quiz_workflow")

    assert dialog.basic_group.title() == "一、模板信息"
    assert dialog.resource_group.title() == "二、环境与资源"
    assert not hasattr(dialog, "_workflow_param_widgets")
    assert "member_tier" not in dialog._object_param_widgets
    assert isinstance(dialog._object_binding_widgets["orchestrator"], StyledComboBox)
    assert isinstance(dialog._object_binding_widgets["orchestrator.labor"], StyledComboBox)
    assert isinstance(dialog._object_param_widgets["api_labor"]["base_url"], StyledLineEdit)
    assert isinstance(dialog._object_param_widgets["api_labor"]["timeout"], StyledSpinBox)
    assert isinstance(dialog._object_param_widgets["api_labor"]["ratio"], StyledDoubleSpinBox)
    assert isinstance(dialog._object_param_widgets["api_labor"]["enabled"], ToggleSwitch)
    assert isinstance(dialog._object_param_widgets["api_labor"]["mode"], StyledComboBox)
    assert isinstance(dialog._object_param_widgets["api_labor"]["notes"], StyledPlainTextEdit)
    assert isinstance(dialog._object_param_widgets["api_labor"]["raw_payload"], StyledLineEdit)

    labor_combo = dialog._object_binding_widgets["orchestrator.labor"]
    labor_combo.setCurrentIndex(labor_combo.findData("api_labor"))
    dialog._object_param_widgets["api_labor"]["base_url"].setText("https://labor.example.com")
    dialog._object_param_widgets["api_labor"]["timeout"].setValue(60)
    dialog._object_param_widgets["api_labor"]["ratio"].setValue(0.8)
    dialog._object_param_widgets["api_labor"]["enabled"].setChecked(False)
    dialog._object_param_widgets["api_labor"]["mode"].setCurrentIndex(
        dialog._object_param_widgets["api_labor"]["mode"].findData("async")
    )
    dialog._object_param_widgets["api_labor"]["notes"].setPlainText("只处理已绑定环境。")
    dialog._object_param_widgets["api_labor"]["raw_payload"].setText('{"limit": 20}')

    profile = dialog._build_run_profile_from_form()

    assert profile.execution is not None
    assert profile.execution.object_bindings == {
        "orchestrator": "quiz_orchestrator",
        "orchestrator.labor": "api_labor",
    }
    assert profile.execution.object_params == {
        "api_labor": {
            "base_url": "https://labor.example.com",
            "timeout": 60,
            "mode": "async",
            "enabled": False,
            "notes": "只处理已绑定环境。",
            "ratio": 0.8,
            "raw_payload": '{"limit": 20}',
        }
    }


def test_run_profile_dialog_loads_object_assembly_from_run_profile(qtbot, monkeypatch):
    _patch_parameterized_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    run_profile = RunProfile(
        resource=ResourceConfig(
            acquisition=AcquisitionConfig(
                mode=AcquisitionMode.SELECT,
                candidates="ctrip_account_pool",
            ),
        ),
        execution=ExecutionContext(
            module="ctrip_crawler",
            workflow="quiz_workflow",
            object_bindings={
                "orchestrator": "quiz_orchestrator",
                "orchestrator.labor": "api_labor",
            },
            object_params={
                "api_labor": {
                    "base_url": "https://saved.example.com",
                    "timeout": 75,
                    "mode": "async",
                    "enabled": False,
                    "notes": "优先处理普通会员。",
                    "ratio": 0.9,
                    "raw_payload": '{"limit": 30}',
                }
            },
        ),
    )

    dialog = RunProfileDialog(run_profile=run_profile)
    qtbot.addWidget(dialog)

    assert dialog._object_binding_widgets["orchestrator"].currentData() == "quiz_orchestrator"
    assert dialog._object_binding_widgets["orchestrator.labor"].currentData() == "api_labor"
    assert dialog._object_param_widgets["api_labor"]["base_url"].text() == "https://saved.example.com"
    assert dialog._object_param_widgets["api_labor"]["timeout"].value() == 75
    assert dialog._object_param_widgets["api_labor"]["mode"].currentData() == "async"
    assert dialog._object_param_widgets["api_labor"]["enabled"].isChecked() is False
    assert dialog._object_param_widgets["api_labor"]["notes"].toPlainText() == "优先处理普通会员。"
    assert dialog._object_param_widgets["api_labor"]["ratio"].value() == 0.9
    assert dialog._object_param_widgets["api_labor"]["raw_payload"].text() == '{"limit": 30}'

    profile = dialog._build_run_profile_from_form()

    assert profile.execution is not None

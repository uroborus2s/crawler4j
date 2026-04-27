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
from src.ui.components.yaml_code_editor import YamlCodeEditor


def _patch_dialog_dependencies(monkeypatch):
    import src.core.atm.ui.run_profile_dialog as dialog_module
    import src.core.atm.controller as controller_module

    module = SimpleNamespace(
        name="demo_module",
        manifest=SimpleNamespace(
            workflows=[
                SimpleNamespace(name="repair", display_name="修复流程"),
                SimpleNamespace(name="collect", display_name=""),
            ],
            resource_pools=[
                SimpleNamespace(name="bound_account_ready", display_name="已绑定账号环境池"),
            ],
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
    def module_service():
        return SimpleNamespace(
            list_env_selectors=lambda module_name: [
                SimpleNamespace(
                    name="return_none",
                    display_name="返回 None",
                    description="占位选择器",
                    returns_none=True,
                ),
                SimpleNamespace(
                    name="random_ready",
                    display_name="随机选择就绪环境",
                    description="随机选择已就绪环境",
                    returns_none=False,
                ),
            ]
            if module_name == "demo_module"
            else []
        )
    monkeypatch.setattr(dialog_module, "get_module_service", module_service)
    monkeypatch.setattr(controller_module, "get_module_service", module_service)


def _patch_ctrip_dialog_dependencies(monkeypatch):
    import src.core.atm.ui.run_profile_dialog as dialog_module
    import src.core.atm.controller as controller_module

    module = SimpleNamespace(
        name="ctrip_crawler",
        manifest=SimpleNamespace(
            workflows=[
                SimpleNamespace(name="web_quiz_workflow", display_name="网页做题"),
            ],
            resource_pools=[
                SimpleNamespace(name="bound_account_ready", display_name="已绑定账号环境池"),
            ],
        ),
    )
    registry = SimpleNamespace(
        list_modules=lambda: [module],
        get_module=lambda name: module if name == "ctrip_crawler" else None,
        refresh=lambda: None,
    )
    pool = SimpleNamespace(id="pool-1", name="主池")

    monkeypatch.setattr(dialog_module, "get_module_registry", lambda: registry)
    monkeypatch.setattr(
        dialog_module,
        "get_ip_pool_manager",
        lambda: SimpleNamespace(list_pools=lambda: [pool]),
    )
    def module_service():
        return SimpleNamespace(
            list_env_selectors=lambda module_name: [
                SimpleNamespace(
                    name="reuse_bound_account_env",
                    display_name="复用已绑定账号环境",
                    description="在当前资源池候选内复用已绑定账号环境",
                    returns_none=True,
                ),
            ]
            if module_name == "ctrip_crawler"
            else []
        )
    monkeypatch.setattr(dialog_module, "get_module_service", module_service)
    monkeypatch.setattr(controller_module, "get_module_service", module_service)


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
    dialog.selector_name_combo.setCurrentIndex(dialog.selector_name_combo.findData("random_ready"))

    profile = dialog._build_run_profile_from_form()

    assert profile.resource.acquisition.mode == AcquisitionMode.SELECT
    assert profile.resource.acquisition.selector_name == "random_ready"
    assert profile.resource.acquisition.provider == ""
    assert profile.resource.acquisition.wait_timeout == 60


def test_run_profile_dialog_builds_fixed_pool_select_profile_without_selector(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.script_selector.set_value("demo_module", "collect")
    dialog.resource_mode_combo.setCurrentIndex(dialog.resource_mode_combo.findData(AcquisitionMode.SELECT))
    dialog.selector_name_combo.setCurrentIndex(-1)
    dialog.resource_pool_combo.setCurrentIndex(dialog.resource_pool_combo.findData("bound_account_ready"))

    profile = dialog._build_run_profile_from_form()

    assert profile.resource.acquisition.mode == AcquisitionMode.SELECT
    assert profile.resource.acquisition.selector_name == ""
    assert profile.resource.acquisition.resource_pool == "bound_account_ready"
    assert profile.resource.acquisition.provider == ""


def test_run_profile_dialog_lists_declared_resource_pools(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.script_selector.set_value("demo_module", "collect")

    assert dialog.resource_pool_combo.isEnabled() is True
    assert dialog.resource_pool_combo.findData("") >= 0
    pool_index = dialog.resource_pool_combo.findData("bound_account_ready")
    assert pool_index >= 0
    assert dialog.resource_pool_combo.itemText(pool_index) == "已绑定账号环境池 (bound_account_ready)"


def test_run_profile_dialog_warns_when_selector_returns_none(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.script_selector.set_value("demo_module", "collect")
    dialog.resource_mode_combo.setCurrentIndex(dialog.resource_mode_combo.findData(AcquisitionMode.SELECT))
    dialog.selector_name_combo.setCurrentIndex(dialog.selector_name_combo.findData("return_none"))

    assert dialog.selector_none_hint.isHidden() is False
    assert "返回了 none" in dialog.selector_none_hint.text()


def test_run_profile_dialog_does_not_autofill_pool_for_returns_none_selector(qtbot, monkeypatch):
    _patch_ctrip_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.script_selector.set_value("ctrip_crawler", "web_quiz_workflow")
    dialog.resource_mode_combo.setCurrentIndex(dialog.resource_mode_combo.findData(AcquisitionMode.SELECT))
    dialog.selector_name_combo.setCurrentIndex(dialog.selector_name_combo.findData("reuse_bound_account_env"))

    profile = dialog._build_run_profile_from_form()

    assert dialog.selector_none_hint.isHidden() is False
    assert dialog.resource_pool_combo.currentData() == ""
    assert profile.resource.acquisition.resource_pool == ""


def test_run_profile_dialog_keeps_manual_pool_for_returns_none_selector(qtbot, monkeypatch):
    _patch_ctrip_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.script_selector.set_value("ctrip_crawler", "web_quiz_workflow")
    dialog.resource_mode_combo.setCurrentIndex(dialog.resource_mode_combo.findData(AcquisitionMode.SELECT))
    dialog.selector_name_combo.setCurrentIndex(dialog.selector_name_combo.findData("reuse_bound_account_env"))
    dialog.resource_pool_combo.setCurrentIndex(dialog.resource_pool_combo.findData("bound_account_ready"))

    profile = dialog._build_run_profile_from_form()

    assert profile.resource.acquisition.resource_pool == "bound_account_ready"


def test_run_profile_dialog_rejects_undeclared_resource_pool(qtbot, monkeypatch):
    _patch_dialog_dependencies(monkeypatch)

    from src.core.atm.ui.run_profile_dialog import RunProfileDialog

    dialog = RunProfileDialog()
    qtbot.addWidget(dialog)

    dialog.script_selector.set_value("demo_module", "collect")
    dialog.resource_mode_combo.setCurrentIndex(dialog.resource_mode_combo.findData(AcquisitionMode.SELECT))
    dialog.selector_name_combo.setCurrentIndex(-1)
    dialog.resource_pool_combo.addItem("missing_pool", "missing_pool")
    dialog.resource_pool_combo.setCurrentIndex(dialog.resource_pool_combo.findData("missing_pool"))

    with pytest.raises(ValueError, match="未在 module.yaml.resource_pools 中声明"):
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

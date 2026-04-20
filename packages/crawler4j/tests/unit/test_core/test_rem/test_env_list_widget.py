from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from src.core.rem import EnvKind
from src.core.rem.models import ProxyMode
from src.ui.components.combo_box import StyledComboBox


def _patch_dialog_dependencies(monkeypatch, suggested_name: str):
    import src.core.mms.registry as registry_module
    import src.core.rem.ui.env_list_widget as env_list_widget

    monkeypatch.setattr(
        env_list_widget,
        "get_create_env_default_name",
        lambda: suggested_name,
    )
    monkeypatch.setattr(
        env_list_widget,
        "get_ip_pool_manager",
        lambda: SimpleNamespace(list_pools=lambda: []),
    )
    monkeypatch.setattr(
        registry_module,
        "get_module_registry",
        lambda: SimpleNamespace(get_enabled_modules=lambda: []),
    )
    return env_list_widget


def test_create_env_dialog_prefills_suggested_name_without_submitting_override(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")

    dialog = env_list_widget.CreateEnvDialog()
    qtbot.addWidget(dialog)

    assert dialog.name_input.text() == "env-20260414-3"

    kind, provider, config = dialog.get_values()

    assert kind == EnvKind.BROWSER
    assert provider == "virtualbrowser"
    assert config == {"proxy": {"mode": ProxyMode.NONE}}


def test_create_env_dialog_submits_custom_name_after_edit(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")

    dialog = env_list_widget.CreateEnvDialog()
    qtbot.addWidget(dialog)

    dialog.name_input.setFocus()
    dialog.name_input.clear()
    qtbot.keyClicks(dialog.name_input, "custom-env")

    _, _, config = dialog.get_values()

    assert config["env_name"] == "custom-env"


def test_create_env_dialog_uses_styled_combo_boxes(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")

    dialog = env_list_widget.CreateEnvDialog()
    qtbot.addWidget(dialog)

    assert isinstance(dialog.kind_combo, StyledComboBox)
    assert isinstance(dialog.provider_combo, StyledComboBox)
    assert isinstance(dialog.proxy_mode_combo, StyledComboBox)
    assert isinstance(dialog.proxy_source_combo, StyledComboBox)
    assert isinstance(dialog.pool_combo, StyledComboBox)
    assert "QComboBox {" not in dialog.styleSheet()


def test_env_list_widget_create_finished_refreshes_without_success_dialog(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(
        manager_module,
        "get_environment_manager",
        lambda: SimpleNamespace(pool=SimpleNamespace()),
    )

    info = MagicMock()
    monkeypatch.setattr(env_list_widget.QMessageBox, "information", info)

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)
    widget.load_data = MagicMock()

    widget._on_create_finished(SimpleNamespace(id=123))

    widget.load_data.assert_called_once_with()
    info.assert_not_called()


def test_env_list_widget_busy_state_disables_controls(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(
        manager_module,
        "get_environment_manager",
        lambda: SimpleNamespace(pool=SimpleNamespace()),
    )

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)

    assert widget._begin_operation() is True
    assert widget.create_btn.isEnabled() is False
    assert widget.refresh_btn.isEnabled() is False
    assert widget.table.isEnabled() is False

    widget._end_operation()

    assert widget.create_btn.isEnabled() is True
    assert widget.refresh_btn.isEnabled() is True
    assert widget.table.isEnabled() is True


def test_env_list_widget_async_action_refreshes_without_threads(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")

    manager = SimpleNamespace(
        pool=SimpleNamespace(),
        start_env=AsyncMock(return_value=True),
    )

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(manager_module, "get_environment_manager", lambda: manager)

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)
    widget.load_data = MagicMock()

    import asyncio

    asyncio.run(widget._async_env_action("env-1", "start"))

    manager.start_env.assert_awaited_once_with("env-1")
    widget.load_data.assert_called_once_with()

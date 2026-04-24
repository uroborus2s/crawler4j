import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from PyQt6.QtWidgets import QDialog

from src.core.rem import EnvKind, EnvStatus
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


def _make_env(env_id: str, status: EnvStatus = EnvStatus.READY):
    return SimpleNamespace(
        id=env_id,
        name=f"{env_id}-name",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=status,
        task_run_id="",
    )


class _FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def disconnect(self, callback):
        try:
            self._callbacks.remove(callback)
        except ValueError as exc:
            raise TypeError from exc

    def emit(self, *args):
        for callback in list(self._callbacks):
            callback(*args)


class _ControlledLoaderThread:
    instances: list["_ControlledLoaderThread"] = []

    def __init__(self, pool, run_gc: bool = False):
        self._pool = pool
        self._run_gc = run_gc
        self.finished = _FakeSignal()
        self.error = _FakeSignal()
        self.started = False
        _ControlledLoaderThread.instances.append(self)

    def start(self):
        self.started = True

    def finish(self, envs):
        self.finished.emit(envs)

    def fail(self, message: str):
        self.error.emit(message)


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
    assert widget.import_existing_btn.isEnabled() is False
    assert widget.refresh_btn.isEnabled() is False
    assert widget.table.isEnabled() is False
    assert widget.loading_bar.isHidden() is False
    assert widget.operation_status_label.isHidden() is False
    assert widget.operation_status_label.text() == "正在处理环境操作..."

    widget._end_operation()

    assert widget.create_btn.isEnabled() is True
    assert widget.import_existing_btn.isEnabled() is True
    assert widget.refresh_btn.isEnabled() is True
    assert widget.table.isEnabled() is True
    assert widget.loading_bar.isHidden() is True
    assert widget.operation_status_label.isHidden() is True


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


def test_env_list_widget_rows_expose_actions_and_row_click_signal(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(
        manager_module,
        "get_environment_manager",
        lambda: SimpleNamespace(pool=SimpleNamespace()),
    )

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)
    selected: list[str] = []
    widget.env_selected.connect(selected.append)

    widget._on_data_loaded([_make_env("env-1", EnvStatus.READY)])
    row = widget.table.displayed_rows()[0]

    assert row["status"]["text"] == "就绪"
    assert [action["id"] for action in row["actions"]] == ["start", "pause", "edit", "destroy"]

    widget._on_table_row_clicked(row)

    assert selected == ["env-1"]


@pytest.mark.asyncio
async def test_env_list_widget_start_action_shows_provider_status_until_done(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")
    start_future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()

    async def start_env(env_id: str) -> bool:
        assert env_id == "env-1"
        return await start_future

    manager = SimpleNamespace(
        pool=SimpleNamespace(),
        start_env=AsyncMock(side_effect=start_env),
    )

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(manager_module, "get_environment_manager", lambda: manager)

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)
    widget.load_data = MagicMock()
    widget._on_data_loaded([_make_env("env-1", EnvStatus.READY)])

    widget._start_env("env-1")
    await asyncio.sleep(0)

    assert widget.loading_bar.isHidden() is False
    assert widget.operation_status_label.isHidden() is False
    assert "VirtualBrowser API" in widget.operation_status_label.text()
    assert "启动环境 env-1" in widget.operation_status_label.text()
    assert widget.create_btn.isEnabled() is False

    start_future.set_result(True)
    await _drain_widget_tasks(widget)

    assert widget.loading_bar.isHidden() is True
    assert widget.operation_status_label.isHidden() is True
    widget.load_data.assert_called_once_with()


@pytest.mark.asyncio
async def test_env_list_widget_exec_dialog_async_uses_open_without_nested_exec(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(
        manager_module,
        "get_environment_manager",
        lambda: SimpleNamespace(pool=SimpleNamespace()),
    )

    class FakeDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.open_called = False
            self.exec_called = False

        def exec(self):  # type: ignore[override]
            self.exec_called = True
            raise AssertionError("blocking exec should not be used")

        def open(self):  # type: ignore[override]
            self.open_called = True
            asyncio.get_running_loop().call_soon(
                lambda: self.done(int(QDialog.DialogCode.Accepted))
            )

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)

    dialog = FakeDialog(widget)
    result = await widget._exec_dialog_async(dialog)

    assert result == int(QDialog.DialogCode.Accepted)
    assert dialog.open_called is True
    assert dialog.exec_called is False


async def _drain_widget_tasks(widget) -> None:
    for _ in range(20):
        pending = [task for task in widget._pending_tasks if not task.done()]
        operation_task = widget._operation_task
        if not pending and (operation_task is None or operation_task.done()):
            return
        await asyncio.sleep(0)
    raise AssertionError("pending widget tasks did not finish in time")


@pytest.mark.asyncio
async def test_env_list_widget_destroy_refresh_waits_for_inflight_load(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")
    _ControlledLoaderThread.instances.clear()
    monkeypatch.setattr(env_list_widget, "DataLoaderThread", _ControlledLoaderThread)

    manager = SimpleNamespace(
        pool=SimpleNamespace(),
        destroy_env=AsyncMock(return_value=True),
    )

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(manager_module, "get_environment_manager", lambda: manager)
    monkeypatch.setattr(
        env_list_widget.QMessageBox,
        "question",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("blocking static question dialog should not be used")
        ),
    )
    monkeypatch.setattr(
        env_list_widget.QMessageBox,
        "information",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("blocking static information dialog should not be used")
        ),
    )
    shown_messages: list[tuple[str, str]] = []

    def fake_open(box):
        shown_messages.append((box.windowTitle(), box.text()))
        if box.text().startswith("确定要销毁环境"):
            result = int(env_list_widget.QMessageBox.StandardButton.Yes)
        else:
            result = int(env_list_widget.QMessageBox.StandardButton.Ok)
        asyncio.get_running_loop().call_soon(lambda: box.done(result))

    monkeypatch.setattr(env_list_widget.QMessageBox, "open", fake_open)

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)

    widget.load_data()
    assert len(_ControlledLoaderThread.instances) == 1
    assert widget._load_in_progress is True

    widget._destroy_env("env-1")
    await _drain_widget_tasks(widget)

    manager.destroy_env.assert_awaited_once_with("env-1")
    assert widget._reload_requested is True
    assert len(shown_messages) == 2
    assert shown_messages[0][1] == "确定要销毁环境 env-1 ?"
    assert shown_messages[1][1] == "环境已销毁"

    _ControlledLoaderThread.instances[0].finish([_make_env("env-1", EnvStatus.READY)])
    qtbot.waitUntil(lambda: len(_ControlledLoaderThread.instances) == 2, timeout=500)

    assert len(_ControlledLoaderThread.instances) == 2
    assert _ControlledLoaderThread.instances[1].started is True
    assert widget.table.displayed_rows()[0]["id"] == "env-1"
    assert widget.table.displayed_rows()[0]["status"]["text"] == "就绪"

    _ControlledLoaderThread.instances[1].finish([_make_env("env-1", EnvStatus.BUSY)])
    qtbot.waitUntil(lambda: widget._load_in_progress is False, timeout=500)

    assert widget._reload_requested is False
    assert widget.table.displayed_rows()[0]["status"]["text"] == "启动中"


@pytest.mark.asyncio
async def test_env_list_widget_load_data_queues_refresh_when_loading(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")
    _ControlledLoaderThread.instances.clear()
    monkeypatch.setattr(env_list_widget, "DataLoaderThread", _ControlledLoaderThread)

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(
        manager_module,
        "get_environment_manager",
        lambda: SimpleNamespace(pool=SimpleNamespace()),
    )

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)

    widget.load_data()
    assert len(_ControlledLoaderThread.instances) == 1
    assert widget._load_in_progress is True

    widget.load_data()
    assert len(_ControlledLoaderThread.instances) == 1

    _ControlledLoaderThread.instances[0].finish([_make_env("env-1", EnvStatus.READY)])
    qtbot.waitUntil(lambda: len(_ControlledLoaderThread.instances) == 2, timeout=500)

    assert len(_ControlledLoaderThread.instances) == 2
    assert _ControlledLoaderThread.instances[1].started is True
    assert widget._load_in_progress is True
    assert widget.table.displayed_rows()[0]["status"]["text"] == "就绪"

    _ControlledLoaderThread.instances[1].finish([_make_env("env-1", EnvStatus.BUSY)])
    qtbot.waitUntil(lambda: widget._load_in_progress is False, timeout=500)

    assert widget._load_in_progress is False
    assert widget.table.displayed_rows()[0]["status"]["text"] == "启动中"
    assert widget.stats_label.text() == "总计: 1 | 就绪: 0 | 忙碌: 1"


@pytest.mark.asyncio
async def test_env_list_widget_import_source_loading_shows_status_before_dialog(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")
    list_future: asyncio.Future[list[Any]] = asyncio.get_running_loop().create_future()
    dialog_events: list[str] = []

    async def list_unsynced_provider_envs(provider_name: str) -> list[Any]:
        assert provider_name == "virtualbrowser"
        return await list_future

    manager = SimpleNamespace(
        pool=SimpleNamespace(),
        list_existing_env_import_sources=lambda: [
            {"provider": "virtualbrowser", "label": "Virtual Browser"}
        ],
        list_unsynced_provider_envs=AsyncMock(side_effect=list_unsynced_provider_envs),
    )

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(manager_module, "get_environment_manager", lambda: manager)

    import src.core.mms.registry as registry_module

    module = SimpleNamespace(
        name="demo_module",
        manifest=SimpleNamespace(
            display_name="Demo Module",
            workflows=[
                SimpleNamespace(
                    name="main_flow",
                    display_name="Main Flow",
                    host_scenarios=["existing_env_import"],
                )
            ],
        ),
    )
    monkeypatch.setattr(
        registry_module,
        "get_module_registry",
        lambda: SimpleNamespace(get_enabled_modules=lambda: [module]),
    )

    class FakeDialog(QDialog):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent)
            dialog_events.append("constructed")

        def open(self):  # type: ignore[override]
            dialog_events.append("opened")
            asyncio.get_running_loop().call_soon(
                lambda: self.done(int(QDialog.DialogCode.Rejected))
            )

    monkeypatch.setattr(env_list_widget, "ImportExistingEnvDialog", FakeDialog)

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)

    task = asyncio.create_task(widget._import_existing_env_async())
    await asyncio.sleep(0)

    assert widget.loading_bar.isHidden() is False
    assert widget.operation_status_label.text() == "正在读取来源环境列表..."
    assert widget.create_btn.isEnabled() is False
    assert dialog_events == []

    list_future.set_result([])
    await task

    assert dialog_events == ["constructed", "opened"]
    assert widget.loading_bar.isHidden() is True
    assert widget.operation_status_label.isHidden() is True


@pytest.mark.asyncio
async def test_env_list_widget_import_source_loading_error_is_visible(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")
    dialog_events: list[str] = []

    manager = SimpleNamespace(
        pool=SimpleNamespace(),
        list_existing_env_import_sources=lambda: [
            {"provider": "virtualbrowser", "label": "Virtual Browser"}
        ],
        list_unsynced_provider_envs=AsyncMock(side_effect=RuntimeError("virtualbrowser API 未就绪")),
    )

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(manager_module, "get_environment_manager", lambda: manager)

    import src.core.mms.registry as registry_module

    module = SimpleNamespace(
        name="demo_module",
        manifest=SimpleNamespace(
            display_name="Demo Module",
            workflows=[
                SimpleNamespace(
                    name="main_flow",
                    display_name="Main Flow",
                    host_scenarios=["existing_env_import"],
                )
            ],
        ),
    )
    monkeypatch.setattr(
        registry_module,
        "get_module_registry",
        lambda: SimpleNamespace(get_enabled_modules=lambda: [module]),
    )

    class FakeDialog(QDialog):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent)
            dialog_events.append("constructed")

    monkeypatch.setattr(env_list_widget, "ImportExistingEnvDialog", FakeDialog)

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)
    widget._show_operation_error = AsyncMock()

    await widget._import_existing_env_async()

    widget._show_operation_error.assert_awaited_once_with("virtualbrowser API 未就绪")
    assert dialog_events == []
    assert widget.loading_bar.isHidden() is True
    assert widget.operation_status_label.isHidden() is True


@pytest.mark.asyncio
async def test_env_list_widget_import_existing_env_starts_background_job(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")

    manager = SimpleNamespace(
        pool=SimpleNamespace(),
        list_existing_env_import_sources=lambda: [
            {"provider": "virtualbrowser", "label": "Virtual Browser"}
        ],
        list_unsynced_provider_envs=AsyncMock(
            return_value=[
                SimpleNamespace(
                    external_id="vb-101",
                    name="VB Env 101",
                    remark="demo",
                    proxy_summary_text="SOCKS5 127.0.0.1:1080",
                    running_status="运行中",
                    last_used_at=1_746_000_000,
                )
            ]
        ),
    )
    import_service = SimpleNamespace(
        import_and_run=AsyncMock(
            return_value=SimpleNamespace(
                env=SimpleNamespace(id=33),
                task_id="task-33",
                job_id="job-33",
            )
        )
    )

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(manager_module, "get_environment_manager", lambda: manager)
    monkeypatch.setattr(env_list_widget, "get_existing_env_import_job_service", lambda: import_service)

    import src.core.mms.registry as registry_module

    module = SimpleNamespace(
        name="demo_module",
        manifest=SimpleNamespace(
            display_name="Demo Module",
            workflows=[SimpleNamespace(name="main_flow", display_name="Main Flow", host_scenarios=["existing_env_import"])],
        ),
    )
    monkeypatch.setattr(registry_module, "get_module_registry", lambda: SimpleNamespace(get_enabled_modules=lambda: [module]))

    class FakeDialog(QDialog):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent)
            self._values = {
                "provider": "virtualbrowser",
                "module_name": "demo_module",
                "workflow_name": "main_flow",
                "name": "VB Env 101",
            }

        def open(self):  # type: ignore[override]
            asyncio.get_running_loop().call_soon(
                lambda: self.done(int(QDialog.DialogCode.Accepted))
            )

        def get_values(self):
            return dict(self._values)

    monkeypatch.setattr(env_list_widget, "ImportExistingEnvDialog", FakeDialog)

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)
    widget.load_data = MagicMock()
    widget._show_message_async = AsyncMock()

    await widget._import_existing_env_async()
    await _drain_widget_tasks(widget)

    manager.list_unsynced_provider_envs.assert_awaited_once_with("virtualbrowser")
    import_service.import_and_run.assert_awaited_once_with(
        provider_name="virtualbrowser",
        env_name="VB Env 101",
        module_name="demo_module",
        workflow_name="main_flow",
    )
    widget.load_data.assert_called_once_with()

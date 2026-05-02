import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog

from src.core.atm.models import Job, JobType, TriggerConfig, TriggerType
from src.core.atm.run_profile import ExecutionContext, RunProfile
from src.core.rem.cleanup_service import (
    EnvCleanupExecutionItem,
    EnvCleanupExecutionResult,
    EnvCleanupPreview,
    EnvCleanupPreviewItem,
    EnvCleanupSource,
)
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


def _make_import_job(job_id: str = "job-import") -> Job:
    return Job(
        id=job_id,
        name="导入已登录环境",
        type=JobType.BATCH,
        trigger=TriggerConfig(type=TriggerType.MANUAL),
        concurrency_target=2,
        run_profile=RunProfile(
            execution=ExecutionContext(module="demo_module", workflow="main_flow")
        ),
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

    def __init__(self, pool, run_gc: bool = False, reload_from_db: bool = False):
        self._pool = pool
        self._run_gc = run_gc
        self._reload_from_db = reload_from_db
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


class _FakeCleanupService:
    def __init__(self, preview: EnvCleanupPreview, result: EnvCleanupExecutionResult | None = None):
        self.preview_result = preview
        self.cleanup_result = result or EnvCleanupExecutionResult()
        self.preview_calls = 0
        self.cleanup_calls = 0

    async def preview(self):
        self.preview_calls += 1
        return self.preview_result

    async def cleanup(self):
        self.cleanup_calls += 1
        return self.cleanup_result


def _patch_cleanup_service(monkeypatch, service: _FakeCleanupService) -> None:
    import src.core.rem.cleanup_service as cleanup_module

    monkeypatch.setattr(cleanup_module, "get_env_cleanup_service", lambda: service)


def test_create_env_dialog_prefills_suggested_name_without_submitting_override(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")

    dialog = env_list_widget.CreateEnvDialog()
    qtbot.addWidget(dialog)

    assert dialog.name_input.text() == "env-20260414-3"

    kind, provider, config = dialog.get_values()

    assert kind == EnvKind.BROWSER
    assert provider == "virtualbrowser"
    assert config == {"proxy": {"mode": ProxyMode.NONE}}


def test_create_env_dialog_keeps_native_title_bar(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")

    dialog = env_list_widget.CreateEnvDialog()
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "创建环境"
    assert dialog.windowFlags() & Qt.WindowType.Window
    assert dialog.windowFlags() & Qt.WindowType.WindowTitleHint
    assert not dialog.windowFlags() & Qt.WindowType.FramelessWindowHint


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


def test_cleanup_preview_dialog_renders_cleanup_targets_as_table(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")
    source = EnvCleanupSource(module_name="host", cleanup_name="orphan")

    dialog = env_list_widget.CleanupPreviewDialog(
        eligible_items=[
            EnvCleanupPreviewItem(
                env_id=352,
                sources=(source,),
                env_name="task-480788ce-3632-4799-a56f-5eecec4ffdf6-1776840410",
                provider="virtualbrowser",
                status="ready",
                eligible=True,
            ),
        ],
        skipped_count=1,
        error_count=0,
    )
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "确认批量清理"
    assert dialog.preview_table.table.rowCount() == 1
    assert dialog.preview_table.table.item(0, 1).text() == "352"
    assert dialog.preview_table.table.item(0, 2).text().startswith("task-480788ce-3632-4799")
    assert dialog.preview_table.table.item(0, 3).text() == "VirtualBrowser"
    assert dialog.preview_table.table.item(0, 4).text() == "host.orphan"


def test_env_list_widget_create_finished_refreshes_without_success_dialog(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(
        manager_module,
        "get_environment_manager",
        lambda: SimpleNamespace(pool=SimpleNamespace()),
    )

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)
    widget.load_data = MagicMock()

    widget._on_create_finished(SimpleNamespace(id=123))

    widget.load_data.assert_called_once_with()


def test_data_loader_thread_reloads_pool_from_db_before_listing(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")
    events: list[str] = []
    loaded_records: list[list[Any]] = []
    errors: list[str] = []

    async def reload_from_db():
        events.append("reload")

    async def list_all():
        events.append("list")
        return []

    pool = SimpleNamespace(
        reload_from_db=reload_from_db,
        list_all=list_all,
        list_metadata=lambda _env_id: {},
    )

    thread = env_list_widget.DataLoaderThread(pool, reload_from_db=True)
    thread.finished.connect(lambda records: loaded_records.append(records))
    thread.error.connect(errors.append)

    thread.run()

    assert events == ["reload", "list"]
    assert errors == []
    assert loaded_records == [[]]


@pytest.mark.asyncio
async def test_env_list_widget_delegates_import_task_startup_progress(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-4")
    import_service = SimpleNamespace(
        import_and_run_with_job=AsyncMock(
            return_value=SimpleNamespace(
                env=SimpleNamespace(id=33),
                envs=[SimpleNamespace(id=33)],
                task_ids=["task-33"],
                job_id="job-import",
            )
        )
    )

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)
    widget._import_job_service = import_service
    widget.load_data = MagicMock()
    widget._show_message_async = AsyncMock()
    widget._show_loading = MagicMock()

    await widget._async_import_existing_env_and_run(
        provider_name="virtualbrowser",
        env_names=["VB Env 101"],
        job_id="job-import",
    )

    import_service.import_and_run_with_job.assert_awaited_once_with(
        provider_name="virtualbrowser",
        env_names=["VB Env 101"],
        job_id="job-import",
    )
    widget._show_loading.assert_not_called()
    widget._show_message_async.assert_not_awaited()
    widget.load_data.assert_called_once_with()


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
    assert widget._progress_dialog is not None
    assert widget._progress_dialog.windowTitle() == "环境操作中"
    assert widget._progress_dialog.message_label.text() == "正在处理环境操作..."

    widget._end_operation()

    assert widget.create_btn.isEnabled() is True
    assert widget.import_existing_btn.isEnabled() is True
    assert widget.cleanup_btn.isEnabled() is True
    assert widget.refresh_btn.isEnabled() is True
    assert widget.table.isEnabled() is True
    assert widget._progress_dialog is None


@pytest.mark.asyncio
async def test_env_list_widget_cleanup_confirms_executes_and_refreshes(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")
    source = EnvCleanupSource(module_name="demo_module", cleanup_name="unused_accounts")
    service = _FakeCleanupService(
        EnvCleanupPreview(
            items=(
                EnvCleanupPreviewItem(
                    env_id=1,
                    sources=(source,),
                    env_name="env-1",
                    provider="virtualbrowser",
                    status="ready",
                    eligible=True,
                ),
            )
        ),
        EnvCleanupExecutionResult(
            items=(
                EnvCleanupExecutionItem(
                    env_id=1,
                    outcome="deleted",
                    sources=(source,),
                    env_name="env-1",
                    provider="virtualbrowser",
                    status="ready",
                ),
            )
        ),
    )
    _patch_cleanup_service(monkeypatch, service)

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(
        manager_module,
        "get_environment_manager",
        lambda: SimpleNamespace(pool=SimpleNamespace()),
    )

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)
    widget._show_loading = MagicMock()
    widget._confirm_cleanup_plan_async = AsyncMock(return_value=True)
    widget._show_message_async = AsyncMock()
    widget.load_data = MagicMock()

    await widget._cleanup_envs_async()
    await _drain_widget_tasks(widget)

    assert service.preview_calls == 1
    assert service.cleanup_calls == 1
    widget._confirm_cleanup_plan_async.assert_awaited_once()
    widget._show_message_async.assert_awaited_once()
    widget.load_data.assert_called_once_with(run_gc=False, reload_from_db=True)


@pytest.mark.asyncio
async def test_env_list_widget_cleanup_skips_without_safe_candidates(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")
    source = EnvCleanupSource(module_name="demo_module", cleanup_name="unused_accounts")
    service = _FakeCleanupService(
        EnvCleanupPreview(
            items=(
                EnvCleanupPreviewItem(
                    env_id=2,
                    sources=(source,),
                    env_name="env-2",
                    provider="virtualbrowser",
                    status="running",
                    eligible=False,
                    reason="状态不允许清理: running",
                ),
            )
        )
    )
    _patch_cleanup_service(monkeypatch, service)

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(
        manager_module,
        "get_environment_manager",
        lambda: SimpleNamespace(pool=SimpleNamespace()),
    )

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)
    widget._show_loading = MagicMock()
    widget._confirm_cleanup_plan_async = AsyncMock(return_value=True)
    widget._show_message_async = AsyncMock()

    await widget._cleanup_envs_async()

    assert service.preview_calls == 1
    assert service.cleanup_calls == 0
    widget._confirm_cleanup_plan_async.assert_not_awaited()
    widget._show_message_async.assert_awaited_once_with(
        "批量清理",
        "当前候选环境均不满足清理安全条件。",
        kind="warning",
    )


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

    asyncio.run(widget._async_env_operation("env-1", "start"))

    manager.start_env.assert_awaited_once_with("env-1")
    widget.load_data.assert_called_once_with()


def test_env_list_widget_refresh_requests_pool_reload(qtbot, monkeypatch):
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

    widget.refresh_btn.click()

    assert len(_ControlledLoaderThread.instances) == 1
    assert _ControlledLoaderThread.instances[0]._run_gc is True
    assert _ControlledLoaderThread.instances[0]._reload_from_db is True


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


def test_env_list_widget_preserves_env_metadata_without_resource_pool_availability(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")

    metadata_by_env = {
        101: {
            "demo.custom": {
                "account_status": {"state": "ready"},
            },
        },
        102: {},
    }
    pool = SimpleNamespace(
        list_metadata=MagicMock(side_effect=lambda env_id: metadata_by_env.get(env_id, {}))
    )

    import src.core.rem.manager as manager_module

    monkeypatch.setattr(
        manager_module,
        "get_environment_manager",
        lambda: SimpleNamespace(pool=pool),
    )

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)

    widget._on_data_loaded([
        _make_env(101, EnvStatus.READY),
        _make_env(102, EnvStatus.READY),
    ])
    rows = widget.table.displayed_rows()

    assert rows[0]["env_metadata"] == metadata_by_env[101]
    assert "availability" not in rows[0]
    assert rows[1]["env_metadata"] == {}


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

    assert widget._progress_dialog is not None
    assert "VirtualBrowser API" in widget._progress_dialog.message_label.text()
    assert "启动环境 env-1" in widget._progress_dialog.message_label.text()
    assert widget.create_btn.isEnabled() is False

    start_future.set_result(True)
    await _drain_widget_tasks(widget)

    assert widget._progress_dialog is None
    widget.load_data.assert_called_once_with()


@pytest.mark.asyncio
async def test_env_list_widget_exec_dialog_async_uses_show_without_nested_exec(qtbot, monkeypatch):
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
            self.show_called = False
            self.exec_called = False

        def exec(self):  # type: ignore[override]
            self.exec_called = True
            raise AssertionError("blocking exec should not be used")

        def show(self):  # type: ignore[override]
            self.show_called = True
            asyncio.get_running_loop().call_soon(
                lambda: self.done(int(QDialog.DialogCode.Accepted))
            )

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)

    dialog = FakeDialog(widget)
    result = await widget._exec_dialog_async(dialog)

    assert result == int(QDialog.DialogCode.Accepted)
    assert dialog.show_called is True
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
    confirmations: list[tuple[str, str]] = []
    shown_messages: list[tuple[str, str]] = []

    async def fake_confirm(parent, title, message, **kwargs):
        assert parent is widget
        confirmations.append((title, message))
        return True

    async def fake_show(parent, title, message, **kwargs):
        assert parent is widget
        shown_messages.append((title, message))

    monkeypatch.setattr(env_list_widget.ConfirmDialog, "confirm_async", staticmethod(fake_confirm))
    monkeypatch.setattr(env_list_widget.MessageDialog, "show_async", staticmethod(fake_show))

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)

    widget.load_data()
    assert len(_ControlledLoaderThread.instances) == 1
    assert widget._load_in_progress is True

    widget._destroy_env("env-1")
    await _drain_widget_tasks(widget)

    manager.destroy_env.assert_awaited_once_with("env-1")
    assert widget._reload_requested is True
    assert confirmations == [("确认", "确定要销毁环境 env-1 ?")]
    assert shown_messages == [("成功", "环境已销毁")]

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
async def test_env_list_widget_destroy_failure_shows_manager_reason(qtbot, monkeypatch):
    env_list_widget = _patch_dialog_dependencies(monkeypatch, "env-20260414-3")

    import src.core.rem.manager as manager_module

    manager = SimpleNamespace(pool=SimpleNamespace(), last_destroy_error="VirtualBrowser 删除后环境仍存在")
    monkeypatch.setattr(manager_module, "get_environment_manager", lambda: manager)

    shown_messages: list[tuple[str, str]] = []

    async def fake_show(parent, title, message, **kwargs):
        shown_messages.append((title, message))

    monkeypatch.setattr(env_list_widget.MessageDialog, "show_async", staticmethod(fake_show))

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)

    await widget._on_destroy_finished(False)

    assert shown_messages == [
        ("警告", "环境销毁失败，数据库记录已保留。\n原因：VirtualBrowser 删除后环境仍存在")
    ]


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
    import src.core.atm.service as task_service_module

    monkeypatch.setattr(
        task_service_module,
        "get_task_service",
        lambda: SimpleNamespace(list_jobs=AsyncMock(return_value=[_make_import_job()])),
    )

    class FakeDialog(QDialog):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent)
            dialog_events.append("constructed")

        def show(self):  # type: ignore[override]
            dialog_events.append("opened")
            asyncio.get_running_loop().call_soon(
                lambda: self.done(int(QDialog.DialogCode.Rejected))
            )

    monkeypatch.setattr(env_list_widget, "ImportExistingEnvDialog", FakeDialog)

    widget = env_list_widget.EnvListWidget()
    qtbot.addWidget(widget)

    task = asyncio.create_task(widget._import_existing_env_async())
    await asyncio.sleep(0)

    assert widget._progress_dialog is not None
    assert widget._progress_dialog.message_label.text() == "正在读取来源环境列表..."
    assert widget.create_btn.isEnabled() is False
    assert dialog_events == []

    list_future.set_result([])
    await task

    assert dialog_events == ["constructed", "opened"]
    assert widget._progress_dialog is None


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
    import src.core.atm.service as task_service_module

    monkeypatch.setattr(
        task_service_module,
        "get_task_service",
        lambda: SimpleNamespace(list_jobs=AsyncMock(return_value=[_make_import_job()])),
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
    assert widget._progress_dialog is None


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
        import_and_run_with_job=AsyncMock(
            return_value=SimpleNamespace(
                env=SimpleNamespace(id=33),
                envs=[SimpleNamespace(id=33), SimpleNamespace(id=34)],
                task_ids=["task-33"],
                job_id="job-import",
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

    import src.core.atm.service as task_service_module

    monkeypatch.setattr(
        task_service_module,
        "get_task_service",
        lambda: SimpleNamespace(list_jobs=AsyncMock(return_value=[_make_import_job()])),
    )

    class FakeDialog(QDialog):
        def __init__(self, parent=None, **kwargs):
            super().__init__(parent)
            self._values = {
                "provider": "virtualbrowser",
                "job_id": "job-import",
                "names": ["VB Env 101", "VB Env 102"],
            }

        def show(self):  # type: ignore[override]
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
    import_service.import_and_run_with_job.assert_awaited_once_with(
        provider_name="virtualbrowser",
        env_names=["VB Env 101", "VB Env 102"],
        job_id="job-import",
    )
    widget._show_message_async.assert_not_awaited()
    widget.load_data.assert_called_once_with()

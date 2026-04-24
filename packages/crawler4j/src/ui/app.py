"""UI 应用入口。"""

import asyncio
import runpy
import sys
from collections.abc import Sequence
from pathlib import Path

from PyQt6.QtWidgets import QApplication

from src.core.persistence import init_database
from src.core.system.preferences_service import (
    PreferenceKey,
    get_preferences_service,
)
from src.ui.app_icon import load_app_icon
from src.ui.qasync_compat import install_qasync_timer_compat
from src.utils.paths import get_app_data_dir

EMBEDDED_DEBUG_WORKER_FLAG = "--crawler4j-debug-worker"
EMBEDDED_DEBUGPY_ADAPTER_FLAG = "--crawler4j-debugpy-adapter"
DEFAULT_WORKER_MODULE = "src.core.debug.worker_entry"


def install_logging_preferences_sync(prefs, *, log_dir: Path) -> None:
    """把偏好设置绑定到唯一日志服务，支持热更新。"""
    from src.core.foundation.logging import logger

    def _apply() -> None:
        logger.configure(
            log_dir=log_dir,
            level=prefs.get(PreferenceKey.LOG_LEVEL),
            retention_days=prefs.get(PreferenceKey.LOG_RETENTION),
        )

    def _on_preference_changed(key: str, _value, _requires_restart: bool) -> None:
        if key not in {
            PreferenceKey.LOG_LEVEL.value,
            PreferenceKey.LOG_RETENTION.value,
        }:
            return
        _apply()

    _apply()
    prefs.preference_changed.connect(_on_preference_changed)


def install_update_preferences_sync(prefs) -> None:
    """把更新偏好设置绑定到应用更新服务。"""
    from src.core.system.update_service import get_update_service

    service = get_update_service()

    def _apply() -> None:
        service.configure(auto_check=bool(prefs.get(PreferenceKey.AUTO_UPDATE, True)))

    def _on_preference_changed(key: str, _value, _requires_restart: bool) -> None:
        if key != PreferenceKey.AUTO_UPDATE.value:
            return
        _apply()

    _apply()
    prefs.preference_changed.connect(_on_preference_changed)


def bootstrap_host_updater() -> None:
    """Run packaged-app updater bootstrap before the GUI starts."""
    from src.core.system.update_service import bootstrap_update_runtime

    bootstrap_update_runtime()


def _normalize_exit_code(code: object) -> int:
    if code is None:
        return 0
    if isinstance(code, int):
        return code
    return 1


def _extract_embedded_debug_worker_args(argv: Sequence[str]) -> Sequence[str] | None:
    from src.core.debug.launcher import extract_embedded_debug_worker_args

    return extract_embedded_debug_worker_args(argv)


def _extract_embedded_debugpy_adapter_args(argv: Sequence[str]) -> Sequence[str] | None:
    from src.core.debug.launcher import extract_embedded_debugpy_adapter_args

    return extract_embedded_debugpy_adapter_args(argv)


def _run_embedded_debug_worker(worker_args: Sequence[str], *, executable: str) -> int:
    from src.core.debug import worker_entry

    original_argv = sys.argv
    try:
        sys.argv = [executable, *worker_args]
        try:
            worker_entry.main()
        except SystemExit as exc:
            return _normalize_exit_code(exc.code)
        return 0
    finally:
        sys.argv = original_argv


def _run_embedded_debugpy_adapter(adapter_args: Sequence[str], *, executable: str) -> int:
    original_argv = sys.argv
    try:
        sys.argv = [executable, *adapter_args]
        try:
            runpy.run_module("debugpy.adapter", run_name="__main__")
        except SystemExit as exc:
            return _normalize_exit_code(exc.code)
        return 0
    finally:
        sys.argv = original_argv


def _load_qasync_module():
    import qasync

    return qasync


def _load_shell_class():
    from src.ui.shell import Shell

    return Shell


def _run_embedded_debug_worker_if_requested(argv: Sequence[str]) -> int | None:
    if not getattr(sys, "frozen", False):
        return None
    if len(argv) < 2:
        return None
    if argv[1] == "-m":
        if len(argv) < 4 or argv[2] != DEFAULT_WORKER_MODULE:
            return None
    elif argv[1] != EMBEDDED_DEBUG_WORKER_FLAG:
        return None

    worker_args = _extract_embedded_debug_worker_args(argv)
    if worker_args is None:
        return None

    return _run_embedded_debug_worker(worker_args, executable=argv[0])


def _run_embedded_debugpy_adapter_if_requested(argv: Sequence[str]) -> int | None:
    if not getattr(sys, "frozen", False):
        return None
    if len(argv) < 2 or argv[1] != EMBEDDED_DEBUGPY_ADAPTER_FLAG:
        return None

    adapter_args = _extract_embedded_debugpy_adapter_args(argv)
    if adapter_args is None:
        return None

    return _run_embedded_debugpy_adapter(adapter_args, executable=argv[0])


def main(argv: Sequence[str] | None = None) -> int:
    """启动应用。"""
    argv_list = list(sys.argv if argv is None else argv)
    embedded_worker_exit_code = _run_embedded_debug_worker_if_requested(argv_list)
    if embedded_worker_exit_code is not None:
        return embedded_worker_exit_code
    embedded_adapter_exit_code = _run_embedded_debugpy_adapter_if_requested(argv_list)
    if embedded_adapter_exit_code is not None:
        return embedded_adapter_exit_code

    bootstrap_host_updater()

    # 初始化数据库
    init_database()

    # 初始化唯一日志服务，并绑定日志偏好热更新
    prefs = get_preferences_service()
    log_dir = get_app_data_dir() / "logs"
    install_logging_preferences_sync(prefs, log_dir=log_dir)
    install_update_preferences_sync(prefs)
    from src.core.foundation.logging import logger

    # 创建应用
    app = QApplication(argv_list)
    app.setApplicationName("蛛行演略 · crawler4j")
    # 在异步服务启动且主窗口真正显示前，避免 Qt 因“尚无顶层窗口”提前退出事件循环。
    app.setQuitOnLastWindowClosed(False)

    # 设置应用图标
    app_icon = load_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    
    # 创建主窗口
    try:
        qasync = _load_qasync_module()
    except ImportError:
        logger.error("qasync is required but not installed.")
        sys.exit(1)

    install_qasync_timer_compat(qasync)

    # Setup qasync loop
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    with loop:
        loop.run_until_complete(_run_application(app, prefs))
    return 0


async def _run_application(app: QApplication, prefs) -> None:
    shutdown_requested = asyncio.Event()
    app.lastWindowClosed.connect(shutdown_requested.set)

    from src.core.rem.manager import get_environment_manager

    env_manager = get_environment_manager()
    await env_manager.startup()

    from src.core.atm.service import get_task_service

    task_service = get_task_service()
    await task_service.start()

    window = _load_shell_class()()
    if prefs.get(PreferenceKey.MINIMIZE_ON_START, False):
        window.showMinimized()
    else:
        window.show()
    # 保持“最后一个窗口关闭时不自动退出”，让 qasync 在窗口关闭后仍能继续驱动
    # 异步清理逻辑，避免 Qt 先停环导致 run_until_complete 误判为未完成。
    await asyncio.sleep(0)

    from src.core.system.update_service import get_update_service

    get_update_service().startup()

    try:
        await shutdown_requested.wait()
    finally:
        await task_service.stop()

        from src.core.debug.service import get_debug_service

        await get_debug_service().shutdown()

        from src.core.rem.handle import PlaywrightManager

        await PlaywrightManager.force_shutdown()


if __name__ == "__main__":
    raise SystemExit(main())

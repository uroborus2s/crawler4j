"""UI 应用入口。"""

import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from src.core.foundation.logging import logger
from src.core.persistence import init_database
from src.core.system.preferences_service import (
    PreferenceKey,
    get_preferences_service,
)
from src.ui.shell import Shell
from src.utils.paths import get_app_data_dir, get_resource_path


def install_logging_preferences_sync(prefs, *, log_dir: Path) -> None:
    """把偏好设置绑定到唯一日志服务，支持热更新。"""

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


def main():
    """启动应用。"""
    # 初始化数据库
    init_database()

    # 初始化唯一日志服务，并绑定日志偏好热更新
    prefs = get_preferences_service()
    log_dir = get_app_data_dir() / "logs"
    install_logging_preferences_sync(prefs, log_dir=log_dir)
    
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("蛛行演略 · crawler4j")
    
    # 设置应用图标
    icon_path = get_resource_path("src/ui/assets/icon.jpg")
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))
    
    # 创建主窗口
    try:
        import asyncio

        import qasync
    except ImportError:
        logger.error("qasync is required but not installed.")
        sys.exit(1)

    # Setup qasync loop
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    with loop:
        # 初始化核心服务
        from src.core.rem.manager import get_environment_manager
        
        # 环境管理器启动（加载数据库、同步状态、启动 GC）
        # EnvironmentManager.startup 内部会自动初始化并启动 IPPoolManager
        env_manager = get_environment_manager()
        loop.run_until_complete(env_manager.startup())
        
        # ATM 任务引擎启动（Cron 调度 + 事件驱动补并发 + 崩溃自检）
        from src.core.atm.service import get_task_service
        task_service = get_task_service()
        loop.run_until_complete(task_service.start())
        
        
        window = Shell()
        
        if prefs.get(PreferenceKey.MINIMIZE_ON_START, False):
            window.showMinimized()
        else:
            window.show()
        
        # 运行事件循环
        loop.run_forever()
        
        # 应用退出时清理资源
        # 1. 优雅退出 ATM 控制循环，等待正在执行的任务完成
        loop.run_until_complete(task_service.stop())
        # 2. 停止调试 worker
        from src.core.debug.service import get_debug_service
        loop.run_until_complete(get_debug_service().shutdown())
        # 2. 关闭 Playwright 进程
        from src.core.rem.handle import PlaywrightManager
        loop.run_until_complete(PlaywrightManager.force_shutdown())


if __name__ == "__main__":
    main()

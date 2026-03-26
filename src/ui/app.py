"""UI 应用入口。"""

import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from src.core.foundation.logging import setup_file_logging
from src.core.persistence import init_database
from src.core.system.preferences_service import (
    PreferenceKey,
    get_preferences_service,
)
from src.ui.shell import Shell
from src.utils.paths import get_app_data_dir, get_resource_path


def main():
    """启动应用。"""
    # 初始化数据库
    init_database()

    # 读取日志配置
    prefs = get_preferences_service()
    log_level = prefs.get(PreferenceKey.LOG_LEVEL, "INFO")
    log_retention = prefs.get(PreferenceKey.LOG_RETENTION, 14)

    # 初始化日志 (使用默认路径)
    log_dir = get_app_data_dir() / "logs"
    setup_file_logging(str(log_dir), level=log_level, retention_days=log_retention)
    
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("Crawler4j")
    
    # 设置应用图标
    icon_path = get_resource_path("src/ui/assets/icon.jpg")
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))
    
    # 创建主窗口
    try:
        import asyncio

        import qasync
    except ImportError:
        print("Error: qasync is required but not installed.")
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

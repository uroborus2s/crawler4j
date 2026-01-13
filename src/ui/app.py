"""UI 应用入口。"""

import sys
from pathlib import Path

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from src.core.foundation.logging import setup_file_logging
from src.core.persistence import init_database
from src.ui.shell import Shell
from src.utils.paths import get_app_data_dir


def main():
    """启动应用。"""
    # 初始化数据库
    init_database()

    # 初始化日志 (使用默认路径)
    log_dir = get_app_data_dir() / "logs"
    setup_file_logging(str(log_dir))
    
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("Crawler4j")
    
    # 设置应用图标
    icon_path = Path(__file__).parent / "assets" / "icon.jpg"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
    # 创建主窗口
    window = Shell()
    window.show()
    
    # 运行事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

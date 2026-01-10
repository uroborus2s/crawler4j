"""UI 应用入口。"""

import sys

from PyQt6.QtWidgets import QApplication

from src.core.persistence import init_database
from src.ui.shell import Shell


def main():
    """启动应用。"""
    # 初始化数据库
    init_database()
    
    # 创建应用
    app = QApplication(sys.argv)
    app.setApplicationName("Crawler4j")
    
    # 创建主窗口
    window = Shell()
    window.show()
    
    # 运行事件循环
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

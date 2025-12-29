"""Application entry point.

Launches the Crawler4j GUI application.
"""

import asyncio
import sys
from pathlib import Path

import qasync
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from src.__version__ import VERSION
from src.ui.main_window import MainWindow
from src.ui.pages.ctrip_accounts_page import CtripAccountsPage
from src.ui.pages.dashboard_page import DashboardPage
from src.ui.pages.environments_page import EnvironmentsPage
from src.ui.pages.labor_accounts_page import LaborAccountsPage
from src.ui.pages.settings_page import SettingsPage
from src.utils.init_db import init_database
from src.utils.paths import get_resource_path


def main():

    # Initialize database
    init_database()
    
    # Enable high DPI scaling (must be before QApplication)
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Crawler4j")
    app.setApplicationVersion(VERSION)
        
    # Set app icon
    icon_path = get_resource_path("src/assets/icon.png")
    if Path(icon_path).exists():
        app.setWindowIcon(QIcon(icon_path))
    
    # Create asyncio event loop integrated with Qt
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # Create main window
    window = MainWindow()
    
    dashboard = DashboardPage()
    
    ctrip_page = CtripAccountsPage()
    labor_page = LaborAccountsPage()
    env_page = EnvironmentsPage()
    settings_page = SettingsPage()

    # Add pages to window (order must match Sidebar.NAV_ITEMS)
    window.add_page(dashboard)
    window.add_page(ctrip_page)
    window.add_page(labor_page)
    window.add_page(env_page)
    window.add_page(settings_page)
    
    # Show window
    window.show()
    
    # Run integrated Qt + asyncio event loop
    with loop:
        loop.run_forever()


if __name__ == "__main__":
    main()

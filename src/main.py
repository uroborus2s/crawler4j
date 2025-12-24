"""Application entry point.

Launches the Crawler4j GUI application.
"""

import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from src.ui.main_window import MainWindow
from src.ui.pages.dashboard_page import DashboardPage
from src.utils.init_db import init_database


def main():
    """Main application entry point."""
    # Initialize database
    init_database()
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Crawler4j")
    app.setApplicationVersion("0.1.0")
    
    # Enable high DPI scaling
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    # Create main window
    window = MainWindow()
    
    # Replace dashboard placeholder with real page
    dashboard = DashboardPage()
    dashboard.add_demo_data()  # Add demo data for testing
    window.set_page(0, dashboard)
    
    # Show window
    window.show()
    
    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

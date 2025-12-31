import os
import sys
from pathlib import Path


def get_resource_path(relative_path: str) -> str:
    """Get absolute path to resource, works for dev and for PyInstaller bundle.

    PyInstaller creates a temporary folder and stores path in _MEIPASS.
    """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # If not bundled, use absolute path to project root
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    return os.path.join(base_path, relative_path)


def get_app_data_dir() -> Path:
    """Get the platform-specific directory for application data.

    Windows: %APPDATA%/Crawler4j/
    macOS: ~/Library/Application Support/Crawler4j/
    Linux: ~/.local/share/Crawler4j/
    """
    app_name = "Crawler4j"

    if sys.platform == "win32":
        base_dir = Path(os.getenv("APPDATA", os.path.expanduser("~")))
    elif sys.platform == "darwin":
        base_dir = Path("~/Library/Application Support").expanduser()
    else:
        base_dir = Path("~/.local/share").expanduser()

    app_dir = base_dir / app_name
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_db_path() -> Path:
    """Get the database path in the application data directory."""
    return get_app_data_dir() / "crawler.db"

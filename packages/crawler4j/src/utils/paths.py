import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """判断是否为打包后的环境"""
    return getattr(sys, 'frozen', False)


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


def get_workspace_root() -> Path:
    """Return the repository workspace root in development mode."""
    return Path(__file__).resolve().parents[4]


def get_docs_root() -> Path:
    """Return the bundled public docs root for dev and packaged runs."""
    if is_frozen():
        return Path(get_resource_path("docs"))
    return get_workspace_root() / "docs"


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

def get_builtin_modules_path() -> Path:
    """获取内置模块目录
    
    内置模块随应用打包分发，位于：
    - 打包后: _MEIPASS/modules
    - 开发时: 项目根目录/modules
    """
    return Path(get_resource_path("modules"))


def get_user_modules_path() -> Path:
    """获取用户模块目录
    
    用户安装的外部模块存放位置。
    """
    modules_dir = get_app_data_dir() / "modules"
    modules_dir.mkdir(parents=True, exist_ok=True)
    return modules_dir


def get_config_dir() -> Path:
    """获取配置存储目录。"""
    config_dir = get_app_data_dir() / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

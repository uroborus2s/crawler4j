"""Browser detector module.

Detects if fingerprint browsers (BitBrowser/VirtualBrowser) are installed.
"""

import platform
import subprocess
from pathlib import Path

import requests


class BrowserDetector:
    """Detects fingerprint browser installation and connectivity."""
    
    # Common installation paths
    PATHS = {
        "bitbrowser": {
            "darwin": [
                "/Applications/BitBrowser.app",
                Path.home() / "Applications/BitBrowser.app",
                Path.home() / "Library/Application Support/BitBrowser/BitBrowser.app",
            ],
            "windows": [
                Path.home() / "AppData/Local/BitBrowser",
                Path.home() / "AppData/Roaming/BitBrowser",
                Path("C:/Program Files/BitBrowser"),
            ],
        },
        "virtualbrowser": {
            "darwin": [
                "/Applications/VirtualBrowser.app",
                Path.home() / "Applications/VirtualBrowser.app",
                Path.home() / "Library/Application Support/VirtualBrowser/VirtualBrowser.app",
            ],
            "windows": [
                Path.home() / "AppData/Local/VirtualBrowser",
                Path.home() / "AppData/Roaming/VirtualBrowser",
                Path("C:/Program Files/VirtualBrowser"),
            ],
        },
    }
    
    # Default API ports
    DEFAULT_PORTS = {
        "bitbrowser": 54345,
        "virtualbrowser": 54346,
    }
    
    @classmethod
    def get_system(cls) -> str:
        """Get current operating system."""
        system = platform.system().lower()
        if system == "darwin":
            return "darwin"
        elif system == "windows":
            return "windows"
        return "linux"
    
    @classmethod
    def is_installed(cls, browser_type: str) -> bool:
        """Check if browser is installed.
        
        Args:
            browser_type: 'bitbrowser' or 'virtualbrowser'
            
        Returns:
            True if installed.
        """
        system = cls.get_system()
        paths = cls.PATHS.get(browser_type, {}).get(system, [])
        
        for path in paths:
            path = Path(path)
            if path.exists():
                return True
        
        # Also check if process is running
        return cls._is_process_running(browser_type)
    
    @classmethod
    def _is_process_running(cls, browser_type: str) -> bool:
        """Check if browser process is running."""
        system = cls.get_system()
        
        try:
            if system == "darwin":
                process_name = "BitBrowser" if browser_type == "bitbrowser" else "VirtualBrowser"
                result = subprocess.run(
                    ["pgrep", "-f", process_name],
                    capture_output=True,
                    timeout=5,
                )
                return result.returncode == 0
            elif system == "windows":
                process_name = "BitBrowser.exe" if browser_type == "bitbrowser" else "VirtualBrowser.exe"
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
                    capture_output=True,
                    timeout=5,
                )
                return process_name.lower() in result.stdout.decode().lower()
        except Exception:
            pass
        
        return False
    
    @classmethod
    def test_api_connection(cls, url: str) -> bool:
        """Test connection to browser API.
        
        Args:
            url: API base URL (e.g., http://127.0.0.1:54345)
            
        Returns:
            True if connection successful.
        """
        try:
            # Most fingerprint browsers have a health/status endpoint
            response = requests.get(
                f"{url.rstrip('/')}/api/v1/health",
                timeout=5,
            )
            return response.status_code < 500
        except requests.exceptions.ConnectionError:
            # Try the base URL
            try:
                response = requests.get(url, timeout=5)
                return response.status_code < 500
            except Exception:
                pass
        except Exception:
            pass
        
        return False
    
    @classmethod
    def get_default_api_url(cls, browser_type: str) -> str:
        """Get default API URL for browser type.
        
        Args:
            browser_type: 'bitbrowser' or 'virtualbrowser'
            
        Returns:
            Default API URL.
        """
        port = cls.DEFAULT_PORTS.get(browser_type, 54345)
        return f"http://127.0.0.1:{port}"
    
    @classmethod
    def get_installation_path(cls, browser_type: str) -> Path | None:
        """Get installation path if browser is installed.
        
        Args:
            browser_type: Browser type.
            
        Returns:
            Path if found, None otherwise.
        """
        system = cls.get_system()
        paths = cls.PATHS.get(browser_type, {}).get(system, [])
        
        for path in paths:
            path = Path(path)
            if path.exists():
                return path
        
        return None

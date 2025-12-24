"""Browser API module.

Provides a unified interface for BitBrowser and VirtualBrowser APIs.
"""

from typing import Any

import requests

from src.config import config


class BrowserAPI:
    """Interface for fingerprint browser local APIs."""
    
    @classmethod
    def open_browser(cls, profile_id: str) -> dict[str, Any]:
        """Open a browser profile and return connection info.
        
        Args:
            profile_id: The browser profile ID.
            
        Returns:
            Dict containing 'ws_endpoint' (CDP URL) and 'http_endpoint'.
            
        Raises:
            RuntimeError: If browser fails to open.
        """
        browser_type = config.browser_type
        base_url = config.browser_api_url.rstrip("/")
        
        if browser_type == "bitbrowser":
            # BitBrowser Open API
            url = f"{base_url}/api/v1/browser/open"
            payload = {"id": profile_id}
        else:
            # VirtualBrowser Open API
            url = f"{base_url}/api/v1/browser/start"
            payload = {"profileId": profile_id}
            
        try:
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            if browser_type == "bitbrowser":
                if data.get("success"):
                    return {
                        "ws_endpoint": data["data"]["ws"],
                        "http_endpoint": data["data"]["http"],
                        "driver_path": data["data"]["driver"],
                    }
            else:
                if data.get("code") == 0:
                    return {
                        "ws_endpoint": data["data"]["ws"],
                        "http_endpoint": data["data"]["http"],
                    }
                    
            error_msg = data.get("msg") or data.get("message") or "Unknown error"
            raise RuntimeError(f"Failed to open browser: {error_msg}")
            
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"Browser API connection error: {e}")

    @classmethod
    def close_browser(cls, profile_id: str) -> bool:
        """Close a browser profile.
        
        Args:
            profile_id: The browser profile ID.
            
        Returns:
            True if successful.
        """
        browser_type = config.browser_type
        base_url = config.browser_api_url.rstrip("/")
        
        if browser_type == "bitbrowser":
            url = f"{base_url}/api/v1/browser/close"
            payload = {"id": profile_id}
        else:
            url = f"{base_url}/api/v1/browser/stop"
            payload = {"profileId": profile_id}
            
        try:
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            if browser_type == "bitbrowser":
                return data.get("success", False)
            else:
                return data.get("code") == 0
        except Exception:
            return False

    @classmethod
    def create_profile(cls, name: str, remark: str = "") -> str:
        """Create a new browser profile.
        
        Args:
            name: Profile name.
            remark: Optional remark.
            
        Returns:
            Profile ID.
        """
        browser_type = config.browser_type
        base_url = config.browser_api_url.rstrip("/")
        
        if browser_type == "bitbrowser":
            url = f"{base_url}/api/v1/browser/update"
            payload = {
                "name": name,
                "remark": remark,
                "browserFingerprint": {"os": "windows"} # Default to windows
            }
        else:
            url = f"{base_url}/api/v1/profile/create"
            payload = {
                "name": name,
                "notes": remark,
            }
            
        try:
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            
            if browser_type == "bitbrowser":
                if data.get("success"):
                    return data["data"]["id"]
            else:
                if data.get("code") == 0:
                    return data["data"]["id"]
            
            raise RuntimeError(f"Failed to create profile: {data}")
        except Exception as e:
            raise RuntimeError(f"Browser API error: {e}")
            
    @classmethod
    def delete_profile(cls, profile_id: str) -> bool:
        """Delete a browser profile."""
        browser_type = config.browser_type
        base_url = config.browser_api_url.rstrip("/")
        
        if browser_type == "bitbrowser":
            url = f"{base_url}/api/v1/browser/delete"
            payload = {"id": profile_id}
        else:
            url = f"{base_url}/api/v1/profile/delete"
            payload = {"profileId": profile_id}
            
        try:
            response = requests.post(url, json=payload, timeout=10)
            data = response.json()
            return data.get("success") or data.get("code") == 0
        except Exception:
            return False

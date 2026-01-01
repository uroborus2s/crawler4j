"""Browser API module.

Provides a unified interface for BitBrowser and VirtualBrowser APIs.
"""

from typing import Any

import requests

from src.config import config
from src.utils.http_client import AsyncHttpClient


class BrowserAPI:
    """Interface for fingerprint browser local APIs."""

    # ==================== Async Methods (aiohttp) ====================

    @classmethod
    async def open_browser_async(cls, profile_id: str) -> dict[str, Any]:
        """Open a browser profile asynchronously."""
        browser_type = config.browser_type
        base_url = config.browser_api_url.rstrip("/")

        if browser_type == "bitbrowser":
            url = f"{base_url}/browser/open"
            payload = {"id": profile_id}
        else:
            url = f"{base_url}/api/v1/browser/start"
            payload = {"profileId": profile_id}

        try:
            data = await AsyncHttpClient.post(url, json=payload)
            
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
    async def close_browser_async(cls, profile_id: str) -> bool:
        """Close a browser profile asynchronously."""
        browser_type = config.browser_type
        base_url = config.browser_api_url.rstrip("/")

        if browser_type == "bitbrowser":
            url = f"{base_url}/browser/close"
            payload = {"id": profile_id}
        else:
            url = f"{base_url}/api/v1/browser/stop"
            payload = {"profileId": profile_id}

        try:
            data = await AsyncHttpClient.post(url, json=payload)
            return (
                data.get("success")
                if browser_type == "bitbrowser"
                else data.get("code") == 0
            )
        except Exception:
            return False

    @classmethod
    async def create_profile_async(
        cls,
        name: str,
        remark: str = "",
        proxy: dict[str, Any] | None = None,
        fingerprint: dict[str, Any] | None = None,
        group_id: str | None = None,
    ) -> str:
        """Create a new browser profile asynchronously."""
        browser_type = config.browser_type
        base_url = config.browser_api_url.rstrip("/")
        real_proxy: dict[str, Any] = proxy or {"type": "noproxy"}
        real_fingerprint: dict[str, Any] = fingerprint or {}

        if browser_type == "bitbrowser":
            url = f"{base_url}/browser/update"
            payload = cls._build_bitbrowser_payload(
                name, remark, group_id, real_proxy, real_fingerprint
            )
        else:
            url = f"{base_url}/api/v1/browser/add"
            # Re-implement payload building for virtualbrowser or abstract it? 
            # For now, duplicate logic to keep it simple self-contained or call shared
            # Ideally we extract "build_payload" but it's mixed in the sync method.
            # Let's verify if we can extract it. 
            # The sync method creates it inline. I will duplicate for safety/speed now.
            payload: dict[str, Any] = {
                "name": name,
                "notes": remark,
                "groupId": group_id,
            }
            if real_proxy.get("type", "noproxy") != "noproxy":
                payload["proxy"] = {
                    "type": real_proxy.get("type"),
                    "host": real_proxy.get("host"),
                    "port": real_proxy.get("port"),
                    "username": real_proxy.get("user"),
                    "password": real_proxy.get("pass"),
                }

            fp_config_vb: dict[str, Any] = {}
            if real_fingerprint.get("os"):
                fp_config_vb["os"] = real_fingerprint["os"]
            if real_fingerprint.get("user_agent"):
                fp_config_vb["userAgent"] = real_fingerprint["user_agent"]
            if fp_config_vb:
                payload["fingerprint"] = fp_config_vb

        try:
            data = await AsyncHttpClient.post(url, json=payload)
            
            if browser_type == "bitbrowser":
                if data.get("success"):
                    return data["data"]["id"]
            else:
                if data.get("code") == 0:
                    return data["data"]["id"]

            error_msg = data.get("msg") or data.get("message") or str(data)
            raise RuntimeError(f"Failed to create profile: {error_msg}")
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"Browser API error: {e}")

    @classmethod
    async def delete_profile_async(cls, profile_id: str) -> bool:
        """Delete a browser profile asynchronously."""
        browser_type = config.browser_type
        base_url = config.browser_api_url.rstrip("/")

        if browser_type == "bitbrowser":
            url = f"{base_url}/browser/delete"
            payload = {"id": profile_id}
        else:
            url = f"{base_url}/api/v1/profile/delete"
            payload = {"profileId": profile_id}

        try:
            data = await AsyncHttpClient.post(url, json=payload)
            return (
                data.get("success")
                if browser_type == "bitbrowser"
                else data.get("code") == 0
            )
        except Exception:
            return False
            
    # ==================== Sync Methods (requests) ====================

    @classmethod
    def open_browser(cls, profile_id: str) -> dict[str, Any]:
        """Open a browser profile and return connection info."""
        browser_type = config.browser_type
        base_url = config.browser_api_url.rstrip("/")

        if browser_type == "bitbrowser":
            url = f"{base_url}/browser/open"
            payload = {"id": profile_id}
        else:
            url = f"{base_url}/api/v1/browser/start"
            payload = {"profileId": profile_id}

        try:
            # Bypass system proxies for local API calls
            response = requests.post(
                url, json=payload, timeout=5, proxies={"http": None, "https": None} # type: ignore # type: ignore
            )
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
        """Close a browser profile."""
        browser_type = config.browser_type
        base_url = config.browser_api_url.rstrip("/")

        if browser_type == "bitbrowser":
            url = f"{base_url}/browser/close"
            payload = {"id": profile_id}
        else:
            url = f"{base_url}/api/v1/browser/stop"
            payload = {"profileId": profile_id}

        try:
            response = requests.post(
                url, json=payload, timeout=60, proxies={"http": None, "https": None} # type: ignore
            )
            data = response.json()
            return (
                data.get("success")
                if browser_type == "bitbrowser"
                else data.get("code") == 0
            )
        except Exception:
            return False

    @classmethod
    def _build_bitbrowser_payload(
        cls,
        name: str,
        remark: str,
        group_id: str | None,
        proxy: dict[str, Any],
        fingerprint: dict[str, Any],
    ) -> dict[str, Any]:
        """构建 BitBrowser 创建配置的请求体。"""
        payload: dict[str, Any] = {
            "name": name,
            "remark": remark,
            "groupId": group_id,
            "proxyMethod": 2,
            "proxyType": proxy.get("type", "noproxy"),
        }

        if payload["proxyType"] != "noproxy":
            payload["host"] = proxy.get("host")
            port = proxy.get("port")
            payload["port"] = int(port) if port else None
            payload["proxyUserName"] = proxy.get("user")
            payload["proxyPassword"] = proxy.get("pass")

        fp_config: dict[str, Any] = {
            "ostype": "PC",
            "coreVersion": "130",
            "devicePixelRatio": 1,
        }

        if fingerprint.get("os") == "macOS":
            fp_config["os"] = "MacIntel"
            fp_config["osVersion"] = fingerprint.get("os_version", "10.15")
        else:
            fp_config["os"] = "Win32"
            fp_config["osVersion"] = fingerprint.get("os_version", "11,10")

        if fingerprint.get("user_agent"):
            fp_config["userAgent"] = fingerprint["user_agent"]

        if fingerprint.get("resolution"):
            fp_config["resolutionType"] = "1"
            fp_config["resolution"] = fingerprint["resolution"]

        payload["browserFingerPrint"] = fp_config
        return payload

    @classmethod
    def _parse_bitbrowser_profiles(cls, data: dict) -> tuple[int, list]:
        """解析 BitBrowser 配置列表响应。"""
        profiles = []
        if not data.get("success"):
            return 0, profiles

        resp_data = data.get("data")
        items = []
        total = 0

        if isinstance(resp_data, dict):
            items = resp_data.get("list", [])
            total = resp_data.get("total", 0)
        elif isinstance(resp_data, list):
            items = resp_data
            total = len(items)

        for item in items:
            if not isinstance(item, dict):
                continue
            profiles.append({
                "id": item.get("id"),
                "seq": item.get("seq"),
                "name": item.get("name"),
                "group": item.get("groupName") or "未分组",
                "proxy_ip": item.get("host", "直连"),
                "status": "Running" if item.get("status") else "Closed",
                "created_at": item.get("createdAt", ""),
            })

        return total, profiles

    @classmethod
    def _parse_virtualbrowser_profiles(cls, data: dict) -> tuple[int, list]:
        """解析 VirtualBrowser 配置列表响应。"""
        profiles = []
        if data.get("code") != 0:
            return 0, profiles

        result = data.get("data", {})
        total = result.get("total", 0)

        for item in result.get("list", []):
            profiles.append({
                "id": item.get("id"),
                "name": item.get("name"),
                "group": item.get("groupName") or "未分组",
                "proxy_ip": item.get("proxyHost", "直连"),
                "status": "Running" if item.get("status") == 1 else "Closed",
                "created_at": item.get("createTime", ""),
            })

        return total, profiles

    @classmethod
    def create_profile(
        cls,
        name: str,
        remark: str = "",
        proxy: dict[str, Any] | None = None,
        fingerprint: dict[str, Any] | None = None,
        group_id: str | None = None,
    ) -> str:
        """Create a new browser profile."""
        browser_type = config.browser_type
        base_url = config.browser_api_url.rstrip("/")
        real_proxy: dict[str, Any] = proxy or {"type": "noproxy"}
        real_fingerprint: dict[str, Any] = fingerprint or {}

        if browser_type == "bitbrowser":
            url = f"{base_url}/browser/update"
            payload = cls._build_bitbrowser_payload(
                name, remark, group_id, real_proxy, real_fingerprint
            )
        else:
            url = f"{base_url}/api/v1/browser/add"
            payload: dict[str, Any] = {
                "name": name,
                "notes": remark,
                "groupId": group_id,
            }
            if real_proxy.get("type", "noproxy") != "noproxy":
                payload["proxy"] = {
                    "type": real_proxy.get("type"),
                    "host": real_proxy.get("host"),
                    "port": real_proxy.get("port"),
                    "username": real_proxy.get("user"),
                    "password": real_proxy.get("pass"),
                }

            fp_config_vb: dict[str, Any] = {}
            if real_fingerprint.get("os"):
                fp_config_vb["os"] = real_fingerprint["os"]
            if real_fingerprint.get("user_agent"):
                fp_config_vb["userAgent"] = real_fingerprint["user_agent"]
            if fp_config_vb:
                payload["fingerprint"] = fp_config_vb

        try:
            response = requests.post(
                url, json=payload, timeout=10, proxies={"http": None, "https": None} # type: ignore
            )
            try:
                data = response.json()
            except ValueError:
                raise RuntimeError(f"Invalid JSON from {url}: {response.text}")

            if browser_type == "bitbrowser":
                if data.get("success"):
                    return data["data"]["id"]
            else:
                if data.get("code") == 0:
                    return data["data"]["id"]

            error_msg = data.get("msg") or data.get("message") or str(data)
            raise RuntimeError(f"Failed to create profile: {error_msg}")
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"Browser API error: {e}")

    @classmethod
    def list_profiles(
        cls, page_num: int = 1, page_size: int = 10, name: str = ""
    ) -> dict[str, Any] | None:
        """List browser profiles from the browser API.
        
        Returns:
            dict with total and list, or None if connection fails.
        """
        browser_type = config.browser_type
        base_url = config.browser_api_url.rstrip("/")

        if browser_type == "bitbrowser":
            url = f"{base_url}/browser/list"
            payload = {"page": page_num - 1, "pageSize": page_size, "name": name}
        else:
            url = f"{base_url}/api/v1/browser/list"
            payload = {"page": page_num, "pageSize": page_size, "name": name}

        try:
            response = requests.post(
                url, json=payload, timeout=5, proxies={"http": None, "https": None} # type: ignore
            )
            data = response.json()

            if not isinstance(data, dict):
                print(f"Unexpected API response type: {type(data)}: {data}")
                return {"total": 0, "list": []}

            if browser_type == "bitbrowser":
                total, profiles = cls._parse_bitbrowser_profiles(data)
            else:
                total, profiles = cls._parse_virtualbrowser_profiles(data)

            return {"total": total, "list": profiles}
        except Exception as e:
            print(f"Error listing profiles: {e}")
            return None

    @classmethod
    def delete_profile(cls, profile_id: str) -> bool:
        """Delete a browser profile."""
        browser_type = config.browser_type
        base_url = config.browser_api_url.rstrip("/")

        if browser_type == "bitbrowser":
            url = f"{base_url}/browser/delete"
            payload = {"id": profile_id}
        else:
            url = f"{base_url}/api/v1/profile/delete"
            payload = {"profileId": profile_id}

        try:
            response = requests.post(
                url, json=payload, timeout=60, proxies={"http": None, "https": None} # type: ignore
            )
            data = response.json()
            return (
                data.get("success")
                if browser_type == "bitbrowser"
                else data.get("code") == 0
            )
        except Exception:
            return False

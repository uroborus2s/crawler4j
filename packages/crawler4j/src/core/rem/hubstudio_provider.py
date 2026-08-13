"""HubStudio local API client and browser environment provider."""

import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from src.core.rem.handle import BrowserHandle
from src.core.rem.models import Environment, EnvKind, EnvStatus, ProviderEnvInfo, ProxyConfig, ProxyMode
from src.core.rem.provider import BaseProvider, register_provider


class HubStudioClient:
    """Small wrapper around HubStudio's local HTTP API."""

    def __init__(self, port: int = 6873, api_key: str = ""):
        self.base_url = f"http://127.0.0.1:{port}"
        self.headers = {"Authorization": api_key} if api_key else {}
        self.client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self.client is None:
            self.client = httpx.AsyncClient(
                base_url=self.base_url, headers=self.headers, timeout=30.0, trust_env=False
            )
        return self.client

    async def request(self, path: str, payload: dict[str, Any]) -> Any:
        response = await (await self._get_client()).post(path, json=payload)
        try:
            body = response.json()
        except Exception as exc:
            raise RuntimeError(f"HubStudio API failed: HTTP {response.status_code}") from exc
        data = body.get("data") if isinstance(body, dict) else None
        if (
            not response.is_success
            or not isinstance(body, dict)
            or body.get("code") != 0
            or (isinstance(data, dict) and "statusCode" in data and str(data["statusCode"]) != "0")
        ):
            raise RuntimeError(f"HubStudio API failed: HTTP {response.status_code}")
        return data

    async def list_environments(self) -> list[dict[str, Any]]:
        data = await self.request("/api/v1/env/list", {})
        if isinstance(data, dict):
            data = data.get("list", [])
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []

    async def create_environment(self, payload: dict[str, Any]) -> str:
        data = await self.request("/api/v1/env/create", payload)
        code = data.get("containerCode") if isinstance(data, dict) else None
        if code is None or not str(code).strip():
            raise RuntimeError("HubStudio create response missing containerCode")
        return str(code)

    async def update_environment(self, container_code: str, config: dict[str, Any]) -> bool:
        await self.request("/api/v1/env/update", {"containerCode": container_code, **config})
        return True

    async def update_proxy(self, container_code: str, proxy: dict[str, Any]) -> bool:
        await self.request("/api/v1/env/proxy/update", {"containerCode": container_code, **proxy})
        return True

    async def import_cookies(self, container_code: str, cookies: list[dict[str, Any]]) -> bool:
        await self.request("/api/v1/env/import-cookie", {"containerCode": container_code, "cookie": json.dumps(cookies)})
        return True

    async def export_cookies(self, container_code: str) -> list[dict[str, Any]]:
        data = await self.request("/api/v1/env/export-cookie", {"containerCode": container_code})
        if isinstance(data, dict):
            data = data.get("cookie", data.get("cookies", []))
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError as exc:
                raise RuntimeError("HubStudio export-cookie returned invalid JSON") from exc
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []

    async def delete_environment(self, container_code: str) -> bool:
        await self.request("/api/v1/env/del", {"containerCodes": [container_code]})
        return True

    async def clear_cache(self, browser_ids: list[str]) -> bool:
        data = await self.request("/api/v1/cache/clear", {"browserOauths": browser_ids})
        if isinstance(data, dict):
            failed = {str(item) for item in data.get("failIds", [])}
            if failed.intersection(map(str, browser_ids)):
                raise RuntimeError("HubStudio clear cache failed")
        return True

    async def refresh_fingerprint(self, container_code: str) -> bool:
        await self.request("/api/v1/env/refresh-fingerprint", {"containerCode": container_code})
        return True

    async def start_browser(self, container_code: str, *, headless: bool = False) -> dict[str, Any]:
        data = await self.request(
            "/api/v1/browser/start", {"containerCode": container_code, "isHeadless": headless}
        )
        if not isinstance(data, dict):
            raise RuntimeError("HubStudio start response missing browser data")
        return data

    async def stop_browser(self, container_code: str) -> bool:
        await self.request("/api/v1/browser/stop", {"containerCode": container_code})
        return True

    async def all_browser_status(self, container_codes: list[str]) -> list[dict[str, Any]]:
        data = await self.request("/api/v1/browser/all-browser-status", {"containerCodes": container_codes})
        if isinstance(data, dict):
            data = data.get("containers", [])
        return [item for item in data if isinstance(item, dict)] if isinstance(data, list) else []


def _container_code(env: Environment) -> str | None:
    value = env.external_id or (env.handle.browser_id if env.handle else "")
    value = str(value or "").strip()
    return value or None


def _proxy_payload(proxy: Any, *, host_key: str = "proxyHost") -> dict[str, Any]:
    if not isinstance(proxy, dict):
        return {"asDynamicType": 0, "proxyTypeName": "不使用代理"}
    try:
        config = ProxyConfig.from_dict(proxy)
    except (TypeError, ValueError):
        config = ProxyConfig()
    raw = str(config.static_value or "").strip()
    if config.mode not in {ProxyMode.STATIC, ProxyMode.POOL} or not raw:
        return {"asDynamicType": 0, "proxyTypeName": "不使用代理"}
    parts = urlsplit(raw if "://" in raw else f"socks5://{raw}")
    types = {"http": "HTTP", "https": "HTTPS", "ssh": "SSH", "socks": "Socks5", "socks5": "Socks5"}
    if not parts.hostname or not parts.port:
        return {"asDynamicType": 0, "proxyTypeName": "不使用代理"}
    return {
        "asDynamicType": 0,
        "proxyTypeName": types.get(parts.scheme.lower(), "Socks5"),
        host_key: parts.hostname,
        "proxyPort": parts.port,
        "proxyAccount": parts.username or "",
        "proxyPassword": parts.password or "",
    }


def _proxy_from_row(row: dict[str, Any]) -> ProxyConfig | None:
    host, port = str(row.get("proxyHost") or "").strip(), row.get("proxyPort")
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = 0
    if not host or not port:
        return None
    kind = str(row.get("proxyTypeName") or "socks5").lower().replace(" ", "")
    scheme = {"socks5": "socks5", "http": "http", "https": "https", "ssh": "ssh"}.get(kind, "socks5")
    username, password = str(row.get("proxyAccount") or ""), str(row.get("proxyPassword") or "")
    auth = f"{username}:{password}@" if username or password else ""
    return ProxyConfig(mode=ProxyMode.STATIC, static_value=f"{scheme}://{auth}{host}:{port}", current_ip=host)


def _cookie_to_core(cookie: dict[str, Any]) -> dict[str, Any]:
    result = {
        "name": cookie.get("Name", cookie.get("name")),
        "value": cookie.get("Value", cookie.get("value")),
        "domain": cookie.get("Domain", cookie.get("domain")),
        "path": cookie.get("Path", cookie.get("path", "/")),
        "secure": bool(cookie.get("Secure", cookie.get("secure", False))),
        "httpOnly": bool(cookie.get("HttpOnly", cookie.get("httpOnly", False))),
    }
    expires = cookie.get("Expires", cookie.get("expires"))
    if isinstance(expires, str):
        try:
            expires = datetime.fromisoformat(expires.replace("Z", "+00:00")).timestamp()
        except ValueError:
            expires = None
    if expires not in (None, ""):
        result["expires"] = float(expires)
    same_site = cookie.get("Samesite", cookie.get("sameSite"))
    if str(same_site).lower() in {"lax", "strict", "none"}:
        result["sameSite"] = str(same_site).capitalize()
    return result


def _cookie_to_hub(cookie: dict[str, Any]) -> dict[str, Any]:
    result = {
        "Name": cookie["name"], "Value": cookie["value"], "Domain": cookie["domain"],
        "Path": cookie.get("path", "/"), "Secure": bool(cookie.get("secure", False)),
        "HttpOnly": bool(cookie.get("httpOnly", False)),
    }
    expires = cookie.get("expires")
    if expires not in (None, ""):
        result["Expires"] = datetime.fromtimestamp(float(expires), UTC).isoformat().replace("+00:00", "Z")
    same_site = cookie.get("sameSite")
    if str(same_site).lower() in {"lax", "strict", "none"}:
        result["Samesite"] = str(same_site).capitalize()
    return result


class HubStudioProvider(BaseProvider):
    name, display_name, kind = "hubstudio", "HubStudio", EnvKind.BROWSER

    def __init__(self) -> None:
        self._runtime_browser_ids: dict[str, str] = {}
        self._client_cache: HubStudioClient | None = None
        self._client_config: tuple[Any, Any] | None = None

    def _get_api_client(self) -> HubStudioClient:
        from src.core.system.config_center import get_config_center

        config = get_config_center()
        values = (config.get("browser.hubstudio.port") or 6873, config.get("browser.hubstudio.apikey") or "")
        if self._client_cache is None or self._client_config != values:
            self._client_cache, self._client_config = HubStudioClient(*values), values
        return self._client_cache

    async def create(self, config: dict[str, Any] | None = None) -> Environment:
        config = config or {}
        params = config.get("creation_params", {}).get("hubstudio", {})
        params = dict(params) if isinstance(params, dict) else {}
        name = str(config.get("env_name") or params.pop("containerName", "hubstudio-env"))
        proxy = config.get("proxy") or params.pop("proxy", {})
        payload = {
            "containerName": name,
            "asDynamicType": 0,
            "proxyTypeName": "不使用代理",
            "labels": [],
            **params,
            **_proxy_payload(proxy, host_key="proxyServer"),
        }
        code = await self._get_api_client().create_environment(payload)
        return Environment(name=name, kind=self.kind, provider=self.name, status=EnvStatus.READY, external_id=code,
                           capabilities={"page", "cookies", "fingerprint"}, handle=BrowserHandle(browser_id=code),
                           proxy_config=ProxyConfig.from_dict(config["proxy"]) if config.get("proxy") else None)

    async def open(self, env: Environment) -> bool:
        code = _container_code(env)
        if not code:
            return False
        data = await self._get_api_client().start_browser(code)
        runtime_id, port = data.get("browserID"), data.get("debuggingPort")
        if runtime_id is None or port is None:
            return False
        env.external_id = code
        env.handle = env.handle or BrowserHandle(browser_id=code)
        env.handle.browser_id, env.handle.ws_url = code, f"http://127.0.0.1:{port}"
        self._runtime_browser_ids[code] = str(runtime_id)
        return True

    async def connect(self, env: Environment) -> bool:
        return bool(env.handle and env.handle.ws_url and await env.handle.safe_connect())

    async def close(self, env: Environment) -> bool:
        code = _container_code(env)
        if not code:
            return True
        if env.handle:
            await env.handle.safe_close()
        await self._get_api_client().stop_browser(code)
        self._runtime_browser_ids.pop(code, None)
        env.handle = BrowserHandle(browser_id=code)
        return True

    async def destroy(self, env: Environment) -> bool:
        code = _container_code(env)
        if not code:
            return False
        if env.handle:
            await env.handle.safe_close()
        self._runtime_browser_ids.pop(code, None)
        if await self.is_window_open(env):
            await self._get_api_client().stop_browser(code)
        return await self._get_api_client().delete_environment(code)

    async def is_window_open(self, env: Environment) -> bool:
        code = _container_code(env)
        if not code:
            return False
        return any(
            str(item.get("containerCode")) == code and item.get("status") == 0
            for item in await self._get_api_client().all_browser_status([code])
        )

    async def is_running(self, env: Environment) -> bool:
        return bool(env.handle and env.handle.is_connected())

    async def exists(self, env: Environment) -> bool:
        code = _container_code(env)
        return bool(code and any(str(item.get("containerCode")) == code for item in await self._get_api_client().list_environments()))

    async def health_check(self, env: Environment) -> bool:
        return bool(env.handle and env.handle.is_connected() and await self.is_window_open(env))

    async def update(self, env: Environment, config: dict) -> bool:
        code = _container_code(env)
        if not code:
            return False
        client, ok = self._get_api_client(), False
        if config.get("name"):
            ok = await client.update_environment(code, {"containerName": config["name"]})
        if "proxy" in config:
            ok = await client.update_proxy(code, _proxy_payload(config["proxy"])) or ok
        if config.get("randomize_fingerprint"):
            ok = await client.refresh_fingerprint(code) or ok
        return ok

    async def clear_cache(self, env: Environment) -> bool:
        code = _container_code(env)
        if not code:
            raise RuntimeError("HubStudio environment missing containerCode")
        client, runtime_id = self._get_api_client(), self._runtime_browser_ids.get(code)
        temporary = runtime_id is None
        if temporary:
            data = await client.start_browser(code, headless=True)
            runtime_id = str(data.get("browserID") or "")
            if not runtime_id:
                raise RuntimeError("HubStudio start response missing browserID")
            await client.stop_browser(code)
        else:
            await client.stop_browser(code)
            self._runtime_browser_ids.pop(code, None)
        return await client.clear_cache([runtime_id])

    async def reset(self, env: Environment) -> bool:
        return await self.clear_cache(env)

    async def get_persisted_cookies(self, env: Environment) -> list[dict[str, Any]]:
        code = _container_code(env)
        if not code:
            raise RuntimeError("HubStudio environment missing containerCode")
        return [_cookie_to_core(cookie) for cookie in await self._get_api_client().export_cookies(code)]

    async def replace_persisted_cookies(self, env: Environment, cookies: list[dict[str, Any]]) -> None:
        code = _container_code(env)
        if not code:
            raise RuntimeError("HubStudio environment missing containerCode")
        await self._get_api_client().import_cookies(code, [_cookie_to_hub(cookie) for cookie in cookies])

    def supports_existing_env_import(self) -> bool:
        return True

    async def list_existing_envs(self) -> list[ProviderEnvInfo]:
        infos = []
        for row in await self._get_api_client().list_environments():
            code = row.get("containerCode")
            if code is None:
                continue
            proxy = _proxy_from_row(row)
            infos.append(ProviderEnvInfo(provider=self.name, provider_label=self.display_name, external_id=str(code),
                name=str(row.get("containerName", row.get("name", code))), proxy_config=proxy,
                proxy_summary=proxy.static_value if proxy else "", remark=str(row.get("remark") or "")))
        return sorted(infos, key=lambda item: (item.name.lower(), item.external_id))

    async def build_imported_environment(self, info: ProviderEnvInfo) -> Environment:
        env = await super().build_imported_environment(info)
        env.capabilities = {"page", "cookies", "fingerprint"}
        env.handle = BrowserHandle(browser_id=str(info.external_id))
        return env


register_provider(HubStudioProvider())

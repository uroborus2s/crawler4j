from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.rem.handle import BrowserHandle
from src.core.rem.hubstudio_provider import HubStudioClient, HubStudioProvider
from src.core.rem.models import EnvKind, EnvStatus, Environment
from src.core.rem.provider import get_provider


def test_direct_import_registers_hubstudio_provider():
    assert isinstance(get_provider("hubstudio"), HubStudioProvider)


@pytest.mark.asyncio
async def test_client_uses_loopback_without_ambient_proxy_and_optional_authorization(monkeypatch):
    captured = {}

    class _AsyncClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr("src.core.rem.hubstudio_provider.httpx.AsyncClient", _AsyncClient)
    await HubStudioClient(6873, "key")._get_client()
    assert captured["base_url"] == "http://127.0.0.1:6873"
    assert captured["headers"] == {"Authorization": "key"}
    assert captured["trust_env"] is False
    assert HubStudioClient().headers == {}


class _Response:
    def __init__(self, payload, status_code=200, json_error=False):
        self._payload = payload
        self.status_code = status_code
        self.is_success = 200 <= status_code < 400
        self.text = "response body"
        self.json_error = json_error

    def json(self):
        if self.json_error:
            raise ValueError("invalid json")
        return self._payload


class _Http:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def post(self, path, json):
        self.calls.append((path, json))
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_client_requires_http_and_hubstudio_success_contract():
    client = HubStudioClient(6873)
    client._get_client = AsyncMock(return_value=_Http(_Response({"code": 1, "msg": "nope"})))
    with pytest.raises(RuntimeError, match="HubStudio API failed"):
        await client.request("/api/v1/env/list", {})

    client._get_client = AsyncMock(return_value=_Http(_Response({"code": 0}, status_code=500)))
    with pytest.raises(RuntimeError, match="HubStudio API failed"):
        await client.request("/api/v1/env/list", {})

    client._get_client = AsyncMock(return_value=_Http(_Response({"code": 0, "data": {"statusCode": "1"}})))
    with pytest.raises(RuntimeError, match="HubStudio API failed"):
        await client.request("/api/v1/browser/start", {})

    client._get_client = AsyncMock(return_value=_Http(_Response({}, json_error=True)))
    with pytest.raises(RuntimeError, match="HubStudio API failed"):
        await client.request("/api/v1/env/list", {})


@pytest.mark.asyncio
async def test_client_operations_and_cookie_wire_format():
    client = HubStudioClient(6873)
    http = _Http(
        _Response({"code": 0, "data": {"containerCode": 42}}),
        _Response({"code": 0, "data": {}}),
        _Response({"code": 0, "data": '[{"Name":"sid","Value":"secret","Domain":".a.test","Path":"/","Secure":true,"HttpOnly":true,"Expires":"2028-01-02T03:04:05Z","Samesite":"lax"}]'}),
    )
    client._get_client = AsyncMock(return_value=http)
    assert await client.create_environment({"name": "e"}) == "42"
    await client.import_cookies("42", [{"Name": "sid", "Value": "secret", "Domain": ".a.test", "Path": "/", "Secure": True, "HttpOnly": True, "Expires": "2028-01-02T03:04:05Z", "Samesite": "Lax"}])
    assert http.calls[1][0] == "/api/v1/env/import-cookie"
    wire_cookies = pytest.importorskip("json").loads(http.calls[1][1]["cookie"])
    assert wire_cookies[0]["Name"] == "sid"
    assert wire_cookies[0]["Samesite"] == "Lax"
    cookies = await client.export_cookies("42")
    assert cookies[0]["Name"] == "sid"


@pytest.mark.asyncio
async def test_client_reads_containers_status_and_lists_without_undeclared_paging():
    client = HubStudioClient(6873)
    http = _Http(
        _Response({"code": 0, "data": {"list": [{"containerCode": 1}]}}),
        _Response({"code": 0, "data": {"containers": [{"containerCode": 1, "status": "running"}]}}),
    )
    client._get_client = AsyncMock(return_value=http)
    assert await client.list_environments() == [{"containerCode": 1}]
    assert http.calls[0] == ("/api/v1/env/list", {})
    assert await client.all_browser_status(["1"]) == [{"containerCode": 1, "status": "running"}]
    assert http.calls[1] == ("/api/v1/browser/all-browser-status", {"containerCodes": ["1"]})


@pytest.mark.asyncio
async def test_client_clear_cache_rejects_partial_failure():
    client = HubStudioClient(6873)
    client._get_client = AsyncMock(return_value=_Http(_Response({"code": 0, "data": {"statusCode": "0", "failIds": ["88"]}})))
    with pytest.raises(RuntimeError, match="clear cache failed"):
        await client.clear_cache(["88"])


@pytest.mark.asyncio
async def test_provider_converts_cookies_both_directions(monkeypatch):
    provider = HubStudioProvider()
    client = SimpleNamespace(
        export_cookies=AsyncMock(return_value=[{"Name": "sid", "Value": "secret", "Domain": ".a.test", "Path": "/", "Secure": True, "HttpOnly": True, "Expires": "2028-01-02T03:04:05Z", "Samesite": "lax"}]),
        import_cookies=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    env = Environment(external_id="42", handle=BrowserHandle(browser_id="42"))
    assert (await provider.get_persisted_cookies(env))[0]["sameSite"] == "Lax"
    await provider.replace_persisted_cookies(env, [{"name": "sid", "value": "secret", "domain": ".a.test", "path": "/", "secure": True, "httpOnly": True, "sameSite": "Unknown"}])
    assert "Samesite" not in client.import_cookies.await_args.args[1][0]


@pytest.mark.asyncio
async def test_provider_create_start_close_destroy_status_connect_and_health(monkeypatch):
    provider = HubStudioProvider()
    client = SimpleNamespace(
        create_environment=AsyncMock(return_value="42"),
        start_browser=AsyncMock(return_value={"browserID": 99, "debuggingPort": "59591"}),
        stop_browser=AsyncMock(return_value=True),
        delete_environment=AsyncMock(return_value=True),
        all_browser_status=AsyncMock(return_value=[{"containerCode": "42", "status": 0}]),
        list_environments=AsyncMock(return_value=[{"containerCode": "42", "name": "hub-env"}]),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    env = await provider.create({"env_name": "hub-env"})
    assert env.external_id == env.handle.browser_id == "42"
    assert (await provider.open(env)) is True
    assert env.handle.ws_url == "http://127.0.0.1:59591"
    assert provider._runtime_browser_ids == {"42": "99"}
    monkeypatch.setattr(env.handle, "safe_connect", AsyncMock(return_value=True))
    monkeypatch.setattr(env.handle, "is_connected", lambda: True)
    assert await provider.connect(env) is True
    assert await provider.health_check(env) is True
    assert await provider.is_window_open(env) is True
    assert await provider.exists(env) is True
    monkeypatch.setattr(env.handle, "safe_close", AsyncMock())
    assert await provider.close(env) is True
    assert env.handle.browser_id == "42"
    assert "42" not in provider._runtime_browser_ids
    assert await provider.destroy(env) is True


@pytest.mark.asyncio
@pytest.mark.parametrize("status, expected", [(0, True), (1, False), (2, False), (3, False)])
async def test_provider_window_status_queries_only_target_and_requires_open_status(monkeypatch, status, expected):
    provider = HubStudioProvider()
    client = SimpleNamespace(all_browser_status=AsyncMock(return_value=[{"containerCode": "42", "status": status}]))
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    env = Environment(external_id="42")
    assert await provider.is_window_open(env) is expected
    client.all_browser_status.assert_awaited_once_with(["42"])


@pytest.mark.asyncio
async def test_provider_create_uses_create_proxy_server_and_fingerprint_capability(monkeypatch):
    provider = HubStudioProvider()
    client = SimpleNamespace(create_environment=AsyncMock(return_value="42"))
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    env = await provider.create({"env_name": "hub-env", "proxy": {"mode": "static", "static_value": "socks5://u:p@host:1080"}})
    payload = client.create_environment.await_args.args[0]
    assert payload["proxyServer"] == "host"
    assert "proxyHost" not in payload
    assert env.capabilities == {"page", "cookies", "fingerprint"}


@pytest.mark.asyncio
async def test_provider_update_proxy_refresh_cache_and_imported_envs(monkeypatch):
    provider = HubStudioProvider()
    client = SimpleNamespace(
        update_environment=AsyncMock(return_value=True),
        update_proxy=AsyncMock(return_value=True),
        refresh_fingerprint=AsyncMock(return_value=True),
        clear_cache=AsyncMock(return_value=True),
        start_browser=AsyncMock(return_value={"browserID": 88, "debuggingPort": 50001}),
        stop_browser=AsyncMock(return_value=True),
        list_environments=AsyncMock(return_value=[{"containerCode": 7, "name": "imported", "proxyType": "socks5", "proxyHost": "127.0.0.1", "proxyPort": 1080}]),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    env = Environment(name="e", kind=EnvKind.BROWSER, provider="hubstudio", status=EnvStatus.READY, external_id="42", handle=BrowserHandle(browser_id="42"))
    assert await provider.update(env, {"name": "renamed", "proxy": {"mode": "static", "static_value": "socks5://u:p@host:1080"}, "randomize_fingerprint": True})
    assert client.update_environment.await_count == 1
    assert client.update_proxy.await_count == 1
    proxy_payload = client.update_proxy.await_args.args[1]
    assert proxy_payload["proxyHost"] == "host"
    assert "proxyServer" not in proxy_payload
    assert client.refresh_fingerprint.await_count == 1
    assert await provider.clear_cache(env) is True
    assert client.clear_cache.await_args.args == (["88"],)
    assert client.stop_browser.await_args.args == ("42",)
    infos = await provider.list_existing_envs()
    assert infos[0].external_id == "7"
    imported = await provider.build_imported_environment(infos[0])
    assert imported.external_id == imported.handle.browser_id == "7"
    assert imported.capabilities == {"page", "cookies", "fingerprint"}


@pytest.mark.asyncio
async def test_clear_cache_stops_temporary_browser_before_clearing(monkeypatch):
    provider = HubStudioProvider()
    calls = []

    async def start(container_code, *, headless=False):
        calls.append(("start", container_code, headless))
        return {"browserID": 88, "debuggingPort": 50001}

    async def stop(container_code):
        calls.append(("stop", container_code))
        return True

    async def clear(browser_ids):
        calls.append(("clear", browser_ids))
        return True

    client = SimpleNamespace(start_browser=start, stop_browser=stop, clear_cache=clear)
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    assert await provider.clear_cache(Environment(external_id="42")) is True
    assert calls == [("start", "42", True), ("stop", "42"), ("clear", ["88"])]


@pytest.mark.asyncio
async def test_clear_cache_stops_cached_browser_before_clearing_and_forgets_runtime_id(monkeypatch):
    provider = HubStudioProvider()
    provider._runtime_browser_ids["42"] = "88"
    calls = []

    async def stop(container_code):
        calls.append(("stop", container_code))
        return True

    async def clear(browser_ids):
        calls.append(("clear", browser_ids))
        return True

    monkeypatch.setattr(provider, "_get_api_client", lambda: SimpleNamespace(stop_browser=stop, clear_cache=clear))
    assert await provider.clear_cache(Environment(external_id="42")) is True
    assert calls == [("stop", "42"), ("clear", ["88"])]
    assert "42" not in provider._runtime_browser_ids


@pytest.mark.asyncio
async def test_destroy_stops_open_browser_before_deleting(monkeypatch):
    provider = HubStudioProvider()
    calls = []

    async def status(_container_codes):
        return [{"containerCode": "42", "status": 0}]

    async def stop(container_code):
        calls.append(("stop", container_code))
        return True

    async def delete(container_code):
        calls.append(("delete", container_code))
        return True

    env = Environment(external_id="42", handle=BrowserHandle(browser_id="42"))
    monkeypatch.setattr(env.handle, "safe_close", AsyncMock())
    monkeypatch.setattr(provider, "_get_api_client", lambda: SimpleNamespace(all_browser_status=status, stop_browser=stop, delete_environment=delete))
    assert await provider.destroy(env) is True
    env.handle.safe_close.assert_awaited_once()
    assert calls == [("stop", "42"), ("delete", "42")]

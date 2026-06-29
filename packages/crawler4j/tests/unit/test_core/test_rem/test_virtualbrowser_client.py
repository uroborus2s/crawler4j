import httpx
import pytest
from unittest.mock import AsyncMock
from types import SimpleNamespace

import src.core.rem.provider as provider_module
from src.core.rem.models import EnvKind, EnvStatus, Environment
from src.core.rem.provider import VirtualBrowserClient


class _DummyResponse:
    def __init__(self, payload, *, response_data=None, success=True, status_code=200, error_message=""):
        self._payload = payload
        self._response_data = response_data if response_data is not None else {"id": 101}
        self._success = success
        self.status_code = status_code
        self._error_message = error_message
        self.text = (
            '{"success":true}'
            if success
            else f'{{"success":false,"error":"{error_message}"}}'
        )

    @property
    def is_success(self):
        return 200 <= self.status_code < 400

    def raise_for_status(self):
        if self.is_success:
            return None
        request = httpx.Request("POST", "http://localhost/test")
        response = httpx.Response(self.status_code, request=request, text=self.text)
        raise httpx.HTTPStatusError("dummy failure", request=request, response=response)

    def json(self):
        payload = {"success": self._success, "echo": self._payload}
        if self._success:
            payload["data"] = self._response_data
        elif self._error_message:
            payload["error"] = self._error_message
        return payload


class _DummyHttpClient:
    def __init__(self, *, response_data=None, responses=None, get_responses=None):
        self.last_path = None
        self.last_payload = None
        self.last_get_path = None
        self.last_get_payload = None
        self._response_data = response_data
        self._responses = list(responses or [])
        self._get_responses = list(get_responses or [])
        self.calls: list[tuple[str, dict]] = []
        self.get_calls: list[str] = []

    async def post(self, path, json):
        self.last_path = path
        self.last_payload = json
        self.calls.append((path, json))
        if self._responses:
            response = self._responses.pop(0)
            if isinstance(response, _DummyResponse):
                return response
            return _DummyResponse(json, **response)
        return _DummyResponse(json, response_data=self._response_data)

    async def get(self, path):
        self.last_get_path = path
        self.last_get_payload = {}
        self.get_calls.append(path)
        if self._get_responses:
            response = self._get_responses.pop(0)
            if isinstance(response, _DummyResponse):
                return response
            return _DummyResponse({}, **response)
        return _DummyResponse({}, response_data=self._response_data)


def test_virtualbrowser_client_uses_loopback_base_url():
    client = VirtualBrowserClient(port=9002, api_key="")

    assert client.base_url == "http://127.0.0.1:9002"


@pytest.mark.asyncio
async def test_add_browser_defaults_to_no_proxy_when_proxy_not_provided():
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient()

    # patch async getter explicitly to keep test deterministic
    async def _fake_get_client():
        return dummy

    client._get_client = _fake_get_client  # type: ignore[method-assign]

    browser_id = await client.add_browser(name="env-a", group_ids=[])

    assert browser_id == 101
    assert dummy.last_path == "/api/addBrowser"
    assert dummy.last_payload["proxy"]["mode"] == 1
    assert dummy.last_payload["proxy"]["host"] == ""


@pytest.mark.asyncio
async def test_list_browsers_returns_browser_entries():
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient(
        response_data=[
            {"id": 1, "name": "env-1"},
            {"id": 2, "name": "env-2"},
        ]
    )

    async def _fake_get_client():
        return dummy

    client._get_client = _fake_get_client  # type: ignore[method-assign]

    browsers = await client.list_browsers()

    assert dummy.last_get_path == "/api/getBrowserList"
    assert browsers == [{"id": 1, "name": "env-1"}, {"id": 2, "name": "env-2"}]


@pytest.mark.asyncio
async def test_get_browser_full_parameters_without_id_returns_all_rows():
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient(
        response_data=[
            {"id": 1, "name": "env-1", "remark": "demo"},
            {"id": 2, "name": "env-2", "remark": "demo-2"},
        ]
    )

    async def _fake_get_client():
        return dummy

    client._get_client = _fake_get_client  # type: ignore[method-assign]

    payload = await client.get_browser_full_parameters()

    assert dummy.last_get_path == "/api/getBrowserFullParameters"
    assert payload == [
        {"id": 1, "name": "env-1", "remark": "demo"},
        {"id": 2, "name": "env-2", "remark": "demo-2"},
    ]


@pytest.mark.asyncio
async def test_add_browser_uses_canonical_proxy_keys_and_enables_custom_mode():
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient()

    async def _fake_get_client():
        return dummy

    client._get_client = _fake_get_client  # type: ignore[method-assign]

    await client.add_browser(
        name="env-b",
        group_ids=["g1"],
        proxy={
            "protocol": "socks5",
            "host": "127.0.0.1",
            "port": "1080",
            "user": "u",
            "pass": "p",
        },
    )

    proxy = dummy.last_payload["proxy"]
    assert proxy["mode"] == 2
    assert proxy["protocol"] == "SOCKS5"
    assert proxy["user"] == "u"
    assert proxy["pass"] == "p"


@pytest.mark.asyncio
async def test_add_browser_surfaces_http_failure_response_body(monkeypatch):
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient(
        responses=[
            {
                "success": False,
                "status_code": 500,
                "error_message": "ERR_PROXY_AUTHENTICATION_FAILED",
            }
        ]
    )
    error_messages: list[str] = []

    async def _fake_get_client():
        return dummy

    client._get_client = _fake_get_client  # type: ignore[method-assign]
    monkeypatch.setattr(provider_module.logger, "error", lambda message: error_messages.append(str(message)))

    with pytest.raises(
        RuntimeError,
        match=r"VirtualBrowser addBrowser 失败: status=500 body=\{\"success\":false,\"error\":\"ERR_PROXY_AUTHENTICATION_FAILED\"\}",
    ):
        await client.add_browser(
            name="env-error",
            group_ids=[],
            proxy={
                "protocol": "http",
                "host": "127.0.0.1",
                "port": 8080,
                "user": "bad-user",
                "pass": "bad-pass",
            },
        )

    assert len(error_messages) == 1
    assert "endpoint=http://127.0.0.1:9002" in error_messages[0]
    assert 'status=500 body={"success":false,"error":"ERR_PROXY_AUTHENTICATION_FAILED"}' in error_messages[0]
    assert "bad-user" in error_messages[0]
    assert "bad-pass" not in error_messages[0]
    assert '"pass": "***"' in error_messages[0]


@pytest.mark.asyncio
async def test_add_browser_retries_relay_failure_before_success(monkeypatch):
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient(
        responses=[
            {
                "success": False,
                "status_code": 500,
                "error_message": "Relay failed to localhost:9000",
            },
            {
                "response_data": {"id": 202},
            },
        ]
    )
    warning_messages: list[str] = []
    sleep_delays: list[float] = []

    async def _fake_get_client():
        return dummy

    async def _fake_sleep(delay):
        sleep_delays.append(delay)

    client._get_client = _fake_get_client  # type: ignore[method-assign]
    monkeypatch.setattr(provider_module.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(provider_module.logger, "warning", lambda message: warning_messages.append(str(message)))

    browser_id = await client.add_browser(
        name="env-retry",
        group_ids=[],
        proxy={
            "protocol": "socks5",
            "host": "127.0.0.1",
            "port": 1080,
            "user": "u",
            "pass": "secret",
        },
    )

    assert browser_id == 202
    assert [path for path, _ in dummy.calls] == ["/api/addBrowser", "/api/addBrowser"]
    assert sleep_delays == [provider_module.VIRTUALBROWSER_ADD_BROWSER_RETRY_DELAY_SECONDS]
    assert len(warning_messages) == 1
    assert "Relay failed to localhost:9000" in warning_messages[0]
    assert "secret" not in warning_messages[0]
    assert '"pass": "***"' in warning_messages[0]


@pytest.mark.asyncio
async def test_add_browser_materializes_randomize_fingerprint_template(monkeypatch):
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient()

    async def _fake_get_client():
        return dummy

    client._get_client = _fake_get_client  # type: ignore[method-assign]
    monkeypatch.setattr(
        provider_module,
        "materialize_virtualbrowser_fingerprint",
        lambda fingerprint, *, default_chrome_version: (
            144,
            {},
        ),
    )

    await client.add_browser(
        name="env-c",
        group_ids=["g1"],
        fingerprint={
            "chrome_version": 144,
            "__randomize_fingerprint__": True,
        },
    )

    assert dummy.calls == [
        (
            "/api/addBrowser",
            {
                "name": "env-c",
                "group": ["g1"],
                "chrome_version": 144,
                "proxy": {
                    "mode": 1,
                    "value": "",
                    "protocol": "",
                    "host": "",
                    "port": "",
                    "user": "",
                    "pass": "",
                    "API": "",
                },
            },
        )
    ]


@pytest.mark.asyncio
async def test_add_browser_strips_legacy_randomize_marker_without_compat_behavior():
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient()

    async def _fake_get_client():
        return dummy

    client._get_client = _fake_get_client  # type: ignore[method-assign]

    await client.add_browser(
        name="env-d",
        group_ids=["g1"],
        fingerprint={
            "chrome_version": 145,
            "__randomize_after_create__": True,
            "fonts": {"mode": 1},
        },
    )

    assert dummy.calls == [
        (
            "/api/addBrowser",
            {
                "name": "env-d",
                "group": ["g1"],
                "chrome_version": 145,
                "proxy": {
                    "mode": 1,
                    "value": "",
                    "protocol": "",
                    "host": "",
                    "port": "",
                    "user": "",
                    "pass": "",
                    "API": "",
                },
                "fonts": {"mode": 1},
            },
        )
    ]


@pytest.mark.asyncio
async def test_add_browser_passes_proxy_geo_to_fingerprint_materializer(monkeypatch):
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient()
    seen_geo = None

    async def _fake_get_client():
        return dummy

    def _fake_materialize(fingerprint, *, default_chrome_version, geo):  # noqa: ARG001
        nonlocal seen_geo
        seen_geo = geo
        return 145, {"time-zone": {"utc": geo["timezone"]}}

    client._get_client = _fake_get_client  # type: ignore[method-assign]
    monkeypatch.setattr(provider_module, "materialize_virtualbrowser_fingerprint", _fake_materialize)

    await client.add_browser(
        name="env-geo",
        group_ids=[],
        fingerprint={
            "chrome_version": 145,
            "__randomize_fingerprint__": True,
        },
        geo={"country_code": "JP", "timezone": "Asia/Tokyo"},
    )

    assert seen_geo == {"country_code": "JP", "timezone": "Asia/Tokyo"}
    assert dummy.last_payload["time-zone"] == {"utc": "Asia/Tokyo"}


@pytest.mark.asyncio
async def test_launch_browser_uses_ws_field_when_available():
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient(response_data={"ws": "ws://127.0.0.1:9222/devtools/browser/abc"})

    async def _fake_get_client():
        return dummy

    client._get_client = _fake_get_client  # type: ignore[method-assign]

    endpoint = await client.launch_browser(101)

    assert dummy.last_path == "/api/launchBrowser"
    assert endpoint == "ws://127.0.0.1:9222/devtools/browser/abc"


@pytest.mark.asyncio
async def test_launch_browser_falls_back_to_debugging_port():
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient(response_data={"debuggingPort": 56764})

    async def _fake_get_client():
        return dummy

    client._get_client = _fake_get_client  # type: ignore[method-assign]

    endpoint = await client.launch_browser(101)

    assert endpoint == "http://localhost:56764"


@pytest.mark.asyncio
async def test_virtualbrowser_connect_recovers_ws_url_from_running_detail(monkeypatch):
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient(
        get_responses=[
            {
                "response_data": {
                    "data": [
                        {
                            "id": 1,
                            "name": "1",
                            "debuggingPort": 57204,
                            "webdriverPath": "/tmp/driver",
                        }
                    ]
                }
            },
        ]
    )

    async def _fake_get_client():
        return dummy

    client._get_client = _fake_get_client  # type: ignore[method-assign]

    runtime_detail = await client.get_browser_runtime_detail(1)

    assert runtime_detail is not None
    assert dummy.get_calls == ["/api/getBrowserRunningList"]
    assert provider_module._extract_cdp_endpoint(runtime_detail) == "http://localhost:57204"


@pytest.mark.asyncio
async def test_virtualbrowser_connect_recovers_missing_ws_url_from_running_detail(monkeypatch):
    provider = provider_module.VirtualBrowserProvider()
    env = Environment(
        id=101,
        name="vb-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.BUSY,
        handle=provider_module.BrowserHandle(browser_id="1"),
    )
    handle = env.handle
    assert handle is not None

    client = SimpleNamespace(
        get_browser_runtime_detail=AsyncMock(
            return_value={
                "id": 1,
                "name": "1",
                "debuggingPort": 57204,
                "webdriverPath": "/tmp/driver",
            }
        )
    )

    provider._get_api_client = lambda: client  # type: ignore[method-assign]
    monkeypatch.setattr(handle, "safe_connect", AsyncMock(return_value=True))

    success = await provider.connect(env)

    assert success is True
    assert handle.ws_url == "http://localhost:57204"
    client.get_browser_runtime_detail.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_launch_browser_retries_after_recoverable_devtools_failure():
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient(
        responses=[
            {
                "success": False,
                "status_code": 500,
                "error_message": "Browser process closed before DevTools port was detected.",
            },
            {},
            {
                "response_data": {"debuggingPort": 56764},
            },
        ]
    )

    async def _fake_get_client():
        return dummy

    client._get_client = _fake_get_client  # type: ignore[method-assign]

    endpoint = await client.launch_browser(101)

    assert endpoint == "http://localhost:56764"
    assert dummy.calls == [
        ("/api/launchBrowser", {"id": 101}),
        ("/api/stopBrowser", {"id": 101}),
        ("/api/launchBrowser", {"id": 101}),
    ]


@pytest.mark.asyncio
async def test_launch_browser_retries_after_running_conflict():
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient(
        responses=[
            {
                "success": False,
                "status_code": 400,
                "error_message": "browser(id: 101) is running",
            },
            {},
            {
                "response_data": {"debuggingPort": 56764},
            },
        ]
    )

    async def _fake_get_client():
        return dummy

    client._get_client = _fake_get_client  # type: ignore[method-assign]

    endpoint = await client.launch_browser(101)

    assert endpoint == "http://localhost:56764"
    assert dummy.calls == [
        ("/api/launchBrowser", {"id": 101}),
        ("/api/stopBrowser", {"id": 101}),
        ("/api/launchBrowser", {"id": 101}),
    ]

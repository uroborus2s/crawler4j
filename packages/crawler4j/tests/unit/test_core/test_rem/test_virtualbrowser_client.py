import httpx
import pytest

import src.core.rem.provider as provider_module
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
    def __init__(self, *, response_data=None, responses=None):
        self.last_path = None
        self.last_payload = None
        self._response_data = response_data
        self._responses = list(responses or [])
        self.calls: list[tuple[str, dict]] = []

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
            "protocol": "SOCKS5",
            "host": "127.0.0.1",
            "port": "1080",
            "user": "u",
            "pass": "p",
        },
    )

    proxy = dummy.last_payload["proxy"]
    assert proxy["mode"] == 2
    assert proxy["protocol"] == "socks5"
    assert proxy["user"] == "u"
    assert proxy["pass"] == "p"


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
            {
                "ua": {"mode": 1, "value": "Mozilla/5.0 Random"},
                "device-name": {"mode": 1, "value": "Q7M2P9X4K3A1B5C6D"},
                "mac": {"mode": 1, "value": "02-76-66-51-39-C9"},
                "fonts": {"mode": 1},
            },
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
                "ua": {"mode": 1, "value": "Mozilla/5.0 Random"},
                "device-name": {"mode": 1, "value": "Q7M2P9X4K3A1B5C6D"},
                "mac": {"mode": 1, "value": "02-76-66-51-39-C9"},
                "fonts": {"mode": 1},
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

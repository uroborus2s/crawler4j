import pytest

from src.core.rem.provider import VirtualBrowserClient


class _DummyResponse:
    def __init__(self, payload, *, response_data=None):
        self._payload = payload
        self._response_data = response_data if response_data is not None else {"id": 101}

    def raise_for_status(self):
        return None

    def json(self):
        return {"success": True, "data": self._response_data, "echo": self._payload}


class _DummyHttpClient:
    def __init__(self, *, response_data=None):
        self.last_path = None
        self.last_payload = None
        self._response_data = response_data

    async def post(self, path, json):
        self.last_path = path
        self.last_payload = json
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

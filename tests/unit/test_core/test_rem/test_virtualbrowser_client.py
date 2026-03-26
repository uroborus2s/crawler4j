import pytest

from src.core.rem.provider import VirtualBrowserClient


class _DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return {"success": True, "data": {"id": 101}, "echo": self._payload}


class _DummyHttpClient:
    def __init__(self):
        self.last_path = None
        self.last_payload = None

    async def post(self, path, json):
        self.last_path = path
        self.last_payload = json
        return _DummyResponse(json)


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
async def test_add_browser_normalizes_proxy_keys_and_enables_custom_mode():
    client = VirtualBrowserClient(port=9002, api_key="")
    dummy = _DummyHttpClient()

    async def _fake_get_client():
        return dummy

    client._get_client = _fake_get_client  # type: ignore[method-assign]

    await client.add_browser(
        name="env-b",
        group_ids=["g1"],
        proxy={
            "type": "SOCKS5",
            "host": "127.0.0.1",
            "port": "1080",
            "username": "u",
            "password": "p",
        },
    )

    proxy = dummy.last_payload["proxy"]
    assert proxy["mode"] == 2
    assert proxy["protocol"] == "socks5"
    assert proxy["user"] == "u"
    assert proxy["pass"] == "p"

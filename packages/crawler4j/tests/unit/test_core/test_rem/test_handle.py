from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core.rem.handle import BrowserHandle, PlaywrightManager, CDP_CONNECT_TIMEOUT_MS


class _FakePage:
    pass


class _FakeContext:
    def __init__(self, page):
        self.pages = [page]

    async def new_page(self):
        return _FakePage()


class _FakeBrowser:
    def __init__(self, context):
        self.contexts = [context]

    def is_connected(self):
        return True

    async def close(self):
        return None


def test_candidate_cdp_endpoints_strip_json_version_suffix():
    candidates = BrowserHandle._candidate_cdp_endpoints("http://127.0.0.1:9222/json/version/")

    assert candidates[0] == "http://127.0.0.1:9222"
    assert "http://localhost:9222" in candidates
    assert "ws://127.0.0.1:9222" not in candidates


@pytest.mark.asyncio
async def test_safe_connect_retries_before_succeeding():
    page = _FakePage()
    context = _FakeContext(page)
    browser = _FakeBrowser(context)
    connect = AsyncMock(side_effect=[RuntimeError("cdp not ready"), browser])
    playwright = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=connect))

    handle = BrowserHandle(browser_id="browser-1", ws_url="ws://127.0.0.1/devtools/browser/1")

    with (
        patch.object(PlaywrightManager, "acquire", AsyncMock(return_value=playwright)),
        patch.object(PlaywrightManager, "release", AsyncMock()),
        patch("src.core.rem.handle.asyncio.sleep", AsyncMock()),
    ):
        success = await handle.safe_connect()

    assert success is True
    assert connect.await_count == 2
    assert handle.browser is browser
    assert handle.context is context
    assert handle.page is page


@pytest.mark.asyncio
async def test_safe_connect_uses_short_cdp_timeout():
    page = _FakePage()
    context = _FakeContext(page)
    browser = _FakeBrowser(context)
    connect = AsyncMock(return_value=browser)
    playwright = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=connect))

    handle = BrowserHandle(browser_id="browser-1", ws_url="ws://127.0.0.1/devtools/browser/1")

    with (
        patch.object(PlaywrightManager, "acquire", AsyncMock(return_value=playwright)),
        patch.object(PlaywrightManager, "release", AsyncMock()),
        patch("src.core.rem.handle.asyncio.sleep", AsyncMock()),
    ):
        success = await handle.safe_connect()

    assert success is True
    assert CDP_CONNECT_TIMEOUT_MS == 15_000
    assert connect.await_args.kwargs["timeout"] == CDP_CONNECT_TIMEOUT_MS


@pytest.mark.asyncio
async def test_safe_connect_waits_for_late_cdp_ready_after_probe():
    page = _FakePage()
    context = _FakeContext(page)
    browser = _FakeBrowser(context)
    connect = AsyncMock(
        side_effect=[
            RuntimeError("cdp not ready 1"),
            RuntimeError("cdp not ready 2"),
            RuntimeError("cdp not ready 3"),
            RuntimeError("cdp not ready 4"),
            browser,
        ]
    )
    playwright = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=connect))

    handle = BrowserHandle(browser_id="browser-3", ws_url="http://127.0.0.1:63333/json/version/")

    with (
        patch.object(
            BrowserHandle,
            "_probe_websocket_debugger_url",
            AsyncMock(return_value="ws://localhost:63333/devtools/browser/abc"),
        ),
        patch.object(PlaywrightManager, "acquire", AsyncMock(return_value=playwright)),
        patch.object(PlaywrightManager, "release", AsyncMock()),
        patch("src.core.rem.handle.asyncio.sleep", AsyncMock()),
    ):
        success = await handle.safe_connect()

    assert success is True
    assert connect.await_count == 5
    assert connect.await_args_list[0].args[0] == "ws://localhost:63333/devtools/browser/abc"
    assert handle.browser is browser


@pytest.mark.asyncio
async def test_safe_connect_probes_localhost_variant_before_connecting():
    page = _FakePage()
    context = _FakeContext(page)
    browser = _FakeBrowser(context)
    connect = AsyncMock(return_value=browser)
    playwright = SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=connect))
    probe = AsyncMock(
        side_effect=[
            None,
            "ws://localhost:63285/devtools/browser/abc",
        ]
    )

    handle = BrowserHandle(browser_id="browser-2", ws_url="http://127.0.0.1:63285")

    with (
        patch.object(BrowserHandle, "_probe_websocket_debugger_url", probe),
        patch.object(PlaywrightManager, "acquire", AsyncMock(return_value=playwright)),
        patch.object(PlaywrightManager, "release", AsyncMock()),
        patch("src.core.rem.handle.asyncio.sleep", AsyncMock()),
    ):
        success = await handle.safe_connect()

    assert success is True
    assert probe.await_args_list[0].args[0] == "http://127.0.0.1:63285"
    assert probe.await_args_list[1].args[0] == "http://localhost:63285"
    assert connect.await_args_list[0].args[0] == "ws://localhost:63285/devtools/browser/abc"


def test_candidate_cdp_endpoints_include_localhost_variants():
    candidates = BrowserHandle._candidate_cdp_endpoints("http://127.0.0.1:63285/json/version/")

    assert candidates == [
        "http://127.0.0.1:63285",
        "http://localhost:63285",
    ]

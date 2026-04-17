from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.core.rem.provider import PlaywrightProvider


class _FakePage:
    def __init__(self) -> None:
        self.goto = AsyncMock()
        self._closed = False

    def is_closed(self) -> bool:
        return self._closed

    async def title(self) -> str:
        return "playwright-local"


class _FakeContext:
    def __init__(self, pages=None) -> None:
        self.pages = list(pages or [])
        self.clear_cookies = AsyncMock()

    async def new_page(self):
        page = _FakePage()
        self.pages.append(page)
        return page


class _FakeBrowser:
    def __init__(self, contexts=None) -> None:
        self.contexts = list(contexts or [])
        self.close = AsyncMock()

    def is_connected(self) -> bool:
        return True

    async def new_context(self):
        context = _FakeContext()
        self.contexts.append(context)
        return context


@pytest.mark.asyncio
async def test_playwright_provider_open_and_connect_create_page():
    provider = PlaywrightProvider()
    env = await provider.create({"env_name": "local-env"})
    browser = _FakeBrowser()
    launch = AsyncMock(return_value=browser)
    playwright = SimpleNamespace(chromium=SimpleNamespace(launch=launch))

    with (
        patch("src.core.rem.handle.PlaywrightManager.acquire", AsyncMock(return_value=playwright)),
        patch("src.core.rem.handle.PlaywrightManager.release", AsyncMock()),
    ):
        assert await provider.open(env) is True
        assert await provider.connect(env) is True

    launch.assert_awaited_once_with(headless=False)
    assert env.handle is not None
    assert env.handle.browser is browser
    assert env.handle.context is not None
    assert env.handle.page is not None


@pytest.mark.asyncio
async def test_playwright_provider_close_releases_browser_and_resets_handle():
    provider = PlaywrightProvider()
    env = await provider.create({"env_name": "local-env"})
    browser = _FakeBrowser([_FakeContext([_FakePage()])])
    assert env.handle is not None
    env.handle._browser = browser
    env.handle._context = browser.contexts[0]
    env.handle._page = browser.contexts[0].pages[0]
    env.handle._has_playwright_ref = True

    with patch("src.core.rem.handle.PlaywrightManager.release", AsyncMock()) as release:
        assert await provider.close(env) is True

    browser.close.assert_awaited_once()
    release.assert_awaited_once()
    assert env.handle is not None
    assert env.handle.browser is None
    assert env.handle.page is None
    assert env.handle.browser_id == "local-env"


@pytest.mark.asyncio
async def test_playwright_provider_reset_and_health_check_use_connected_page():
    provider = PlaywrightProvider()
    env = await provider.create({"env_name": "local-env"})
    page = _FakePage()
    context = _FakeContext([page])
    browser = _FakeBrowser([context])
    assert env.handle is not None
    env.handle._browser = browser
    env.handle._context = context
    env.handle._page = page

    assert await provider.health_check(env) is True
    assert await provider.reset(env) is True

    context.clear_cookies.assert_awaited_once()
    page.goto.assert_awaited_once_with("about:blank", wait_until="domcontentloaded")

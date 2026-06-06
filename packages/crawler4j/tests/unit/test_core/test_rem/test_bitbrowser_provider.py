import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.rem.handle import BrowserHandle
from src.core.rem.models import Environment, EnvKind, EnvStatus
from src.core.rem.provider import BitBrowserProvider


@pytest.mark.asyncio
async def test_bitbrowser_provider_reads_creation_params_fallback(monkeypatch):
    provider = BitBrowserProvider()
    captured: dict[str, object] = {}

    async def create_browser(name, proxy, group_id, fingerprint):
        captured.update(
            {
                "name": name,
                "proxy": proxy,
                "group_id": group_id,
                "fingerprint": fingerprint,
            }
        )
        return 77

    monkeypatch.setattr(
        provider,
        "_get_api_client",
        lambda: SimpleNamespace(create_browser=create_browser),
    )

    env = await provider.create(
        {
            "env_name": "bit-env",
            "creation_params": {
                "group_id": "group-1",
                "fingerprint": {"randomize_all": True},
            },
        }
    )

    assert captured["name"] == "bit-env"
    assert captured["group_id"] == "group-1"
    assert captured["fingerprint"] == {"randomize_all": True}
    assert env.external_id == "77"


@pytest.mark.asyncio
async def test_bitbrowser_close_serializes_close_browser_operations(monkeypatch):
    provider = BitBrowserProvider()
    env_a = Environment(
        id=101,
        name="bit-env-a",
        kind=EnvKind.BROWSER,
        provider="bitbrowser",
        status=EnvStatus.BUSY,
        handle=BrowserHandle(browser_id="101"),
    )
    env_b = Environment(
        id=102,
        name="bit-env-b",
        kind=EnvKind.BROWSER,
        provider="bitbrowser",
        status=EnvStatus.BUSY,
        handle=BrowserHandle(browser_id="102"),
    )
    assert env_a.handle is not None
    assert env_b.handle is not None
    monkeypatch.setattr(env_a.handle, "safe_close", AsyncMock())
    monkeypatch.setattr(env_b.handle, "safe_close", AsyncMock())

    active_closes = 0
    max_active_closes = 0
    close_order: list[str] = []

    async def close_browser(browser_id: str) -> None:
        nonlocal active_closes, max_active_closes
        active_closes += 1
        max_active_closes = max(max_active_closes, active_closes)
        close_order.append(browser_id)
        await asyncio.sleep(0)
        active_closes -= 1

    client = SimpleNamespace(
        get_browser_pids=AsyncMock(return_value={"101": 1, "102": 2}),
        close_browser=AsyncMock(side_effect=close_browser),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await asyncio.gather(provider.close(env_a), provider.close(env_b)) == [True, True]
    assert max_active_closes == 1
    assert close_order == ["101", "102"]


@pytest.mark.asyncio
async def test_bitbrowser_destroy_serializes_delete_operations(monkeypatch):
    provider = BitBrowserProvider()
    env_a = Environment(
        id=101,
        name="bit-env-a",
        kind=EnvKind.BROWSER,
        provider="bitbrowser",
        status=EnvStatus.READY,
        handle=BrowserHandle(browser_id="101"),
    )
    env_b = Environment(
        id=102,
        name="bit-env-b",
        kind=EnvKind.BROWSER,
        provider="bitbrowser",
        status=EnvStatus.READY,
        handle=BrowserHandle(browser_id="102"),
    )
    assert env_a.handle is not None
    assert env_b.handle is not None
    monkeypatch.setattr(env_a.handle, "safe_close", AsyncMock())
    monkeypatch.setattr(env_b.handle, "safe_close", AsyncMock())

    existing_ids = {"101", "102"}
    active_deletes = 0
    max_active_deletes = 0

    async def get_browser_detail(browser_id: str) -> dict | None:
        return {"id": browser_id} if browser_id in existing_ids else None

    async def delete_browser(browser_id: str) -> bool:
        nonlocal active_deletes, max_active_deletes
        active_deletes += 1
        max_active_deletes = max(max_active_deletes, active_deletes)
        await asyncio.sleep(0)
        existing_ids.discard(browser_id)
        active_deletes -= 1
        return True

    client = SimpleNamespace(
        get_browser_detail=AsyncMock(side_effect=get_browser_detail),
        delete_browser=AsyncMock(side_effect=delete_browser),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await asyncio.gather(provider.destroy(env_a), provider.destroy(env_b)) == [True, True]
    assert max_active_deletes == 1
    assert sorted(existing_ids) == []


@pytest.mark.asyncio
async def test_bitbrowser_reset_serializes_cache_clear_operations(monkeypatch):
    provider = BitBrowserProvider()
    env_a = Environment(
        id=101,
        name="bit-env-a",
        kind=EnvKind.BROWSER,
        provider="bitbrowser",
        status=EnvStatus.READY,
        handle=BrowserHandle(browser_id="101"),
    )
    env_b = Environment(
        id=102,
        name="bit-env-b",
        kind=EnvKind.BROWSER,
        provider="bitbrowser",
        status=EnvStatus.READY,
        handle=BrowserHandle(browser_id="102"),
    )
    active_clears = 0
    max_active_clears = 0
    clear_order: list[list[str]] = []

    async def clear_cache_except_extensions(browser_ids: list[str]) -> bool:
        nonlocal active_clears, max_active_clears
        active_clears += 1
        max_active_clears = max(max_active_clears, active_clears)
        clear_order.append(list(browser_ids))
        await asyncio.sleep(0)
        active_clears -= 1
        return True

    client = SimpleNamespace(
        get_browser_pids=AsyncMock(return_value={}),
        clear_cache_except_extensions=AsyncMock(side_effect=clear_cache_except_extensions),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await asyncio.gather(provider.reset(env_a), provider.reset(env_b)) == [True, True]
    assert max_active_clears == 1
    assert clear_order == [["101"], ["102"]]

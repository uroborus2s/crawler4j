from unittest.mock import AsyncMock

import pytest

from src.core.system.external_app_service import AppLaunchResult, ExternalApp, ExternalAppService


@pytest.mark.asyncio
async def test_wait_until_ready_uses_virtualbrowser_management_api(monkeypatch):
    service = ExternalAppService()
    ready = AsyncMock(side_effect=[False, True])

    monkeypatch.setattr(service, "_get_app_port", lambda app: 9000)
    monkeypatch.setattr(service, "_check_app_api_ready", ready)

    result = await service.wait_until_ready(ExternalApp.VIRTUALBROWSER, timeout=3)

    assert result is True
    assert ready.await_args_list[0].args == (ExternalApp.VIRTUALBROWSER, 9000)
    assert ready.await_args_list[1].args == (ExternalApp.VIRTUALBROWSER, 9000)


@pytest.mark.asyncio
async def test_check_app_api_ready_uses_browser_list_for_virtualbrowser(monkeypatch):
    service = ExternalAppService()
    virtualbrowser_ready = AsyncMock(return_value=True)
    port_ready = AsyncMock(return_value=True)

    monkeypatch.setattr(service, "_check_virtualbrowser_api_ready", virtualbrowser_ready)
    monkeypatch.setattr(service, "_check_port_available", port_ready)

    assert await service._check_app_api_ready(ExternalApp.VIRTUALBROWSER, 9000) is True

    virtualbrowser_ready.assert_awaited_once_with(9000)
    port_ready.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_running_waits_until_preexisting_app_is_ready(monkeypatch):
    service = ExternalAppService()
    is_running = AsyncMock(return_value=True)
    wait_until_ready = AsyncMock(return_value=True)
    launch = AsyncMock()

    monkeypatch.setattr(service, "is_running", is_running)
    monkeypatch.setattr(service, "wait_until_ready", wait_until_ready)
    monkeypatch.setattr(service, "launch", launch)

    result = await service.ensure_running(ExternalApp.VIRTUALBROWSER, timeout=5)

    assert result == AppLaunchResult(success=True)
    is_running.assert_awaited_once_with(ExternalApp.VIRTUALBROWSER)
    wait_until_ready.assert_awaited_once_with(ExternalApp.VIRTUALBROWSER, timeout=5)
    launch.assert_not_awaited()

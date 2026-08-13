from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

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
async def test_check_app_api_ready_uses_hubstudio_management_api(monkeypatch):
    service = ExternalAppService()
    hubstudio_ready = AsyncMock(return_value=True)
    port_ready = AsyncMock(return_value=True)

    monkeypatch.setattr(service, "_check_hubstudio_api_ready", hubstudio_ready)
    monkeypatch.setattr(service, "_check_port_available", port_ready)

    assert await service._check_app_api_ready(ExternalApp.HUBSTUDIO, 6873) is True
    hubstudio_ready.assert_awaited_once_with(6873)
    port_ready.assert_not_awaited()


def test_hubstudio_external_app_defaults_are_registered():
    from src.core.system.external_app_service import APP_CONFIG

    config = APP_CONFIG[ExternalApp.HUBSTUDIO]
    assert config["default_port"] == 6873
    assert config["display_name"] == "HubStudio"
    assert config["default_paths"]["Darwin"] == "/Applications/Hubstudio.app"


@pytest.mark.asyncio
async def test_hubstudio_ready_check_posts_json_with_optional_authorization(monkeypatch):
    import httpx

    service = ExternalAppService()
    response = SimpleNamespace(is_success=True, json=lambda: {"code": 0})
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.post = AsyncMock(return_value=response)
    factory = MagicMock(return_value=client)
    monkeypatch.setattr(httpx, "AsyncClient", factory)
    monkeypatch.setattr(
        "src.core.system.config_center.get_config_center",
        lambda: SimpleNamespace(get=lambda key: "api-key" if key.endswith("apikey") else None),
    )

    assert await service._check_hubstudio_api_ready(6873) is True
    assert factory.call_args.kwargs == {
        "timeout": 2.0,
        "headers": {"Content-Type": "application/json", "Authorization": "api-key"},
        "trust_env": False,
    }
    client.post.assert_awaited_once_with("http://127.0.0.1:6873/api/v1/env/list", json={})


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

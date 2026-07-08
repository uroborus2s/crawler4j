"""Provider 注册测试。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

import src.core.rem.provider as provider_module
from src.core.rem.handle import BrowserHandle
from src.core.rem.models import Environment, EnvKind, EnvStatus, ProviderEnvInfo, ProxyConfig, ProxyMode
from src.core.rem.provider import (
    VirtualBrowserProvider,
    get_provider,
    list_providers,
)


class TestProviderRegistry:
    """测试 Provider 自动注册。"""

    def test_providers_registered(self):
        """测试所有内置 Provider 自动注册。"""
        registered = list_providers()

        assert "playwright_local" in registered
        assert "bitbrowser" in registered
        assert "virtualbrowser" in registered

    def test_get_playwright_provider(self):
        """测试获取 Playwright Provider。"""
        provider = get_provider("playwright_local")

        assert provider is not None
        assert provider.name == "playwright_local"

    def test_get_bitbrowser_provider(self):
        """测试获取 BitBrowser Provider。"""
        provider = get_provider("bitbrowser")

        assert provider is not None
        assert provider.name == "bitbrowser"

    def test_get_virtualbrowser_provider(self):
        """测试获取 VirtualBrowser Provider。"""
        provider = get_provider("virtualbrowser")

        assert provider is not None
        assert provider.name == "virtualbrowser"

    def test_get_unknown_provider(self):
        """测试获取未注册的 Provider。"""
        provider = get_provider("unknown_provider")

        assert provider is None


def test_created_parameter_warnings_flag_inconsistent_fingerprint_values():
    warnings = provider_module._created_parameter_warnings(
        {
            "id": 55,
            "ua": {
                "mode": 0,
                "value": "Mozilla/5.0 (Windows NT 10.0; WOW64) Chrome/143.0.0.0",
            },
            "location": {"mode": 2, "enable": 1, "longitude": "0", "latitude": "0"},
            "cpu": {"mode": 1, "value": 2},
            "memory": {"mode": 1, "value": 64},
            "proxy": {
                "host": "27.18.13.203",
                "url": "socks5://user:pass@27.18.13.103:2019",
            },
            "fonts": {"mode": 1},
            "canvas": {"mode": 1},
            "webgl-img": {"mode": 1},
            "audio-context": {"mode": 1},
            "client-rects": {"mode": 1},
            "speech_voices": {"mode": 1},
        },
        browser_id=55,
        geo=None,
    )

    rendered = "\n".join(warnings)
    assert "WOW64" in rendered
    assert "location 为 0,0" in rendered
    assert "cpu/memory=2/64" in rendered
    assert "proxy.host='27.18.13.203'" in rendered
    assert "fonts.mode=1" in rendered
    assert "speech_voices.mode=1" in rendered
    assert "canvas.mode=1" in rendered
    assert "webgl-img.mode=1" in rendered
    assert "audio-context.mode=1" in rendered
    assert "client-rects.mode=1" in rendered


def test_created_parameter_warnings_allow_local_forward_proxy_url():
    warnings = provider_module._created_parameter_warnings(
        {
            "id": 9,
            "cpu": {"mode": 1, "value": 8},
            "memory": {"mode": 1, "value": 16},
            "proxy": {"host": "116.140.217.185", "url": "http://127.0.0.1:48065"},
        },
        browser_id=9,
        geo=None,
    )

    assert all("proxy.host" not in warning for warning in warnings)


@pytest.mark.asyncio
async def test_virtualbrowser_create_uses_proxy_geo_and_validates_full_parameters(monkeypatch):
    provider = VirtualBrowserProvider()
    client = SimpleNamespace(
        add_browser=AsyncMock(return_value=303),
        get_browser_full_parameters=AsyncMock(
            return_value={
                "id": 303,
                "name": "env-geo",
                "time-zone": {"utc": "Asia/Tokyo"},
                "ua-language": {"language": "ja-JP"},
                "webrtc": {"mode": 0},
            }
        ),
    )
    probe_entries = []

    def _probe_geo(entry):
        probe_entries.append(entry)
        return provider_module.ProxyProbeResult(
            ok=True,
            stage="probe",
            protocol="http",
            masked_proxy_url="http://alice:***@10.0.0.8:8080",
            latency_ms=12,
            exit_ip="203.0.113.8",
            http_status=200,
            detail="ok",
            error_type=None,
            country_code="JP",
            country="Japan",
            region="Tokyo",
            city="Tokyo",
            timezone="Asia/Tokyo",
            asn="AS64500 TEST-NET",
            isp="Example ISP",
            latitude=35.6895,
            longitude=139.6917,
        )

    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    monkeypatch.setattr(provider_module, "probe_ip_entry_geo", _probe_geo)

    env = await provider.create(
        {
            "env_name": "env-geo",
            "creation_params": {
                "virtualbrowser": {
                    "chrome_version": 145,
                    "__randomize_fingerprint__": True,
                },
                "proxy": {
                    "protocol": "http",
                    "host": "10.0.0.8",
                    "port": 8080,
                    "user": "alice",
                    "pass": "secret",
                },
            },
        }
    )

    assert env.external_id == "303"
    assert probe_entries[0].address == "10.0.0.8"
    assert probe_entries[0].port == 8080
    assert probe_entries[0].username == "alice"
    client.add_browser.assert_awaited_once()
    _, kwargs = client.add_browser.await_args
    assert kwargs["geo"]["country_code"] == "JP"
    assert kwargs["geo"]["timezone"] == "Asia/Tokyo"
    assert kwargs["geo"]["latitude"] == 35.6895
    assert kwargs["geo"]["longitude"] == 139.6917
    client.get_browser_full_parameters.assert_awaited_once_with(303)


@pytest.mark.asyncio
async def test_virtualbrowser_repair_fingerprint_location_updates_only_location(monkeypatch):
    provider = VirtualBrowserProvider()
    env = Environment(
        id=101,
        name="vb-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        external_id="303",
        proxy_config=ProxyConfig(
            mode=ProxyMode.STATIC,
            static_value="http://alice:secret@10.0.0.8:8080",
            current_ip="10.0.0.8",
        ),
        handle=BrowserHandle(browser_id="303"),
    )
    client = SimpleNamespace(update_browser=AsyncMock(return_value=True))

    def _probe_geo(entry):
        assert entry.address == "10.0.0.8"
        assert entry.port == 8080
        assert entry.username == "alice"
        return provider_module.ProxyProbeResult(
            ok=True,
            stage="probe",
            protocol="http",
            masked_proxy_url="http://alice:***@10.0.0.8:8080",
            latency_ms=12,
            exit_ip="203.0.113.8",
            http_status=200,
            detail="ok",
            error_type=None,
            country_code="CN",
            country="China",
            region="Beijing",
            city="Jinrongjie",
            timezone="Asia/Shanghai",
            asn="AS4837 CHINA UNICOM China169 Backbone",
            isp="China Unicom",
            latitude=39.9072,
            longitude=116.357,
        )

    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    monkeypatch.setattr(provider_module, "probe_ip_entry_geo", _probe_geo)

    location = await provider.repair_fingerprint_location(env)

    assert location["longitude"] == "116.357"
    assert location["latitude"] == "39.9072"
    assert 1600 <= location["precision"] <= 5600
    client.update_browser.assert_awaited_once_with(303, {"location": location})


@pytest.mark.asyncio
async def test_virtualbrowser_open_surfaces_launch_error(monkeypatch):
    provider = VirtualBrowserProvider()
    env = Environment(
        id=101,
        name="vb-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        handle=BrowserHandle(browser_id="101"),
    )
    client = SimpleNamespace(
        launch_browser=AsyncMock(side_effect=RuntimeError("Launch Error: DevTools port not detected"))
    )

    monkeypatch.setattr(provider, "is_window_open", AsyncMock(return_value=False))
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    with pytest.raises(
        RuntimeError,
        match="VirtualBrowser launchBrowser 失败: Launch Error: DevTools port not detected",
    ):
        await provider.open(env)


@pytest.mark.asyncio
async def test_virtualbrowser_open_serializes_launch_operations(monkeypatch):
    provider = VirtualBrowserProvider()
    env_a = Environment(
        id=101,
        name="vb-env-a",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        handle=BrowserHandle(browser_id="101"),
    )
    env_b = Environment(
        id=102,
        name="vb-env-b",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        handle=BrowserHandle(browser_id="102"),
    )
    active_launches = 0
    max_active_launches = 0
    launch_order: list[int] = []

    async def launch_browser(browser_id: int) -> str:
        nonlocal active_launches, max_active_launches
        active_launches += 1
        max_active_launches = max(max_active_launches, active_launches)
        launch_order.append(browser_id)
        await asyncio.sleep(0)
        active_launches -= 1
        return f"http://localhost:{browser_id}"

    client = SimpleNamespace(launch_browser=AsyncMock(side_effect=launch_browser))

    monkeypatch.setattr(provider, "is_window_open", AsyncMock(return_value=False))
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await asyncio.gather(provider.open(env_a), provider.open(env_b)) == [True, True]
    assert max_active_launches == 1
    assert launch_order == [101, 102]
    assert env_a.handle is not None
    assert env_b.handle is not None
    assert env_a.handle.ws_url == "http://localhost:101"
    assert env_b.handle.ws_url == "http://localhost:102"


@pytest.mark.asyncio
async def test_virtualbrowser_connect_recovers_missing_ws_url_from_browser_detail(monkeypatch):
    provider = VirtualBrowserProvider()
    env = Environment(
        id=101,
        name="vb-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.BUSY,
        handle=BrowserHandle(browser_id="101"),
    )
    handle = env.handle
    assert handle is not None

    client = SimpleNamespace(
        get_browser_runtime_detail=AsyncMock(return_value={"debuggingPort": 56764}),
    )

    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    monkeypatch.setattr(handle, "safe_connect", AsyncMock(return_value=True))

    success = await provider.connect(env)

    assert success is True
    assert handle.ws_url == "http://localhost:56764"
    handle.safe_connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_virtualbrowser_connect_retries_runtime_detail_before_missing_ws_url(monkeypatch):
    provider = VirtualBrowserProvider()
    env = Environment(
        id=102,
        name="vb-env-retry",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.BUSY,
        handle=BrowserHandle(browser_id="102"),
    )
    handle = env.handle
    assert handle is not None

    client = SimpleNamespace(
        get_browser_runtime_detail=AsyncMock(
            side_effect=[
                None,
                None,
                {"id": 102, "debuggingPort": 57204},
            ]
        )
    )

    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    monkeypatch.setattr(handle, "safe_connect", AsyncMock(return_value=True))

    with patch("src.core.rem.provider.asyncio.sleep", AsyncMock()):
        success = await provider.connect(env)

    assert success is True
    assert handle.ws_url == "http://localhost:57204"
    assert client.get_browser_runtime_detail.await_count == 3
    handle.safe_connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_virtualbrowser_destroy_waits_for_async_external_delete(monkeypatch):
    provider = VirtualBrowserProvider()
    env = Environment(
        id=101,
        name="vb-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        handle=BrowserHandle(browser_id="101"),
    )
    assert env.handle is not None

    client = SimpleNamespace(
        get_browser_detail=AsyncMock(side_effect=[{"id": 101}, {"id": 101}, None]),
        is_browser_running=AsyncMock(side_effect=[True, True, False]),
        stop_browser=AsyncMock(),
        delete_browser=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    monkeypatch.setattr(env.handle, "safe_close", AsyncMock())
    monkeypatch.setattr("src.core.rem.provider.asyncio.sleep", AsyncMock())

    success = await provider.destroy(env)

    assert success is True
    env.handle.safe_close.assert_awaited_once()
    client.stop_browser.assert_awaited_once_with(101)
    client.delete_browser.assert_awaited_once_with(101)
    assert client.is_browser_running.await_count == 3
    assert client.get_browser_detail.await_count == 3


@pytest.mark.asyncio
async def test_virtualbrowser_close_serializes_stop_operations(monkeypatch):
    provider = VirtualBrowserProvider()
    env_a = Environment(
        id=101,
        name="vb-env-a",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.BUSY,
        handle=BrowserHandle(browser_id="101"),
    )
    env_b = Environment(
        id=102,
        name="vb-env-b",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.BUSY,
        handle=BrowserHandle(browser_id="102"),
    )
    assert env_a.handle is not None
    assert env_b.handle is not None
    monkeypatch.setattr(env_a.handle, "safe_close", AsyncMock())
    monkeypatch.setattr(env_b.handle, "safe_close", AsyncMock())

    active_stops = 0
    max_active_stops = 0
    stop_order: list[int] = []

    async def stop_browser(browser_id: int) -> None:
        nonlocal active_stops, max_active_stops
        active_stops += 1
        max_active_stops = max(max_active_stops, active_stops)
        stop_order.append(browser_id)
        await asyncio.sleep(0)
        active_stops -= 1

    client = SimpleNamespace(stop_browser=AsyncMock(side_effect=stop_browser))
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await asyncio.gather(provider.close(env_a), provider.close(env_b)) == [True, True]
    assert max_active_stops == 1
    assert stop_order == [101, 102]


@pytest.mark.asyncio
async def test_virtualbrowser_destroy_serializes_delete_operations(monkeypatch):
    provider = VirtualBrowserProvider()
    env_a = Environment(
        id=101,
        name="vb-env-a",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        handle=BrowserHandle(browser_id="101"),
    )
    env_b = Environment(
        id=102,
        name="vb-env-b",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        handle=BrowserHandle(browser_id="102"),
    )
    assert env_a.handle is not None
    assert env_b.handle is not None
    monkeypatch.setattr(env_a.handle, "safe_close", AsyncMock())
    monkeypatch.setattr(env_b.handle, "safe_close", AsyncMock())

    existing_ids = {101, 102}
    active_deletes = 0
    max_active_deletes = 0

    async def get_browser_detail(browser_id: int) -> dict | None:
        return {"id": browser_id} if browser_id in existing_ids else None

    async def delete_browser(browser_id: int) -> bool:
        nonlocal active_deletes, max_active_deletes
        active_deletes += 1
        max_active_deletes = max(max_active_deletes, active_deletes)
        await asyncio.sleep(0)
        existing_ids.discard(browser_id)
        active_deletes -= 1
        return True

    client = SimpleNamespace(
        get_browser_detail=AsyncMock(side_effect=get_browser_detail),
        is_browser_running=AsyncMock(return_value=False),
        stop_browser=AsyncMock(),
        delete_browser=AsyncMock(side_effect=delete_browser),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await asyncio.gather(provider.destroy(env_a), provider.destroy(env_b)) == [True, True]
    assert max_active_deletes == 1
    assert sorted(existing_ids) == []


@pytest.mark.asyncio
async def test_virtualbrowser_destroy_uses_external_id_when_handle_missing(monkeypatch):
    provider = VirtualBrowserProvider()
    env = Environment(
        id=101,
        name="vb-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        external_id="101",
        handle=None,
    )
    existing_ids = {101}

    async def get_browser_detail(browser_id: int) -> dict | None:
        return {"id": browser_id} if browser_id in existing_ids else None

    async def delete_browser(browser_id: int) -> bool:
        existing_ids.discard(browser_id)
        return True

    client = SimpleNamespace(
        get_browser_detail=AsyncMock(side_effect=get_browser_detail),
        is_browser_running=AsyncMock(return_value=False),
        stop_browser=AsyncMock(),
        delete_browser=AsyncMock(side_effect=delete_browser),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await provider.destroy(env) is True
    assert env.handle is not None
    assert env.handle.browser_id == "101"
    client.delete_browser.assert_awaited_once_with(101)
    assert sorted(existing_ids) == []


@pytest.mark.asyncio
async def test_virtualbrowser_list_existing_envs_preserves_source_proxy_config(monkeypatch):
    provider = VirtualBrowserProvider()
    client = SimpleNamespace(
        list_browsers=AsyncMock(
            return_value=[
                {
                    "id": 101,
                    "name": "vb-imported",
                    "proxy": {
                        "mode": 2,
                        "protocol": "SOCKS5",
                        "host": "10.0.0.8",
                        "port": "1080",
                        "user": "alice",
                        "pass": "secret",
                    },
                }
            ]
        ),
        get_browser_full_parameters=AsyncMock(return_value=[]),
        list_running_browsers=AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    items = await provider.list_existing_envs()

    assert len(items) == 1
    assert items[0].proxy_summary == "socks5 10.0.0.8:1080"
    assert items[0].proxy_config is not None
    assert items[0].proxy_config.static_value == "socks5://alice:secret@10.0.0.8:1080"
    assert items[0].proxy_config.current_ip == "10.0.0.8"


@pytest.mark.asyncio
async def test_virtualbrowser_source_proxy_prefers_structured_host_over_local_forward_url(monkeypatch):
    provider = VirtualBrowserProvider()
    client = SimpleNamespace(
        list_browsers=AsyncMock(
            return_value=[
                {
                    "id": 102,
                    "name": "vb-local-forward",
                    "proxy": {
                        "protocol": "HTTP",
                        "host": "124.225.43.95",
                        "port": "6789",
                        "url": "http://127.0.0.1:23080",
                    },
                }
            ]
        ),
        get_browser_full_parameters=AsyncMock(return_value=[]),
        list_running_browsers=AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    items = await provider.list_existing_envs()

    assert len(items) == 1
    assert items[0].proxy_summary == "http 124.225.43.95:6789"
    assert items[0].proxy_config is not None
    assert items[0].proxy_config.static_value == "http://124.225.43.95:6789"
    assert items[0].proxy_config.current_ip == "124.225.43.95"


@pytest.mark.asyncio
async def test_virtualbrowser_build_imported_environment_keeps_source_proxy_config():
    provider = VirtualBrowserProvider()
    source_proxy = ProxyConfig(
        mode=ProxyMode.STATIC,
        static_value="socks5://alice:secret@10.0.0.8:1080",
        current_ip="10.0.0.8",
    )

    env = await provider.build_imported_environment(
        ProviderEnvInfo(
            provider="virtualbrowser",
            provider_label="Virtual Browser",
            external_id="101",
            name="vb-imported",
            proxy_config=source_proxy,
        )
    )

    assert env.proxy_config is source_proxy


@pytest.mark.asyncio
async def test_virtualbrowser_reset_serializes_data_delete_operations(monkeypatch):
    provider = VirtualBrowserProvider()
    env_a = Environment(
        id=101,
        name="vb-env-a",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        handle=BrowserHandle(browser_id="101"),
    )
    env_b = Environment(
        id=102,
        name="vb-env-b",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        handle=BrowserHandle(browser_id="102"),
    )
    active_deletes = 0
    max_active_deletes = 0
    delete_order: list[int] = []

    async def delete_browser_data(browser_id: int) -> bool:
        nonlocal active_deletes, max_active_deletes
        active_deletes += 1
        max_active_deletes = max(max_active_deletes, active_deletes)
        delete_order.append(browser_id)
        await asyncio.sleep(0)
        active_deletes -= 1
        return True

    client = SimpleNamespace(delete_browser_data=AsyncMock(side_effect=delete_browser_data))
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await asyncio.gather(provider.reset(env_a), provider.reset(env_b)) == [True, True]
    assert max_active_deletes == 1
    assert delete_order == [101, 102]

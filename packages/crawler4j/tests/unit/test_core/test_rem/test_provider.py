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
    BitBrowserProvider,
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


def test_created_parameter_warnings_flag_inconsistent_fingerprint_values(monkeypatch):
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.platform.system",
        lambda: "Windows",
    )
    warnings = provider_module._created_parameter_warnings(
        {
            "id": 55,
            "ua": {
                "mode": 0,
                "value": "Mozilla/5.0 (Windows NT 10.0; WOW64) Chrome/143.0.0.0",
            },
            "chrome_version": 143,
            "ua-full-version": {"mode": 1, "value": "143.0.0.0"},
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
    assert "ua-full-version" in rendered
    assert "location 为 0,0" in rendered
    assert "cpu/memory=2/64" in rendered
    assert "proxy.host='27.18.13.203'" in rendered
    assert "fonts.mode=1" in rendered
    assert "speech_voices.mode=1" in rendered
    assert "canvas.mode=1" in rendered
    assert "webgl-img.mode=1" in rendered
    assert "audio-context.mode=1" in rendered
    assert "client-rects.mode=1" in rendered


def test_created_parameter_warnings_require_automatic_controlled_fields():
    warnings = provider_module._created_parameter_warnings(
        {"id": 55},
        browser_id=55,
        geo=None,
        require_controlled=True,
    )

    assert warnings == [
        "ua.value 缺失",
        "ua-full-version.value 缺失",
        "cpu/memory 缺失",
        "screen 尺寸缺失",
    ]


def test_created_parameter_warnings_require_custom_screen_mode():
    warnings = provider_module._created_parameter_warnings(
        {
            "id": 55,
            "chrome_version": 145,
            "ua": {"mode": 0, "value": "Mozilla/5.0 Chrome/145.0.0.0"},
            "ua-full-version": {"mode": 1, "value": "145.0.7632.109"},
            "cpu": {"mode": 1, "value": 8},
            "memory": {"mode": 1, "value": 16},
            "screen": {"mode": 0, "width": 1920, "height": 1080},
        },
        browser_id=55,
        geo=None,
        require_controlled=True,
    )

    assert warnings == ["screen.mode=0，预期自定义模式 1"]


def test_virtualbrowser_manual_ip_table_geo_allows_fixed_defaults_without_location():
    assert VirtualBrowserProvider._manual_ip_table_geo(
        {
            "country": "CN",
            "timezone": "Asia/Shanghai",
            "language": "zh-CN,zh,en-US,en",
        }
    ) == {
        "country": "CN",
        "timezone": "Asia/Shanghai",
        "language": "zh-CN,zh,en-US,en",
        "latitude": None,
        "longitude": None,
    }


def test_created_parameter_warnings_rejects_local_forward_proxy_url():
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

    assert any("proxy.host" in warning for warning in warnings)


@pytest.mark.asyncio
async def test_bitbrowser_update_translates_proxy_config(monkeypatch):
    provider = BitBrowserProvider()
    client = SimpleNamespace(update_browser=AsyncMock(return_value=True))
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    env = Environment(
        name="env",
        kind=EnvKind.BROWSER,
        provider=provider.name,
        status=EnvStatus.READY,
        external_id="bb-1",
        handle=BrowserHandle(browser_id="bb-1"),
    )
    proxy = ProxyConfig(
        mode=ProxyMode.POOL,
        static_value="socks5://user:pass@10.0.0.8:1080",
        current_ip="10.0.0.8",
        ip_entry_id="ip-1",
    )

    assert await provider.update(env, {"proxy": proxy.to_dict()}) is True

    client.update_browser.assert_awaited_once()
    assert client.update_browser.await_args.args[0] == "bb-1"
    assert client.update_browser.await_args.args[1] == {
        "proxyMethod": 2,
        "proxyType": "socks5",
        "host": "10.0.0.8",
        "port": 1080,
        "proxyUserName": "user",
        "proxyPassword": "pass",
    }


@pytest.mark.asyncio
async def test_virtualbrowser_update_translates_proxy_config(monkeypatch):
    provider = VirtualBrowserProvider()
    client = SimpleNamespace(update_browser=AsyncMock(return_value=True))
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    env = Environment(
        name="env",
        kind=EnvKind.BROWSER,
        provider=provider.name,
        status=EnvStatus.READY,
        external_id="303",
        handle=BrowserHandle(browser_id="303"),
    )
    proxy = ProxyConfig(
        mode=ProxyMode.POOL,
        static_value="socks5://user:pass@10.0.0.8:1080",
        current_ip="10.0.0.8",
        ip_entry_id="ip-1",
    )

    assert await provider.update(env, {"proxy": proxy.to_dict()}) is True

    client.update_browser.assert_awaited_once()
    assert client.update_browser.await_args.args[0] == 303
    assert client.update_browser.await_args.args[1]["proxy"] == {
        "mode": 2,
        "value": "",
        "protocol": "SOCKS5",
        "host": "10.0.0.8",
        "port": "1080",
        "user": "user",
        "pass": "pass",
        "API": "",
        "url": "socks5://user:pass@10.0.0.8:1080",
        "country": "",
        "checkFailed": False,
    }


@pytest.mark.asyncio
async def test_virtualbrowser_create_only_verifies_proxy_without_ip_table_fingerprint(monkeypatch):
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.platform.system",
        lambda: "Windows",
    )
    provider = VirtualBrowserProvider()
    client = SimpleNamespace(
        add_browser=AsyncMock(return_value=303),
        get_browser_full_parameters=AsyncMock(
            return_value={
                "id": 303,
                "name": "env-geo",
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
    args, kwargs = client.add_browser.await_args
    assert kwargs["geo"] is None
    assert args[2]["checkFailed"] is False
    assert args[3]["ua-language"] == {"mode": 2}
    assert args[3]["time-zone"] == {"mode": 2}
    assert args[3]["location"] == {"mode": 2, "enable": 1}
    assert args[3]["speech_voices"]["mode"] == 1
    assert len(args[3]["speech_voices"]["value"]) == 5
    client.get_browser_full_parameters.assert_awaited_once_with(303)


@pytest.mark.asyncio
async def test_virtualbrowser_create_uses_native_speech_voices_on_macos(monkeypatch):
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.platform.system",
        lambda: "Darwin",
    )
    provider = VirtualBrowserProvider()
    client = SimpleNamespace(
        add_browser=AsyncMock(return_value=303),
        get_browser_full_parameters=AsyncMock(return_value={"id": 303, "speech_voices": {"mode": 1}}),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    env = await provider.create(
        {
            "env_name": "env-macos-native-voices",
            "creation_params": {"virtualbrowser": {"chrome_version": 145}},
        }
    )

    fingerprint = client.add_browser.await_args.args[3]
    assert "speech_voices" not in fingerprint
    assert env.fingerprint_validation_warnings == []


@pytest.mark.asyncio
async def test_virtualbrowser_create_uses_ip_table_fingerprint_values_and_only_verifies_proxy(monkeypatch):
    provider = VirtualBrowserProvider()
    client = SimpleNamespace(
        add_browser=AsyncMock(return_value=303),
        randomize_fingerprint=AsyncMock(return_value=True),
        update_browser=AsyncMock(return_value=True),
        get_browser_full_parameters=AsyncMock(return_value={"id": 303}),
    )

    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    probe_entries = []

    def _probe_geo(entry):
        probe_entries.append(entry)
        return provider_module.ProxyProbeResult(
            ok=True,
            stage="probe",
            protocol="http",
            masked_proxy_url="http://10.0.0.8:8080",
            latency_ms=12,
            exit_ip="203.0.113.8",
            http_status=200,
            detail="ok",
            error_type=None,
        )

    monkeypatch.setattr(provider_module, "probe_ip_entry_geo", _probe_geo)

    await provider.create(
        {
            "env_name": "env-manual-geo",
            "geo": {
                "country": "CN",
                "timezone": "Asia/Shanghai",
                "language": "zh-CN,zh,en-US,en",
                "latitude": 39.9,
                "longitude": 116.36,
            },
            "creation_params": {
                "proxy": {
                    "protocol": "http",
                    "host": "10.0.0.8",
                    "port": 8080,
                },
            },
        }
    )

    _, kwargs = client.add_browser.await_args
    assert kwargs["geo"] is None
    assert probe_entries[0].address == "10.0.0.8"
    client.randomize_fingerprint.assert_awaited_once_with(303)
    controlled = client.update_browser.await_args.args[1]
    assert (controlled["cpu"]["value"], controlled["memory"]["value"]) in (
        provider_module.VIRTUALBROWSER_COMMON_HARDWARE_PROFILES
    )
    assert (controlled["screen"]["width"], controlled["screen"]["height"]) in (
        provider_module.VIRTUALBROWSER_COMMON_SCREEN_RESOLUTIONS
    )
    assert "proxy" not in controlled
    assert controlled["ua-language"] == {
        "mode": 1,
        "language": "zh-CN",
        "value": "zh-CN,zh,en-US,en",
    }
    assert controlled["time-zone"] == {
        "mode": 1,
        "zone": "(UTC+08:00) Asia/Shanghai",
        "utc": "Asia/Shanghai",
        "locale": "zh-CN",
        "value": 8,
    }
    assert controlled["location"] | {"precision": 0} == {
        "mode": 1,
        "enable": 1,
        "longitude": "116.36",
        "latitude": "39.9",
        "precision": 0,
    }


@pytest.mark.asyncio
async def test_virtualbrowser_create_uses_structured_static_proxy_with_empty_value(monkeypatch):
    provider = VirtualBrowserProvider()
    client = SimpleNamespace(
        add_browser=AsyncMock(return_value=303),
        randomize_fingerprint=AsyncMock(return_value=True),
        update_browser=AsyncMock(return_value=True),
        get_browser_full_parameters=AsyncMock(return_value={"id": 303}),
    )
    raw_proxy = "http://alice:secret@10.0.0.8:8080"
    geo = {
        "country": "CN",
        "timezone": "Asia/Shanghai",
        "language": "zh-CN,zh,en-US,en",
        "latitude": 31.2304,
        "longitude": 121.4737,
    }

    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    monkeypatch.setattr(
        provider_module,
        "probe_ip_entry_geo",
        lambda _entry: provider_module.ProxyProbeResult(
            ok=True,
            stage="probe",
            protocol="http",
            masked_proxy_url="http://alice:***@10.0.0.8:8080",
            latency_ms=12,
            exit_ip="203.0.113.8",
            http_status=200,
            detail="ok",
            error_type=None,
        ),
    )

    await provider.create(
        {
            "env_name": "env-static-proxy",
            "proxy": {
                "mode": ProxyMode.STATIC,
                "static_value": raw_proxy,
            },
            "geo": geo,
        }
    )

    args, kwargs = client.add_browser.await_args
    assert args[2] == {
        "mode": 2,
        "value": "",
        "protocol": "HTTP",
        "host": "10.0.0.8",
        "port": "8080",
        "user": "alice",
        "pass": "secret",
        "API": "",
        "url": raw_proxy,
        "country": "CN",
        "checkFailed": False,
    }
    assert args[3]["__randomize_fingerprint__"] is True
    assert args[3]["chrome_version"] in provider_module.VIRTUALBROWSER_RANDOM_CHROME_VERSIONS
    client.randomize_fingerprint.assert_awaited_once_with(303)
    assert "proxy" not in client.update_browser.await_args.args[1]


@pytest.mark.asyncio
async def test_virtualbrowser_create_randomizes_then_applies_minimal_patch(monkeypatch):
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.platform.system",
        lambda: "Windows",
    )
    provider = VirtualBrowserProvider()
    randomized_parameters = {
        "id": 303,
        "chrome_version": 145,
        "ua": {
            "mode": 0,
            "value": "Mozilla/5.0 (Windows NT 10.0; WOW64) Chrome/145.0.0.0 Safari/537.36",
        },
        "ua-full-version": {"mode": 1, "value": "145.0.7632.12"},
        "sec-ch-ua": {"mode": 0, "value": [{"brand": "Chromium", "version": 145}]},
        "ua-language": {"mode": 2, "language": "", "value": ""},
        "time-zone": {"mode": 2, "utc": "", "value": 0},
        "location": {"mode": 2, "enable": 1, "longitude": "0", "latitude": "0", "precision": 3000},
        "cpu": {"mode": 1, "value": 2},
        "memory": {"mode": 1, "value": 8},
        "screen": {"mode": 0, "width": 1920, "height": 1080},
        "speech_voices": {"mode": 1, "value": {}},
    }
    final_parameters = {
        "id": 303,
        "chrome_version": 145,
        "ua": {
            "mode": 1,
            "value": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0.0.0 Safari/537.36",
        },
        "ua-full-version": {"mode": 1, "value": "145.0.7632.12"},
        "ua-language": {"mode": 1, "language": "ja-JP", "value": "ja-JP,ja"},
        "time-zone": {"mode": 1, "utc": "Asia/Tokyo"},
        "location": {
            "mode": 1,
            "enable": 1,
            "longitude": "139.6917",
            "latitude": "35.6895",
            "precision": 1500,
        },
        "cpu": {"mode": 1, "value": 8},
        "memory": {"mode": 1, "value": 16},
        "screen": {"mode": 1, "width": 1920, "height": 1080},
    }
    client = SimpleNamespace(
        add_browser=AsyncMock(return_value=303),
        randomize_fingerprint=AsyncMock(return_value=True),
        update_browser=AsyncMock(return_value=True),
        get_browser_full_parameters=AsyncMock(side_effect=[randomized_parameters, final_parameters]),
    )
    geo = {
        "country": "JP",
        "timezone": "Asia/Tokyo",
        "language": "ja-JP,ja",
        "latitude": 35.6895,
        "longitude": 139.6917,
    }

    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    monkeypatch.setattr(provider_module, "select_virtualbrowser_chrome_version", lambda: 145)
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.secrets.choice",
        lambda _items: (8, 16),
    )

    await provider.create(
        {
            "env_name": "env-vendor-random",
            "geo": geo,
            "creation_params": {"virtualbrowser": {"__randomize_fingerprint__": True}},
        }
    )

    args, kwargs = client.add_browser.await_args
    assert args[3] == {"__randomize_fingerprint__": True, "chrome_version": 145}
    assert kwargs["geo"] is None
    client.randomize_fingerprint.assert_awaited_once_with(303)
    patch = client.update_browser.await_args.args[1]
    assert patch["cpu"] == {"mode": 1, "value": 8}
    assert patch["memory"] == {"mode": 1, "value": 16}
    assert patch["screen"] == {
        "mode": 1,
        "width": 1920,
        "height": 1080,
        "_value": "1920 x 1080",
    }
    assert "Win64; x64" in patch["ua"]["value"]
    assert patch["ua-language"] == {"mode": 1, "language": "ja-JP", "value": "ja-JP,ja"}
    assert patch["time-zone"]["utc"] == "Asia/Tokyo"
    assert patch["location"]["longitude"] == "139.6917"
    assert patch["speech_voices"] == provider_module.build_virtualbrowser_speech_voices_override()
    assert "ua-full-version" not in patch
    assert "sec-ch-ua" not in patch
    assert "proxy" not in patch
    assert client.get_browser_full_parameters.await_count == 2


@pytest.mark.asyncio
async def test_virtualbrowser_update_randomizes_then_applies_minimal_patch(monkeypatch):
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.platform.system",
        lambda: "Windows",
    )
    provider = VirtualBrowserProvider()
    randomized_parameters = {
        "id": 303,
        "ua": {"mode": 0, "value": "Mozilla/5.0 (Windows NT 10.0; WOW64) Chrome/145.0.0.0"},
        "cpu": {"mode": 1, "value": 2},
        "memory": {"mode": 1, "value": 64},
        "screen": {"mode": 0, "width": 1920, "height": 1080},
        "speech_voices": {"mode": 1, "value": {}},
    }
    final_parameters = {
        "id": 303,
        "chrome_version": 145,
        "ua": {"mode": 1, "value": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0.0.0"},
        "ua-full-version": {"mode": 1, "value": "145.0.7632.12"},
        "ua-language": {"mode": 2},
        "time-zone": {"mode": 2},
        "location": {"mode": 2, "enable": 1},
        "cpu": {"mode": 1, "value": 8},
        "memory": {"mode": 1, "value": 16},
        "screen": {"mode": 1, "width": 1920, "height": 1080},
        "speech_voices": provider_module.build_virtualbrowser_speech_voices_override(),
    }
    client = SimpleNamespace(
        randomize_fingerprint=AsyncMock(return_value=True),
        update_browser=AsyncMock(return_value=True),
        get_browser_full_parameters=AsyncMock(side_effect=[randomized_parameters, final_parameters]),
    )
    env = Environment(
        name="env",
        kind=EnvKind.BROWSER,
        provider=provider.name,
        status=EnvStatus.READY,
        external_id="303",
        handle=BrowserHandle(browser_id="303"),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    monkeypatch.setattr("src.core.rem.virtualbrowser_fingerprint.secrets.choice", lambda _items: (8, 16))

    assert await provider.update(env, {"randomize_fingerprint": True}) is True

    client.randomize_fingerprint.assert_awaited_once_with(303)
    patch = client.update_browser.await_args.args[1]
    assert patch["cpu"] == {"mode": 1, "value": 8}
    assert patch["memory"] == {"mode": 1, "value": 16}
    assert patch["screen"]["mode"] == 1
    assert patch["ua-language"] == {"mode": 2}
    assert patch["time-zone"] == {"mode": 2}
    assert patch["location"] == {"mode": 2, "enable": 1}
    assert "proxy" not in patch
    assert client.get_browser_full_parameters.await_count == 2
    assert env.fingerprint_validation_warnings == []


@pytest.mark.asyncio
async def test_virtualbrowser_create_deletes_external_env_when_randomize_fails(monkeypatch):
    provider = VirtualBrowserProvider()
    client = SimpleNamespace(
        add_browser=AsyncMock(return_value=303),
        randomize_fingerprint=AsyncMock(return_value=False),
        update_browser=AsyncMock(return_value=True),
        get_browser_full_parameters=AsyncMock(
            return_value={
                "id": 303,
                "ua": {"mode": 0, "value": "Mozilla/5.0 Chrome/145.0.7632.12"},
            }
        ),
        delete_browser=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    with pytest.raises(RuntimeError, match="randomizeFingerprint 失败"):
        await provider.create({"env_name": "env-controlled-write-failure"})

    client.delete_browser.assert_awaited_once_with(303)


@pytest.mark.asyncio
async def test_virtualbrowser_runtime_fingerprint_check_uses_page_visible_values(monkeypatch):
    provider = VirtualBrowserProvider()
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/145.0.0.0"
    full_version = "145.0.7632.116"
    page = SimpleNamespace(
        evaluate=AsyncMock(
            return_value={
                "ua": ua,
                "uaCh": {"fullVersionList": [{"brand": "Chromium", "version": full_version}]},
                "language": "ja-JP",
                "languages": ["ja-JP", "ja"],
                "timezone": "Asia/Tokyo",
                "screen": {"width": 1920, "height": 1080},
                "voices": [{"name": "Google 日本語", "lang": "ja-JP"}],
                "webrtc": {"hasRawPrivateAddress": False, "candidateTypes": ["host"]},
            }
        )
    )
    handle = BrowserHandle(browser_id="303")
    handle._page = page
    env = Environment(
        id=101,
        name="vb-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.RUNNING,
        external_id="303",
        handle=handle,
    )
    client = SimpleNamespace(
        get_browser_full_parameters=AsyncMock(
            return_value={
                "id": 303,
                "chrome_version": 145,
                "ua": {"mode": 0, "value": ua},
                "ua-full-version": {"mode": 1, "value": full_version},
                "ua-language": {"mode": 1, "language": "ja-JP", "value": "ja"},
                "time-zone": {"mode": 1, "utc": "Asia/Tokyo"},
                "screen": {"mode": 1, "width": 1920, "height": 1080},
                "speech_voices": {"mode": 1, "value": [{"name": "Google 日本語"}]},
            }
        )
    )

    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await provider.validate_runtime_fingerprint_environment(env) == []
    page.evaluate.assert_awaited_once()


@pytest.mark.asyncio
async def test_virtualbrowser_runtime_fingerprint_check_flags_page_visible_mismatches(monkeypatch):
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.platform.system",
        lambda: "Windows",
    )
    provider = VirtualBrowserProvider()
    page = SimpleNamespace(
        evaluate=AsyncMock(
            return_value={
                "ua": "Mozilla/5.0 Chrome/144.0.0.0",
                "uaCh": {"fullVersionList": [{"brand": "Chromium", "version": "144.0.7559.177"}]},
                "language": "en-US",
                "languages": ["en-US"],
                "timezone": "America/New_York",
                "screen": {"width": 1366, "height": 768},
                "devicePixelRatio": 1.25,
                "voices": [],
                "webrtc": {"hasRawPrivateAddress": True, "candidateTypes": ["host"]},
            }
        )
    )
    handle = BrowserHandle(browser_id="304")
    handle._page = page
    env = Environment(
        id=102,
        name="vb-env-mismatch",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.RUNNING,
        external_id="304",
        handle=handle,
    )
    client = SimpleNamespace(
        get_browser_full_parameters=AsyncMock(
            return_value={
                "id": 304,
                "chrome_version": 145,
                "ua": {"mode": 0, "value": "Mozilla/5.0 Chrome/145.0.0.0"},
                "ua-full-version": {"mode": 1, "value": "145.0.7632.116"},
                "ua-language": {"mode": 1, "language": "ja-JP", "value": "ja"},
                "time-zone": {"mode": 1, "utc": "Asia/Tokyo"},
                "screen": {"mode": 1, "width": 1920, "height": 1080},
                "speech_voices": {"mode": 1, "value": [{"name": "Google 日本語"}]},
            }
        )
    )

    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    warnings = await provider.validate_runtime_fingerprint_environment(env)

    assert any("navigator.userAgent" in warning for warning in warnings)
    assert any("ua-full-version" in warning for warning in warnings)
    assert any("navigator.language" in warning for warning in warnings)
    assert any("time-zone" in warning for warning in warnings)
    assert "screen 配置=1920x1080，页面=1366x768，devicePixelRatio=1.25" in warnings
    assert any("speechSynthesis" in warning for warning in warnings)
    assert any("WebRTC" in warning for warning in warnings)


@pytest.mark.asyncio
async def test_virtualbrowser_runtime_fingerprint_check_accepts_native_macos_voices(monkeypatch):
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.platform.system",
        lambda: "Darwin",
    )
    provider = VirtualBrowserProvider()
    page = SimpleNamespace(
        evaluate=AsyncMock(
            return_value={
                "voices": [{"name": "Ting-Ting", "lang": "zh-CN"}],
                "webrtc": {"supported": True, "hasRawPrivateAddress": False, "candidateTypes": []},
            }
        )
    )
    handle = BrowserHandle(browser_id="305")
    handle._page = page
    env = Environment(
        id=103,
        name="vb-env-macos-voices",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.RUNNING,
        external_id="305",
        handle=handle,
    )
    client = SimpleNamespace(
        get_browser_full_parameters=AsyncMock(
            return_value={
                "id": 305,
                "speech_voices": {
                    "mode": 1,
                    "value": [{"name": "Google UK English Male"}],
                },
            }
        )
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await provider.validate_runtime_fingerprint_environment(env) == []


@pytest.mark.asyncio
async def test_virtualbrowser_runtime_fingerprint_check_accepts_unavailable_macos_voices(monkeypatch):
    monkeypatch.setattr(
        "src.core.rem.virtualbrowser_fingerprint.platform.system",
        lambda: "Darwin",
    )
    provider = VirtualBrowserProvider()
    page = SimpleNamespace(
        evaluate=AsyncMock(
            return_value={
                "voices": [],
                "webrtc": {"supported": True, "hasRawPrivateAddress": False, "candidateTypes": []},
            }
        )
    )
    handle = BrowserHandle(browser_id="306")
    handle._page = page
    env = Environment(
        id=104,
        name="vb-env-macos-empty-voices",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.RUNNING,
        external_id="306",
        handle=handle,
    )
    client = SimpleNamespace(get_browser_full_parameters=AsyncMock(return_value={"id": 306}))
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await provider.validate_runtime_fingerprint_environment(env) == []


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
    assert 1000 <= location["precision"] <= 2000
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
        get_browser_detail=AsyncMock(return_value={"id": 101}),
        launch_browser=AsyncMock(side_effect=RuntimeError("Launch Error: DevTools port not detected")),
    )

    monkeypatch.setattr(provider, "is_window_open", AsyncMock(return_value=False))
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    with pytest.raises(
        RuntimeError,
        match="VirtualBrowser launchBrowser 失败: Launch Error: DevTools port not detected",
    ):
        await provider.open(env)


@pytest.mark.asyncio
async def test_virtualbrowser_open_replays_complete_proxy_after_launch(monkeypatch):
    provider = VirtualBrowserProvider()
    env = Environment(
        id=101,
        name="vb-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        handle=BrowserHandle(browser_id="101"),
    )
    snapshot = {
        "id": 101,
        "name": "vb-env",
        "proxy": {
            "mode": 2,
            "value": "",
            "protocol": "HTTP",
            "host": "10.0.0.8",
            "port": "8080",
            "user": "alice",
            "pass": "secret",
            "url": "http://alice:secret@10.0.0.8:8080",
            "country": "CN",
            "checkFailed": False,
        },
    }
    sequence: list[str] = []

    async def get_browser_detail(browser_id: int):
        assert browser_id == 101
        sequence.append("snapshot")
        return snapshot

    async def launch_browser(browser_id: int):
        assert browser_id == 101
        sequence.append("launch")
        return "ws://127.0.0.1:9222/devtools/browser/abc"

    async def update_browser(browser_id: int, config: dict):
        assert browser_id == 101
        assert config == {
            "proxy": {
                "mode": 2,
                "value": "",
                "protocol": "HTTP",
                "host": "10.0.0.8",
                "port": "8080",
                "user": "alice",
                "pass": "secret",
                "API": "",
                "url": "http://alice:secret@10.0.0.8:8080",
                "country": "CN",
                "checkFailed": False,
            }
        }
        sequence.append("restore")
        return True

    client = SimpleNamespace(
        get_browser_detail=AsyncMock(side_effect=get_browser_detail),
        launch_browser=AsyncMock(side_effect=launch_browser),
        update_browser=AsyncMock(side_effect=update_browser),
    )
    monkeypatch.setattr(provider, "is_window_open", AsyncMock(return_value=False))
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await provider.open(env) is True

    assert sequence == ["snapshot", "launch", "restore"]
    assert env.handle is not None
    assert env.handle.ws_url == "ws://127.0.0.1:9222/devtools/browser/abc"


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

    client = SimpleNamespace(
        get_browser_detail=AsyncMock(side_effect=lambda browser_id: {"id": browser_id}),
        launch_browser=AsyncMock(side_effect=launch_browser),
        update_browser=AsyncMock(return_value=True),
    )

    monkeypatch.setattr(provider, "is_window_open", AsyncMock(return_value=False))
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await asyncio.gather(provider.open(env_a), provider.open(env_b)) == [True, True]
    assert max_active_launches == 1
    assert launch_order == [101, 102]
    client.update_browser.assert_not_awaited()
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

    client = SimpleNamespace(
        stop_browser=AsyncMock(side_effect=stop_browser),
        is_browser_running=AsyncMock(return_value=False),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await asyncio.gather(provider.close(env_a), provider.close(env_b)) == [True, True]
    assert max_active_stops == 1
    assert stop_order == [101, 102]


@pytest.mark.asyncio
async def test_virtualbrowser_close_waits_for_process_and_old_cdp_port(monkeypatch):
    provider = VirtualBrowserProvider()
    env = Environment(
        id=101,
        name="vb-cookie-restart",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.RUNNING,
        handle=BrowserHandle(browser_id="101", ws_url="ws://127.0.0.1:57204/devtools/browser/test"),
    )
    old_handle = env.handle
    assert old_handle is not None
    monkeypatch.setattr(old_handle, "safe_close", AsyncMock())
    client = SimpleNamespace(
        stop_browser=AsyncMock(),
        is_browser_running=AsyncMock(side_effect=[False, False]),
    )
    cdp_reachable = AsyncMock(side_effect=[True, False])
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    monkeypatch.setattr(provider, "_is_cdp_endpoint_reachable", cdp_reachable)
    monkeypatch.setattr(provider_module.asyncio, "sleep", AsyncMock())

    assert await provider.close(env) is True

    old_handle.safe_close.assert_awaited_once()
    client.stop_browser.assert_awaited_once_with(101)
    assert client.is_browser_running.await_count == 2
    assert cdp_reachable.await_count == 2
    assert env.handle is not old_handle
    assert env.handle is not None
    assert env.handle.browser_id == "101"
    assert env.handle.ws_url == ""


@pytest.mark.asyncio
async def test_virtualbrowser_close_fails_when_running_state_cannot_be_confirmed(monkeypatch):
    provider = VirtualBrowserProvider()
    env = Environment(
        id=101,
        name="vb-cookie-query-failure",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.RUNNING,
        handle=BrowserHandle(browser_id="101", ws_url="ws://127.0.0.1:57204/devtools/browser/test"),
    )
    old_handle = env.handle
    assert old_handle is not None
    monkeypatch.setattr(old_handle, "safe_close", AsyncMock())
    client = SimpleNamespace(
        stop_browser=AsyncMock(),
        is_browser_running=AsyncMock(side_effect=RuntimeError("management unavailable")),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    monkeypatch.setattr(provider, "_is_cdp_endpoint_reachable", AsyncMock(return_value=False))

    with pytest.raises(RuntimeError, match="management unavailable"):
        await provider.close(env)

    assert env.handle is old_handle


@pytest.mark.asyncio
async def test_virtualbrowser_close_fails_when_old_cdp_port_never_closes(monkeypatch):
    provider = VirtualBrowserProvider()
    env = Environment(
        id=101,
        name="vb-cookie-cdp-exhausted",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.RUNNING,
        handle=BrowserHandle(browser_id="101", ws_url="ws://127.0.0.1:57204/devtools/browser/test"),
    )
    old_handle = env.handle
    assert old_handle is not None
    monkeypatch.setattr(old_handle, "safe_close", AsyncMock())
    client = SimpleNamespace(
        stop_browser=AsyncMock(),
        is_browser_running=AsyncMock(return_value=False),
    )
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)
    monkeypatch.setattr(provider, "_is_cdp_endpoint_reachable", AsyncMock(return_value=True))
    monkeypatch.setattr(provider_module.asyncio, "sleep", AsyncMock())

    with pytest.raises(RuntimeError, match="CDP 端口未关闭"):
        await provider.close(env)

    assert env.handle is old_handle
    assert client.is_browser_running.await_count == 20


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


@pytest.mark.asyncio
async def test_virtualbrowser_clear_cache_uses_external_browser_id(monkeypatch):
    provider = VirtualBrowserProvider()
    env = Environment(
        id=185,
        name="vb-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=EnvStatus.READY,
        external_id="903",
    )
    client = SimpleNamespace(clear_cache=AsyncMock(return_value=True))
    monkeypatch.setattr(provider, "_get_api_client", lambda: client)

    assert await provider.clear_cache(env) is True
    client.clear_cache.assert_awaited_once_with(903)

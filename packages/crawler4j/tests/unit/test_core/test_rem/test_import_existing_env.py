from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.rem.ip_pool import IPEntry, IPPool
from src.core.rem.manager import EnvironmentManager
from src.core.rem.models import Environment, EnvKind, EnvStatus, ProviderEnvInfo, ProxyConfig, ProxyMode


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("src.utils.paths.get_app_data_dir", lambda: tmp_path)
    from src.core.persistence.database import init_database

    init_database()
    yield tmp_path


@pytest.mark.asyncio
async def test_list_unsynced_provider_envs_filters_existing_provider_name(monkeypatch):
    manager = EnvironmentManager()
    await manager.pool.add(
        Environment(
            name="already-synced",
            kind=EnvKind.BROWSER,
            provider="virtualbrowser",
            status=EnvStatus.READY,
            external_id="local-old-id",
        )
    )

    provider = SimpleNamespace(
        supports_existing_env_import=lambda: True,
        list_existing_envs=AsyncMock(
            return_value=[
                ProviderEnvInfo(
                    provider="virtualbrowser",
                    provider_label="Virtual Browser",
                    external_id="provider-new-id",
                    name="already-synced",
                ),
                ProviderEnvInfo(
                    provider="virtualbrowser",
                    provider_label="Virtual Browser",
                    external_id="local-old-id",
                    name="same-id-different-name",
                ),
                ProviderEnvInfo(
                    provider="virtualbrowser",
                    provider_label="Virtual Browser",
                    external_id="201",
                    name="unsynced",
                ),
            ]
        ),
    )

    monkeypatch.setattr("src.core.rem.manager.get_provider", lambda name: provider if name == "virtualbrowser" else None)

    unsynced = await manager.list_unsynced_provider_envs("virtualbrowser")

    assert [item.external_id for item in unsynced] == ["local-old-id", "201"]


@pytest.mark.asyncio
async def test_import_existing_env_reuses_existing_provider_name(monkeypatch):
    manager = EnvironmentManager()
    await manager.pool.add(
        Environment(
            name="vb-imported",
            kind=EnvKind.BROWSER,
            provider="virtualbrowser",
            status=EnvStatus.READY,
            external_id="local-old-id",
        )
    )
    existing = (await manager.list_envs())[0]
    provider_env = ProviderEnvInfo(
        provider="virtualbrowser",
        provider_label="Virtual Browser",
        external_id="provider-new-id",
        name="vb-imported",
    )
    provider = SimpleNamespace(
        supports_existing_env_import=lambda: True,
        get_existing_env=AsyncMock(return_value=provider_env),
        build_imported_environment=AsyncMock(),
    )

    monkeypatch.setattr("src.core.rem.manager.get_provider", lambda name: provider if name == "virtualbrowser" else None)

    env = await manager.import_existing_env("virtualbrowser", "vb-imported")

    assert env.id == existing.id
    provider.build_imported_environment.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_existing_env_persists_only_provider_name_and_external_id(monkeypatch):
    manager = EnvironmentManager()
    provider_env = ProviderEnvInfo(
        provider="virtualbrowser",
        provider_label="Virtual Browser",
        external_id="301",
        name="vb-imported",
        proxy_summary="SOCKS5 127.0.0.1:1080",
        remark="demo",
        is_running=True,
        running_status="运行中",
        last_used_at=1_746_000_000,
    )

    provider = SimpleNamespace(
        supports_existing_env_import=lambda: True,
        get_existing_env=AsyncMock(return_value=provider_env),
        build_imported_environment=AsyncMock(
            side_effect=lambda info: Environment(
                name=info.name,
                kind=EnvKind.BROWSER,
                provider=info.provider,
                status=EnvStatus.READY,
                external_id=info.external_id,
            )
        ),
    )

    monkeypatch.setattr("src.core.rem.manager.get_provider", lambda name: provider if name == "virtualbrowser" else None)

    env = await manager.import_existing_env("virtualbrowser", "vb-imported")

    reloaded = await manager.get_env(env.id)
    assert reloaded is not None
    assert reloaded.provider == "virtualbrowser"
    assert reloaded.name == "vb-imported"
    assert reloaded.external_id == "301"
    assert not hasattr(reloaded, "provider_env_id")
    assert not hasattr(reloaded, "provider_env_name")
    assert not hasattr(reloaded, "provider_group")
    assert not hasattr(reloaded, "provider_proxy")
    assert not hasattr(reloaded, "provider_raw_meta")
    assert not hasattr(reloaded, "imported_at")


@pytest.mark.asyncio
async def test_sync_source_proxies_matches_imported_env_proxy_to_ip_entry(monkeypatch):
    manager = EnvironmentManager()
    await manager.pool.add(
        Environment(
            name="vb-imported",
            kind=EnvKind.BROWSER,
            provider="virtualbrowser",
            status=EnvStatus.READY,
            external_id="301",
        )
    )
    env = (await manager.list_envs())[0]
    source_proxy = ProxyConfig(
        mode=ProxyMode.STATIC,
        static_value="socks5://alice:secret@10.0.0.8:1080",
        current_ip="10.0.0.8",
    )
    provider_env = ProviderEnvInfo(
        provider="virtualbrowser",
        provider_label="Virtual Browser",
        external_id="301",
        name="vb-imported",
        proxy_config=source_proxy,
    )
    provider = SimpleNamespace(
        supports_existing_env_import=lambda: True,
        get_imported_env_info=AsyncMock(return_value=provider_env),
    )
    pool = IPPool(id="pool-1", name="Pool 1")
    pool.entries = [
        IPEntry(
            id="ip-1",
            pool_id="pool-1",
            address="10.0.0.8",
            protocol="socks5",
            port=1080,
            username="alice",
            password="secret",
        )
    ]

    monkeypatch.setattr("src.core.rem.manager.get_provider", lambda name: provider if name == "virtualbrowser" else None)
    monkeypatch.setattr(
        "src.core.rem.manager.get_ip_pool_manager",
        lambda: SimpleNamespace(list_pools=lambda: [pool]),
    )

    preview = await manager.preview_source_proxy_sync()
    assert len(preview.items) == 1
    assert preview.items[0].env_id == env.id
    assert preview.items[0].action == "bind_ip_entry"
    assert preview.items[0].ip_entry_id == "ip-1"
    assert preview.items[0].pool_id == "pool-1"

    result = await manager.sync_source_proxies(preview)

    assert result.updated_count == 1
    assert result.bound_count == 1
    reloaded = await manager.get_env(env.id)
    assert reloaded is not None
    assert reloaded.proxy_config is not None
    assert reloaded.proxy_config.static_value == "socks5://alice:secret@10.0.0.8:1080"
    assert reloaded.proxy_config.current_ip == "10.0.0.8"
    assert reloaded.proxy_config.ip_entry_id == "ip-1"
    assert reloaded.proxy_config.pool_id == "pool-1"


@pytest.mark.asyncio
async def test_sync_source_proxies_matches_ip_entry_by_host_and_port_only(monkeypatch):
    manager = EnvironmentManager()
    await manager.pool.add(
        Environment(
            name="vb-imported",
            kind=EnvKind.BROWSER,
            provider="virtualbrowser",
            status=EnvStatus.READY,
            external_id="301",
        )
    )
    env = (await manager.list_envs())[0]
    source_proxy = ProxyConfig(
        mode=ProxyMode.STATIC,
        static_value="socks5://alice:secret@10.0.0.8:1080",
        current_ip="10.0.0.8",
    )
    provider = SimpleNamespace(
        supports_existing_env_import=lambda: True,
        get_imported_env_info=AsyncMock(
            return_value=ProviderEnvInfo(
                provider="virtualbrowser",
                provider_label="Virtual Browser",
                external_id="301",
                name="vb-imported",
                proxy_config=source_proxy,
            )
        ),
    )
    pool = IPPool(id="pool-1", name="Pool 1")
    pool.entries = [
        IPEntry(
            id="ip-1",
            pool_id="pool-1",
            address="10.0.0.8",
            protocol="http",
            port=1080,
            username="different-user",
            password="different-password",
        )
    ]

    monkeypatch.setattr("src.core.rem.manager.get_provider", lambda name: provider if name == "virtualbrowser" else None)
    monkeypatch.setattr(
        "src.core.rem.manager.get_ip_pool_manager",
        lambda: SimpleNamespace(list_pools=lambda: [pool]),
    )

    preview = await manager.preview_source_proxy_sync()

    assert len(preview.items) == 1
    assert preview.items[0].env_id == env.id
    assert preview.items[0].action == "bind_ip_entry"
    assert preview.items[0].ip_entry_id == "ip-1"
    assert preview.items[0].pool_id == "pool-1"

    result = await manager.sync_source_proxies(preview)

    assert result.updated_count == 1
    assert result.bound_count == 1
    reloaded = await manager.get_env(env.id)
    assert reloaded is not None
    assert reloaded.proxy_config is not None
    assert reloaded.proxy_config.static_value == "socks5://alice:secret@10.0.0.8:1080"
    assert reloaded.proxy_config.ip_entry_id == "ip-1"
    assert reloaded.proxy_config.pool_id == "pool-1"


@pytest.mark.asyncio
async def test_sync_source_proxies_repairs_local_forward_proxy_binding(monkeypatch):
    manager = EnvironmentManager()
    await manager.pool.add(
        Environment(
            name="vb-imported",
            kind=EnvKind.BROWSER,
            provider="virtualbrowser",
            status=EnvStatus.READY,
            external_id="301",
            proxy_config=ProxyConfig(
                mode=ProxyMode.STATIC,
                static_value="http://127.0.0.1:23080",
                current_ip="127.0.0.1",
                ip_entry_id="ip-local",
                pool_id="pool-local",
            ),
        )
    )
    source_proxy = ProxyConfig(
        mode=ProxyMode.STATIC,
        static_value="http://124.225.43.95:6789",
        current_ip="124.225.43.95",
    )
    provider = SimpleNamespace(
        supports_existing_env_import=lambda: True,
        get_imported_env_info=AsyncMock(
            return_value=ProviderEnvInfo(
                provider="virtualbrowser",
                provider_label="Virtual Browser",
                external_id="301",
                name="vb-imported",
                proxy_config=source_proxy,
            )
        ),
    )
    pool = IPPool(id="pool-real", name="Real Pool")
    pool.entries = [
        IPEntry(
            id="ip-real",
            pool_id="pool-real",
            address="124.225.43.95",
            protocol="http",
            port=6789,
        )
    ]

    monkeypatch.setattr("src.core.rem.manager.get_provider", lambda name: provider if name == "virtualbrowser" else None)
    monkeypatch.setattr(
        "src.core.rem.manager.get_ip_pool_manager",
        lambda: SimpleNamespace(list_pools=lambda: [pool]),
    )

    result = await manager.sync_source_proxies()

    assert result.updated_count == 1
    assert result.bound_count == 1
    reloaded = (await manager.list_envs())[0]
    assert reloaded.proxy_config is not None
    assert reloaded.proxy_config.static_value == "http://124.225.43.95:6789"
    assert reloaded.proxy_config.current_ip == "124.225.43.95"
    assert reloaded.proxy_config.ip_entry_id == "ip-real"
    assert reloaded.proxy_config.pool_id == "pool-real"


@pytest.mark.asyncio
async def test_sync_source_proxies_skips_when_ip_entry_not_found(monkeypatch):
    manager = EnvironmentManager()
    await manager.pool.add(
        Environment(
            name="vb-unmatched",
            kind=EnvKind.BROWSER,
            provider="virtualbrowser",
            status=EnvStatus.READY,
            external_id="302",
        )
    )
    env = (await manager.list_envs())[0]
    source_proxy = ProxyConfig(
        mode=ProxyMode.STATIC,
        static_value="http://bob:secret@10.0.0.9:8080",
        current_ip="10.0.0.9",
    )
    provider = SimpleNamespace(
        supports_existing_env_import=lambda: True,
        get_imported_env_info=AsyncMock(
            return_value=ProviderEnvInfo(
                provider="virtualbrowser",
                provider_label="Virtual Browser",
                external_id="302",
                name="vb-unmatched",
                proxy_config=source_proxy,
            )
        ),
    )

    monkeypatch.setattr("src.core.rem.manager.get_provider", lambda name: provider if name == "virtualbrowser" else None)
    monkeypatch.setattr(
        "src.core.rem.manager.get_ip_pool_manager",
        lambda: SimpleNamespace(list_pools=lambda: []),
    )

    result = await manager.sync_source_proxies()

    assert result.updated_count == 0
    assert result.bound_count == 0
    assert result.cleared_count == 0
    assert result.items[0].action == "skip"
    reloaded = await manager.get_env(env.id)
    assert reloaded is not None
    assert reloaded.proxy_config is None


@pytest.mark.asyncio
async def test_sync_source_proxies_clears_existing_binding_when_source_not_in_ip_table(monkeypatch):
    manager = EnvironmentManager()
    await manager.pool.add(
        Environment(
            name="vb-stale",
            kind=EnvKind.BROWSER,
            provider="virtualbrowser",
            status=EnvStatus.READY,
            external_id="303",
            proxy_config=ProxyConfig(
                mode=ProxyMode.STATIC,
                static_value="http://127.0.0.1:23080",
                current_ip="127.0.0.1",
                ip_entry_id="ip-stale",
                pool_id="pool-stale",
            ),
        )
    )
    source_proxy = ProxyConfig(
        mode=ProxyMode.STATIC,
        static_value="http://bob:secret@10.0.0.9:8080",
        current_ip="10.0.0.9",
    )
    provider = SimpleNamespace(
        supports_existing_env_import=lambda: True,
        get_imported_env_info=AsyncMock(
            return_value=ProviderEnvInfo(
                provider="virtualbrowser",
                provider_label="Virtual Browser",
                external_id="303",
                name="vb-stale",
                proxy_config=source_proxy,
            )
        ),
    )

    monkeypatch.setattr("src.core.rem.manager.get_provider", lambda name: provider if name == "virtualbrowser" else None)
    monkeypatch.setattr(
        "src.core.rem.manager.get_ip_pool_manager",
        lambda: SimpleNamespace(list_pools=lambda: []),
    )

    result = await manager.sync_source_proxies()

    assert result.updated_count == 1
    assert result.bound_count == 0
    assert result.cleared_count == 1
    assert result.items[0].action == "clear_ip_binding"
    reloaded = (await manager.list_envs())[0]
    assert reloaded.proxy_config is None

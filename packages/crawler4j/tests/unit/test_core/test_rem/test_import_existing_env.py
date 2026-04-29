from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.core.rem.manager import EnvironmentManager
from src.core.rem.models import Environment, EnvKind, EnvStatus, ProviderEnvInfo


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

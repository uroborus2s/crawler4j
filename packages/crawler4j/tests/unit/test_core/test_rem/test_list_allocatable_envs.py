from contextlib import ExitStack
from unittest.mock import AsyncMock, patch

import pytest

from src.core.rem.manager import (
    RESOURCE_POOL_METADATA_NAMESPACE,
    EnvironmentManager,
    build_resource_pool_card,
    build_resource_pool_metadata_key,
)
from src.core.rem.models import Environment, EnvKind, EnvStatus, EnvUnavailableError


@pytest.fixture
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))

        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


@pytest.fixture
def manager(temp_data_dir):
    with patch("src.core.rem.ip_pool.get_ip_pool_manager") as mock_get_pool:
        mock_get_pool.return_value = AsyncMock()
        yield EnvironmentManager()


async def _add_env(
    manager: EnvironmentManager,
    *,
    name: str,
    kind: EnvKind = EnvKind.BROWSER,
    status: EnvStatus = EnvStatus.READY,
    lease_id: str | None = None,
) -> Environment:
    env = Environment(
        name=name,
        kind=kind,
        provider="allocatable-provider",
        status=status,
        lease_id=lease_id,
        external_id=f"ext-{name}",
    )
    await manager.pool.add(env)
    return env


@pytest.mark.asyncio
async def test_list_allocatable_envs_filters_by_module_pool_eligibility_ready_and_lease(
    manager,
):
    current_module = "demo_module.worker"
    current_pool = "bound_account_ready"
    current_key = build_resource_pool_metadata_key(current_module, current_pool)
    other_module_key = build_resource_pool_metadata_key("other_module", current_pool)
    other_pool_key = build_resource_pool_metadata_key(current_module, "other_pool")

    eligible_ready = await _add_env(manager, name="eligible-ready")
    ineligible_ready = await _add_env(manager, name="ineligible-ready")
    leased_ready = await _add_env(manager, name="leased-ready", lease_id="lease-3")
    paused_eligible = await _add_env(manager, name="paused-eligible", status=EnvStatus.PAUSED)
    wrong_module = await _add_env(manager, name="wrong-module")
    wrong_pool = await _add_env(manager, name="wrong-pool")
    wrong_kind = await _add_env(manager, name="wrong-kind", kind=EnvKind.HTTP)
    missing_card = await _add_env(manager, name="missing-card")

    await manager.set_metadata(
        eligible_ready.id,
        RESOURCE_POOL_METADATA_NAMESPACE,
        current_key,
        build_resource_pool_card(current_module, current_pool, eligible=True),
        value_type="json",
    )
    await manager.set_metadata(
        ineligible_ready.id,
        RESOURCE_POOL_METADATA_NAMESPACE,
        current_key,
        build_resource_pool_card(current_module, current_pool, eligible=False, reason="blacklisted"),
        value_type="json",
    )
    await manager.set_metadata(
        leased_ready.id,
        RESOURCE_POOL_METADATA_NAMESPACE,
        current_key,
        build_resource_pool_card(current_module, current_pool, eligible=True),
        value_type="json",
    )
    await manager.set_metadata(
        paused_eligible.id,
        RESOURCE_POOL_METADATA_NAMESPACE,
        current_key,
        build_resource_pool_card(current_module, current_pool, eligible=True),
        value_type="json",
    )
    await manager.set_metadata(
        wrong_module.id,
        RESOURCE_POOL_METADATA_NAMESPACE,
        other_module_key,
        build_resource_pool_card("other_module", current_pool, eligible=True),
        value_type="json",
    )
    await manager.set_metadata(
        wrong_pool.id,
        RESOURCE_POOL_METADATA_NAMESPACE,
        other_pool_key,
        build_resource_pool_card(current_module, "other_pool", eligible=True),
        value_type="json",
    )
    await manager.set_metadata(
        wrong_kind.id,
        RESOURCE_POOL_METADATA_NAMESPACE,
        current_key,
        build_resource_pool_card(current_module, current_pool, eligible=True),
        value_type="json",
    )

    allocatable = await manager.list_allocatable_envs(current_module, current_pool)

    assert [env.id for env in allocatable] == [eligible_ready.id]
    excluded_ids = {
        ineligible_ready.id,
        leased_ready.id,
        paused_eligible.id,
        wrong_module.id,
        wrong_pool.id,
        wrong_kind.id,
        missing_card.id,
    }
    assert excluded_ids.isdisjoint({env.id for env in allocatable})


@pytest.mark.asyncio
async def test_list_allocatable_envs_excludes_running_even_without_lease(manager):
    current_module = "demo_module.worker"
    current_pool = "bound_account_ready"
    current_key = build_resource_pool_metadata_key(current_module, current_pool)

    running_unleased = await _add_env(
        manager,
        name="running-unleased",
        status=EnvStatus.RUNNING,
    )

    await manager.set_metadata(
        running_unleased.id,
        RESOURCE_POOL_METADATA_NAMESPACE,
        current_key,
        build_resource_pool_card(current_module, current_pool, eligible=True),
        value_type="json",
    )

    allocatable = await manager.list_allocatable_envs(current_module, current_pool)

    assert allocatable == []


@pytest.mark.asyncio
async def test_lease_manager_rejects_running_env_without_lease(manager):
    running_env = await _add_env(
        manager,
        name="running-no-lease",
        status=EnvStatus.RUNNING,
    )

    with pytest.raises(EnvUnavailableError, match="已被占用"):
        await manager.lease_manager.acquire(running_env, "task-running")

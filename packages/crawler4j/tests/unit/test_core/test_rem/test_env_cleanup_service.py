from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.rem.cleanup_service import EnvCleanupService
from src.core.rem.env_claims import (
    CLAIM_ABANDONED,
    CLAIM_CLAIMED,
    ENV_CLAIM_NAMESPACE,
    ENV_CLAIM_OWNER_MODULE,
    ENV_CLAIM_STATE,
)
from src.core.rem.models import EnvKind, EnvStatus, Environment


def _env(
    env_id: int,
    *,
    status: EnvStatus = EnvStatus.READY,
    lease_id: str | None = None,
    task_run_id: str | None = None,
) -> Environment:
    return Environment(
        id=env_id,
        name=f"env-{env_id}",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=status,
        external_id=str(env_id),
        lease_id=lease_id,
        task_run_id=task_run_id,
    )


class _FakePool:
    def __init__(self, envs: dict[int, Environment]):
        self._envs = envs

    async def get(self, env_id: int | str) -> Environment | None:
        return self._envs.get(int(env_id))


class _FakeEnvironmentManager:
    def __init__(self, envs: dict[int, Environment]):
        self._envs = envs
        self.pool = _FakePool(envs)
        self.metadata: dict[tuple[int, str, str], object] = {}
        self.destroyed: list[int] = []
        self.last_destroy_error = ""

    async def list_envs(self) -> list[Environment]:
        return list(self._envs.values())

    async def set_metadata(self, env_id: int | str, namespace: str, key: str, value, value_type: str = "string"):
        self.metadata[(int(env_id), namespace, key)] = value

    async def list_metadata(self, env_id: int | str, namespace: str) -> dict[str, object]:
        return {
            key: value
            for (stored_env_id, stored_namespace, key), value in self.metadata.items()
            if stored_env_id == int(env_id) and stored_namespace == namespace
        }

    async def destroy_env(self, env_id: int | str) -> bool:
        self.destroyed.append(int(env_id))
        return True


class _FakeModuleService:
    def __init__(self):
        self.registry = SimpleNamespace(
            get_enabled_modules=lambda: [
                SimpleNamespace(name="demo_module", source=SimpleNamespace(value="external")),
            ]
        )

    def get_runtime_descriptor_v2(self, module_name: str):
        assert module_name == "demo_module"
        return SimpleNamespace(
            env_cleanup_candidates={
                "unused_accounts": SimpleNamespace(
                    meta=SimpleNamespace(
                        name="unused_accounts",
                        label="长期未用账号环境",
                        description="",
                    )
                )
            }
        )

    async def resolve_env_cleanup_candidates_async(self, module_name, context, cleanup_name, params=None):
        assert module_name == "demo_module"
        assert cleanup_name == "unused_accounts"
        assert context.tools.list_tools() == []
        return [1, 2, 2, 3, 404]


class _FakeTaskRepository:
    async def get_running_tasks(self):
        return []

    async def list_jobs(self):
        return []


async def _seed_claim(manager: _FakeEnvironmentManager, env_id: int, owner: str) -> None:
    await manager.set_metadata(env_id, ENV_CLAIM_NAMESPACE, ENV_CLAIM_OWNER_MODULE, owner, "string")
    await manager.set_metadata(env_id, ENV_CLAIM_NAMESPACE, ENV_CLAIM_STATE, CLAIM_CLAIMED, "string")


async def _seed_claim_state(manager: _FakeEnvironmentManager, env_id: int, owner: str, state: str) -> None:
    await manager.set_metadata(env_id, ENV_CLAIM_NAMESPACE, ENV_CLAIM_OWNER_MODULE, owner, "string")
    await manager.set_metadata(env_id, ENV_CLAIM_NAMESPACE, ENV_CLAIM_STATE, state, "string")


def _patch_cleanup_runtime(monkeypatch):
    import src.core.rem.cleanup_service as cleanup_service

    monkeypatch.setattr(
        cleanup_service,
        "build_runtime_capabilities",
        lambda *_args, **_kwargs: SimpleNamespace(
            tools=SimpleNamespace(list_tools=lambda: []),
            db=SimpleNamespace(),
        ),
    )
    monkeypatch.setattr(
        cleanup_service,
        "module_bound_env_ids",
        lambda module_name, module_service=None: {1, 2, 3} if module_name == "demo_module" else set(),
    )


@pytest.mark.asyncio
async def test_env_cleanup_preview_deduplicates_and_marks_safety(monkeypatch):
    manager = _FakeEnvironmentManager(
        {
            1: _env(1),
            2: _env(2, status=EnvStatus.BUSY),
            3: _env(3, lease_id="lease-1"),
        }
    )
    await _seed_claim(manager, 1, "demo_module")
    await _seed_claim(manager, 2, "demo_module")
    await _seed_claim(manager, 3, "demo_module")
    _patch_cleanup_runtime(monkeypatch)
    service = EnvCleanupService(
        module_service=_FakeModuleService(),
        environment_manager=manager,
        task_repository=_FakeTaskRepository(),
    )

    plan = await service.preview()

    assert [item.env_id for item in plan.items] == [1, 2, 3]
    assert plan.items[0].eligible is True
    assert plan.items[0].sources[0].module_name == "demo_module"
    assert plan.items[1].eligible is False
    assert "状态不允许清理" in plan.items[1].reason
    assert plan.items[2].eligible is False
    assert "租约" in plan.items[2].reason


@pytest.mark.asyncio
async def test_env_cleanup_preview_collects_host_orphan_and_unclaimed_envs(monkeypatch):
    manager = _FakeEnvironmentManager(
        {
            10: _env(10),
            11: _env(11),
            12: _env(12),
        }
    )
    await _seed_claim_state(manager, 11, "demo_module", CLAIM_ABANDONED)
    await _seed_claim(manager, 12, "removed_module")
    _patch_cleanup_runtime(monkeypatch)
    service = EnvCleanupService(
        module_service=_FakeModuleService(),
        environment_manager=manager,
        task_repository=_FakeTaskRepository(),
    )

    plan = await service.preview()

    assert [item.env_id for item in plan.items] == [10, 11, 12]
    assert [item.sources[0].cleanup_name for item in plan.items] == [
        "orphan",
        "module_unclaimed",
        "missing_owner",
    ]
    assert all(item.eligible for item in plan.items)


@pytest.mark.asyncio
async def test_env_cleanup_execute_only_destroys_freshly_eligible_envs(monkeypatch):
    manager = _FakeEnvironmentManager(
        {
            1: _env(1),
            2: _env(2, status=EnvStatus.RUNNING),
            3: _env(3, task_run_id="task-1"),
        }
    )
    await _seed_claim(manager, 1, "demo_module")
    await _seed_claim(manager, 2, "demo_module")
    await _seed_claim(manager, 3, "demo_module")
    _patch_cleanup_runtime(monkeypatch)
    service = EnvCleanupService(
        module_service=_FakeModuleService(),
        environment_manager=manager,
        task_repository=_FakeTaskRepository(),
    )

    result = await service.cleanup()

    assert manager.destroyed == [1]
    assert [(item.env_id, item.outcome) for item in result.items] == [
        (1, "deleted"),
        (2, "skipped"),
        (3, "skipped"),
    ]

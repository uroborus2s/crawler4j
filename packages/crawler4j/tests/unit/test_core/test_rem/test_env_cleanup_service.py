from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.rem.cleanup_service import EnvCleanupService
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
        self.pool = _FakePool(envs)
        self.destroyed: list[int] = []
        self.last_destroy_error = ""

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


@pytest.mark.asyncio
async def test_env_cleanup_preview_deduplicates_and_marks_safety():
    manager = _FakeEnvironmentManager(
        {
            1: _env(1),
            2: _env(2, status=EnvStatus.BUSY),
            3: _env(3, lease_id="lease-1"),
        }
    )
    service = EnvCleanupService(module_service=_FakeModuleService(), environment_manager=manager)

    plan = await service.preview()

    assert [item.env_id for item in plan.items] == [1, 2, 3, 404]
    assert plan.items[0].eligible is True
    assert plan.items[0].sources[0].module_name == "demo_module"
    assert plan.items[1].eligible is False
    assert "状态不允许清理" in plan.items[1].reason
    assert plan.items[2].eligible is False
    assert "租约" in plan.items[2].reason
    assert plan.items[3].eligible is False
    assert "不存在" in plan.items[3].reason


@pytest.mark.asyncio
async def test_env_cleanup_execute_only_destroys_freshly_eligible_envs():
    manager = _FakeEnvironmentManager(
        {
            1: _env(1),
            2: _env(2, status=EnvStatus.RUNNING),
            3: _env(3, task_run_id="task-1"),
        }
    )
    service = EnvCleanupService(module_service=_FakeModuleService(), environment_manager=manager)

    result = await service.cleanup()

    assert manager.destroyed == [1]
    assert [(item.env_id, item.outcome) for item in result.items] == [
        (1, "deleted"),
        (2, "skipped"),
        (3, "skipped"),
        (404, "skipped"),
    ]

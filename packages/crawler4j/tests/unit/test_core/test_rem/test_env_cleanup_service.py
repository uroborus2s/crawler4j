from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.core.atm.models import Job, JobState
from src.core.atm.run_profile import (
    AcquisitionConfig,
    AcquisitionMode,
    ExecutionContext,
    ResourceConfig,
    RunProfile,
)
from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource, UpgradeSourceInfo
from src.core.mms.module_loader import purge_module_namespace
from src.core.mms.service import ModuleService
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


def _manifest(module_name: str) -> ModuleManifest:
    return ModuleManifest(
        name=module_name,
        runtime_api="core-native-v2",
        upgrade_source=UpgradeSourceInfo(repo=f"example/{module_name}"),
    )


def _write_v2_cleanup_module(module_dir, *, include_cleanup: bool) -> None:
    for package_dir in (
        module_dir,
        module_dir / "data",
        module_dir / "cleanups",
    ):
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

    (module_dir / "data" / "accounts.py").write_text(
        """
from crawler4j_contracts import data_table


@data_table(
    name="accounts",
    storage_mode="managed_dataset",
    record_key_field="phone",
    env_binding_field="bound_env_id",
    schema=[
        {"name": "phone", "type": "string", "required": True},
        {"name": "bound_env_id", "type": "integer"},
        {"name": "record_status", "type": "string"},
        {"name": "run_status", "type": "string"},
    ],
)
class Accounts:
    pass
""",
        encoding="utf-8",
    )
    cleanup_file = module_dir / "cleanups" / "discarded_bound_accounts.py"
    if include_cleanup:
        cleanup_file.write_text(
            """
from crawler4j_contracts import env_cleanup_candidates


@env_cleanup_candidates(name="discarded_bound_accounts", label="黑号绑定环境")
def discarded_bound_accounts(ctx, params=None):
    return [791, 811]
""",
            encoding="utf-8",
        )
    elif cleanup_file.exists():
        cleanup_file.unlink()


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

    def get_runtime_descriptor_v2(self, module_name: str, context=None):
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
    def __init__(self, *, active_jobs: list[Job] | None = None, all_jobs: list[Job] | None = None):
        self._active_jobs = list(active_jobs or [])
        self._all_jobs = list(all_jobs or [])

    async def get_running_tasks(self):
        return []

    async def list_jobs(self):
        return self._all_jobs

    async def list_active_jobs(self):
        return self._active_jobs


class _BindingRows:
    def __init__(self, rows):
        self._rows = rows

    def select(self, field_name):
        assert field_name == "bound_env_id"
        return self

    def execute(self):
        return list(self._rows)


class _BindingDb:
    def from_(self, table_name):
        assert table_name == "accounts"
        return _BindingRows([{"bound_env_id": 791}, {"bound_env_id": "811"}])


def _fixed_env_job(env_id: int, *, state: JobState) -> Job:
    return Job(
        id=f"job-{state.value}-{env_id}",
        name=f"fixed-env-{env_id}",
        state=state,
        run_profile=RunProfile(
            resource=ResourceConfig(
                acquisition=AcquisitionConfig(
                    mode=AcquisitionMode.SELECT,
                    env_id=env_id,
                )
            ),
            execution=ExecutionContext(module="demo_module", workflow="main"),
        ),
    )


async def _seed_claim(manager: _FakeEnvironmentManager, env_id: int, owner: str) -> None:
    await manager.set_metadata(env_id, ENV_CLAIM_NAMESPACE, ENV_CLAIM_OWNER_MODULE, owner, "string")
    await manager.set_metadata(env_id, ENV_CLAIM_NAMESPACE, ENV_CLAIM_STATE, CLAIM_CLAIMED, "string")


async def _seed_claim_state(manager: _FakeEnvironmentManager, env_id: int, owner: str, state: str) -> None:
    await manager.set_metadata(env_id, ENV_CLAIM_NAMESPACE, ENV_CLAIM_OWNER_MODULE, owner, "string")
    await manager.set_metadata(env_id, ENV_CLAIM_NAMESPACE, ENV_CLAIM_STATE, state, "string")


def _patch_cleanup_runtime(monkeypatch, *, bound_ids: set[int] | None = None):
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
        lambda module_name, module_service=None: (bound_ids or {1, 2, 3}) if module_name == "demo_module" else set(),
    )


@pytest.mark.asyncio
async def test_env_cleanup_preview_refreshes_devlink_descriptor_before_scanning_cleanup_candidates(
    tmp_path, monkeypatch
):
    module_name = "ctrip_crawler"
    module_dir = tmp_path / module_name
    _write_v2_cleanup_module(module_dir, include_cleanup=False)
    module_info = ModuleInfo(
        name=module_name,
        manifest=_manifest(module_name),
        source=ModuleSource.DEV_LINK,
        path=module_dir,
    )
    module_service = ModuleService()
    module_service.registry = SimpleNamespace(
        get_module=lambda name: module_info if name == module_name else None,
        get_enabled_modules=lambda: [module_info],
        list_modules=lambda: [module_info],
    )

    try:
        assert module_service.get_runtime_descriptor_v2(module_name).env_cleanup_candidates == {}
        _write_v2_cleanup_module(module_dir, include_cleanup=True)

        manager = _FakeEnvironmentManager({791: _env(791), 811: _env(811)})
        await _seed_claim(manager, 791, module_name)
        await _seed_claim(manager, 811, module_name)

        import src.core.atm.runtime_capabilities as runtime_capabilities
        import src.core.rem.cleanup_service as cleanup_service
        import src.core.rem.env_claims as env_claims

        caps = SimpleNamespace(
            tools=SimpleNamespace(list_tools=lambda: []),
            db=_BindingDb(),
        )
        monkeypatch.setattr(runtime_capabilities, "build_runtime_capabilities", lambda *_args, **_kwargs: caps)
        monkeypatch.setattr(cleanup_service, "build_runtime_capabilities", lambda *_args, **_kwargs: caps)
        monkeypatch.setattr(env_claims, "build_runtime_capabilities", lambda *_args, **_kwargs: caps)

        service = EnvCleanupService(
            module_service=module_service,
            environment_manager=manager,
            task_repository=_FakeTaskRepository(),
        )

        plan = await service.preview()

        assert [item.env_id for item in plan.items] == [791, 811]
        assert all(item.eligible for item in plan.items)
        assert plan.errors == ()
    finally:
        purge_module_namespace(module_name)


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
async def test_env_cleanup_preview_keeps_module_candidates_filtered_by_binding_visible(monkeypatch):
    manager = _FakeEnvironmentManager({1: _env(1), 2: _env(2), 3: _env(3)})
    await _seed_claim(manager, 1, "demo_module")
    await _seed_claim(manager, 2, "demo_module")
    await _seed_claim(manager, 3, "demo_module")
    _patch_cleanup_runtime(monkeypatch, bound_ids={1})
    service = EnvCleanupService(
        module_service=_FakeModuleService(),
        environment_manager=manager,
        task_repository=_FakeTaskRepository(),
    )

    plan = await service.preview()

    assert [(item.env_id, item.eligible, item.reason) for item in plan.items[:3]] == [
        (1, True, ""),
        (2, False, "模块业务表未绑定该环境"),
        (3, False, "模块业务表未绑定该环境"),
    ]


@pytest.mark.asyncio
async def test_env_cleanup_preview_passes_existing_env_scope_to_module_candidates(monkeypatch):
    class _ScopeAwareModuleService(_FakeModuleService):
        def __init__(self):
            super().__init__()
            self.seen_scope: list[list[int]] = []

        async def resolve_env_cleanup_candidates_async(self, module_name, context, cleanup_name, params=None):
            self.seen_scope.append(list(context.runtime["_env_candidate_scope_ids"]))
            return [1001, 1002, 1, 2]

    manager = _FakeEnvironmentManager({1: _env(1), 2: _env(2)})
    await _seed_claim(manager, 1, "demo_module")
    await _seed_claim(manager, 2, "demo_module")
    _patch_cleanup_runtime(monkeypatch, bound_ids={1, 2})
    module_service = _ScopeAwareModuleService()
    service = EnvCleanupService(
        module_service=module_service,
        environment_manager=manager,
        task_repository=_FakeTaskRepository(),
    )

    plan = await service.preview()

    assert module_service.seen_scope == [[1, 2]]
    assert [(item.env_id, item.eligible) for item in plan.items] == [(1, True), (2, True)]


@pytest.mark.asyncio
async def test_env_cleanup_ignores_paused_fixed_env_jobs(monkeypatch):
    manager = _FakeEnvironmentManager({1: _env(1)})
    await _seed_claim(manager, 1, "demo_module")
    _patch_cleanup_runtime(monkeypatch)
    service = EnvCleanupService(
        module_service=_FakeModuleService(),
        environment_manager=manager,
        task_repository=_FakeTaskRepository(
            active_jobs=[],
            all_jobs=[_fixed_env_job(1, state=JobState.PAUSED)],
        ),
    )

    plan = await service.preview()

    assert plan.items[0].env_id == 1
    assert plan.items[0].eligible is True
    assert plan.items[0].reason == ""


@pytest.mark.asyncio
async def test_env_cleanup_blocks_active_fixed_env_jobs(monkeypatch):
    manager = _FakeEnvironmentManager({1: _env(1)})
    await _seed_claim(manager, 1, "demo_module")
    _patch_cleanup_runtime(monkeypatch)
    service = EnvCleanupService(
        module_service=_FakeModuleService(),
        environment_manager=manager,
        task_repository=_FakeTaskRepository(
            active_jobs=[_fixed_env_job(1, state=JobState.ACTIVE)],
            all_jobs=[],
        ),
    )

    plan = await service.preview()

    assert plan.items[0].env_id == 1
    assert plan.items[0].eligible is False
    assert plan.items[0].reason == "仍被运行模板固定引用"


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

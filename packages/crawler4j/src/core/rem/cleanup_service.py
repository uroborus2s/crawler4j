"""Host-owned batch environment cleanup orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from crawler4j_contracts import TaskContext

from src.core.atm.models import TaskStatus
from src.core.atm.repository import TaskRepository, get_task_repository
from src.core.atm.runtime_capabilities import (
    RUNTIME_SURFACE_ENV_CLEANUP_CANDIDATES,
    build_runtime_capabilities,
)
from src.core.foundation.logging import logger
from src.core.mms.models import ModuleInfo
from src.core.mms.service import ModuleService, get_module_service
from src.core.rem.env_claims import (
    CLAIM_ABANDONED,
    CLAIM_CLAIMED,
    CLAIM_PENDING,
    get_env_claim,
    module_bound_env_ids,
)
from src.core.rem.models import EnvStatus, Environment

SAFE_CLEANUP_STATUSES = frozenset({EnvStatus.READY, EnvStatus.PAUSED})
ACTIVE_TASK_STATUSES = frozenset({TaskStatus.PENDING, TaskStatus.RUNNING})
HOST_CLEANUP_MODULE = "host"


@dataclass(frozen=True)
class EnvCleanupSource:
    module_name: str
    cleanup_name: str
    label: str = ""
    description: str = ""


@dataclass(frozen=True)
class EnvCleanupScanError:
    module_name: str
    cleanup_name: str
    message: str


@dataclass(frozen=True)
class EnvCleanupPreviewItem:
    env_id: int
    sources: tuple[EnvCleanupSource, ...]
    env_name: str = ""
    provider: str = ""
    status: str = ""
    eligible: bool = False
    reason: str = ""


@dataclass(frozen=True)
class EnvCleanupPreview:
    items: tuple[EnvCleanupPreviewItem, ...] = ()
    errors: tuple[EnvCleanupScanError, ...] = ()

    @property
    def eligible_items(self) -> tuple[EnvCleanupPreviewItem, ...]:
        return tuple(item for item in self.items if item.eligible)


@dataclass(frozen=True)
class EnvCleanupExecutionItem:
    env_id: int
    outcome: str
    reason: str = ""
    sources: tuple[EnvCleanupSource, ...] = ()
    env_name: str = ""
    provider: str = ""
    status: str = ""


@dataclass(frozen=True)
class EnvCleanupExecutionResult:
    items: tuple[EnvCleanupExecutionItem, ...] = ()
    errors: tuple[EnvCleanupScanError, ...] = ()

    @property
    def deleted_count(self) -> int:
        return sum(1 for item in self.items if item.outcome == "deleted")

    @property
    def skipped_count(self) -> int:
        return sum(1 for item in self.items if item.outcome == "skipped")

    @property
    def failed_count(self) -> int:
        return sum(1 for item in self.items if item.outcome == "failed")


class EnvCleanupService:
    """Collect module-declared cleanup candidates and let REM perform deletion."""

    def __init__(
        self,
        *,
        module_service: ModuleService | Any | None = None,
        environment_manager: Any | None = None,
        task_repository: TaskRepository | Any | None = None,
        settings_store: Any | None = None,
    ) -> None:
        self._module_service = module_service or get_module_service()
        if environment_manager is None:
            from src.core.rem.manager import get_environment_manager

            environment_manager = get_environment_manager()
        self._environment_manager = environment_manager
        self._task_repository = task_repository or get_task_repository()
        self._settings_store = settings_store

    async def preview(self, params_by_cleanup: dict[str, dict[str, Any]] | None = None) -> EnvCleanupPreview:
        """Collect and safety-check all host and module cleanup candidate env ids."""

        env_sources: dict[int, list[EnvCleanupSource]] = {}
        errors: list[EnvCleanupScanError] = []
        params_by_cleanup = dict(params_by_cleanup or {})
        installed_modules = self._installed_module_names()
        active_task_env_ids, active_task_ids = await self._active_task_refs()
        fixed_job_env_ids = await self._fixed_job_env_ids()
        module_bound_cache: dict[str, set[int]] = {}

        await self._collect_host_candidates(
            env_sources,
            installed_modules=installed_modules,
            active_task_ids=active_task_ids,
            module_bound_cache=module_bound_cache,
        )

        for module in self._enabled_modules():
            try:
                descriptor = self._module_service.get_runtime_descriptor_v2(module.name)
            except Exception as exc:
                errors.append(EnvCleanupScanError(module.name, "", str(exc) or exc.__class__.__name__))
                continue

            for cleanup_name, entry in sorted(descriptor.env_cleanup_candidates.items()):
                source = EnvCleanupSource(
                    module_name=module.name,
                    cleanup_name=cleanup_name,
                    label=entry.meta.label or cleanup_name,
                    description=entry.meta.description,
                )
                try:
                    context = self._build_context(module)
                    ids = await self._module_service.resolve_env_cleanup_candidates_async(
                        module.name,
                        context,
                        cleanup_name,
                        params_by_cleanup.get(f"{module.name}.{cleanup_name}", {}),
                    )
                except Exception as exc:
                    errors.append(
                        EnvCleanupScanError(module.name, cleanup_name, str(exc) or exc.__class__.__name__)
                    )
                    continue

                for env_id in ids:
                    normalized_env_id = int(env_id)
                    if not await self._module_cleanup_candidate_allowed(
                        normalized_env_id,
                        module.name,
                        module_bound_cache=module_bound_cache,
                    ):
                        continue
                    sources = env_sources.setdefault(normalized_env_id, [])
                    if source not in sources:
                        sources.append(source)

        items = [
            await self._build_preview_item(
                env_id,
                tuple(sources),
                active_task_env_ids=active_task_env_ids,
                fixed_job_env_ids=fixed_job_env_ids,
            )
            for env_id, sources in sorted(env_sources.items(), key=lambda item: item[0])
        ]
        return EnvCleanupPreview(items=tuple(items), errors=tuple(errors))

    async def cleanup(self, params_by_cleanup: dict[str, dict[str, Any]] | None = None) -> EnvCleanupExecutionResult:
        """Rescan cleanup candidates and destroy only currently eligible environments."""

        plan = await self.preview(params_by_cleanup)
        results: list[EnvCleanupExecutionItem] = []
        for item in plan.items:
            active_task_env_ids, _active_task_ids = await self._active_task_refs()
            fixed_job_env_ids = await self._fixed_job_env_ids()
            fresh = await self._build_preview_item(
                item.env_id,
                item.sources,
                active_task_env_ids=active_task_env_ids,
                fixed_job_env_ids=fixed_job_env_ids,
            )
            if not fresh.eligible:
                results.append(self._execution_item_from_preview(fresh, outcome="skipped", reason=fresh.reason))
                continue
            try:
                success = await self._environment_manager.destroy_env(fresh.env_id)
            except Exception as exc:
                logger.warning(f"[REM] 批量清理环境失败: env_id={fresh.env_id} error={exc}")
                results.append(
                    self._execution_item_from_preview(
                        fresh,
                        outcome="failed",
                        reason=str(exc) or exc.__class__.__name__,
                    )
                )
                continue
            if success:
                results.append(self._execution_item_from_preview(fresh, outcome="deleted", reason=""))
            else:
                reason = str(getattr(self._environment_manager, "last_destroy_error", "") or "").strip()
                results.append(
                    self._execution_item_from_preview(
                        fresh,
                        outcome="failed",
                        reason=reason or "环境删除失败",
                    )
                )
        return EnvCleanupExecutionResult(items=tuple(results), errors=plan.errors)

    def _enabled_modules(self) -> list[ModuleInfo]:
        modules = self._module_service.registry.get_enabled_modules()
        return list(modules)

    def _installed_module_names(self) -> set[str]:
        registry = self._module_service.registry
        list_modules = getattr(registry, "list_modules", None)
        if callable(list_modules):
            return {str(module.name) for module in list_modules()}
        return {str(module.name) for module in self._enabled_modules()}

    def _module_config(self, module_name: str) -> dict[str, Any]:
        store = self._settings_store
        if store is None:
            try:
                from src.core.mms.settings_store import get_module_settings_store

                store = get_module_settings_store()
            except Exception:
                return {}
        try:
            value = store.read_module_settings(module_name)
        except Exception:
            return {}
        return value if isinstance(value, dict) else {}

    def _build_context(self, module: ModuleInfo) -> TaskContext:
        runtime: dict[str, Any] = {}
        if getattr(getattr(module, "source", None), "value", "") == "dev_link":
            runtime["devel_mode"] = True
        capabilities = build_runtime_capabilities(module.name, surface=RUNTIME_SURFACE_ENV_CLEANUP_CANDIDATES)
        return TaskContext(
            env_id=0,
            task_name=module.name,
            config=self._module_config(module.name),
            logger=logger,
            tools=capabilities.tools,
            db=capabilities.db,
            runtime=runtime,
        )

    async def _collect_host_candidates(
        self,
        env_sources: dict[int, list[EnvCleanupSource]],
        *,
        installed_modules: set[str],
        active_task_ids: set[str],
        module_bound_cache: dict[str, set[int]],
    ) -> None:
        envs = await self._environment_manager.list_envs()
        for env in envs:
            env_id = int(env.id)
            claim = await get_env_claim(self._environment_manager, env_id)
            source: EnvCleanupSource | None = None
            if not claim.owner_module:
                source = EnvCleanupSource(
                    HOST_CLEANUP_MODULE,
                    "orphan",
                    label="孤岛环境",
                    description="没有 host.env_claim.owner_module 的环境",
                )
            elif claim.owner_module not in installed_modules:
                source = EnvCleanupSource(
                    HOST_CLEANUP_MODULE,
                    "missing_owner",
                    label="owner 模块不存在",
                    description="环境 owner 模块已不存在或未安装",
                )
            elif claim.state in {CLAIM_PENDING, CLAIM_ABANDONED}:
                if claim.task_id and claim.task_id in active_task_ids:
                    continue
                bound_ids = self._module_bound_env_ids(claim.owner_module, module_bound_cache)
                if env_id not in bound_ids:
                    source = EnvCleanupSource(
                        HOST_CLEANUP_MODULE,
                        "module_unclaimed",
                        label="模块未认领环境",
                        description="任务创建后未写入模块 env_binding_field 表",
                    )
            if source is None:
                continue
            env_sources.setdefault(env_id, [])
            if source not in env_sources[env_id]:
                env_sources[env_id].append(source)

    async def _module_cleanup_candidate_allowed(
        self,
        env_id: int,
        module_name: str,
        *,
        module_bound_cache: dict[str, set[int]],
    ) -> bool:
        claim = await get_env_claim(self._environment_manager, int(env_id))
        if claim.owner_module != module_name or claim.state != CLAIM_CLAIMED:
            return False
        return int(env_id) in self._module_bound_env_ids(module_name, module_bound_cache)

    def _module_bound_env_ids(self, module_name: str, cache: dict[str, set[int]]) -> set[int]:
        if module_name not in cache:
            try:
                cache[module_name] = module_bound_env_ids(module_name, module_service=self._module_service)
            except Exception as exc:
                logger.warning(f"[REM] 环境清理读取模块绑定表失败: module={module_name} error={exc}")
                cache[module_name] = set()
        return cache[module_name]

    async def _active_task_refs(self) -> tuple[set[int], set[str]]:
        tasks = await self._task_repository.get_running_tasks()
        env_ids: set[int] = set()
        task_ids: set[str] = set()
        for task in tasks:
            if task.status not in ACTIVE_TASK_STATUSES:
                continue
            task_ids.add(task.id)
            if task.env_id:
                try:
                    env_ids.add(int(task.env_id))
                except (TypeError, ValueError):
                    continue
        return env_ids, task_ids

    async def _fixed_job_env_ids(self) -> set[int]:
        list_jobs = getattr(self._task_repository, "list_jobs", None)
        if not callable(list_jobs):
            return set()
        env_ids: set[int] = set()
        try:
            jobs = await list_jobs()
        except Exception:
            return set()
        for job in jobs:
            run_profile = getattr(job, "run_profile", None)
            acquisition = getattr(getattr(run_profile, "resource", None), "acquisition", None)
            env_id = getattr(acquisition, "env_id", None)
            if env_id is None or env_id == "":
                continue
            try:
                env_ids.add(int(env_id))
            except (TypeError, ValueError):
                continue
        return env_ids

    async def _build_preview_item(
        self,
        env_id: int,
        sources: tuple[EnvCleanupSource, ...],
        *,
        active_task_env_ids: set[int] | None = None,
        fixed_job_env_ids: set[int] | None = None,
    ) -> EnvCleanupPreviewItem:
        env = await self._environment_manager.pool.get(env_id)
        if env is None:
            return EnvCleanupPreviewItem(
                env_id=env_id,
                sources=sources,
                eligible=False,
                reason="环境不存在或已清理",
            )
        eligible, reason = self._eligibility(
            env,
            active_task_env_ids=active_task_env_ids or set(),
            fixed_job_env_ids=fixed_job_env_ids or set(),
        )
        return EnvCleanupPreviewItem(
            env_id=env_id,
            sources=sources,
            env_name=env.name,
            provider=env.provider,
            status=env.status.value,
            eligible=eligible,
            reason=reason,
        )

    @staticmethod
    def _eligibility(
        env: Environment,
        *,
        active_task_env_ids: set[int],
        fixed_job_env_ids: set[int],
    ) -> tuple[bool, str]:
        if env.status not in SAFE_CLEANUP_STATUSES:
            return False, f"状态不允许清理: {env.status.value}"
        if env.lease_id:
            return False, f"环境存在租约: {env.lease_id}"
        if env.task_run_id:
            return False, f"环境关联任务: {env.task_run_id}"
        if int(env.id) in active_task_env_ids:
            return False, "仍有关联任务未结束"
        if int(env.id) in fixed_job_env_ids:
            return False, "仍被运行模板固定引用"
        return True, ""

    @staticmethod
    def _execution_item_from_preview(
        item: EnvCleanupPreviewItem,
        *,
        outcome: str,
        reason: str,
    ) -> EnvCleanupExecutionItem:
        return EnvCleanupExecutionItem(
            env_id=item.env_id,
            outcome=outcome,
            reason=reason,
            sources=item.sources,
            env_name=item.env_name,
            provider=item.provider,
            status=item.status,
        )


_cleanup_service: EnvCleanupService | None = None


def get_env_cleanup_service() -> EnvCleanupService:
    global _cleanup_service
    if _cleanup_service is None:
        _cleanup_service = EnvCleanupService()
    return _cleanup_service

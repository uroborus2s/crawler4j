"""Host-owned batch environment cleanup orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from crawler4j_contracts import TaskContext

from src.core.atm.runtime_capabilities import (
    RUNTIME_SURFACE_ENV_CLEANUP_CANDIDATES,
    build_runtime_capabilities,
)
from src.core.foundation.logging import logger
from src.core.mms.models import ModuleInfo
from src.core.mms.service import ModuleService, get_module_service
from src.core.rem.models import EnvStatus, Environment

SAFE_CLEANUP_STATUSES = frozenset({EnvStatus.READY, EnvStatus.PAUSED})


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
        settings_store: Any | None = None,
    ) -> None:
        self._module_service = module_service or get_module_service()
        if environment_manager is None:
            from src.core.rem.manager import get_environment_manager

            environment_manager = get_environment_manager()
        self._environment_manager = environment_manager
        self._settings_store = settings_store

    async def preview(self, params_by_cleanup: dict[str, dict[str, Any]] | None = None) -> EnvCleanupPreview:
        """Collect and safety-check all declared cleanup candidate env ids."""

        env_sources: dict[int, list[EnvCleanupSource]] = {}
        errors: list[EnvCleanupScanError] = []
        params_by_cleanup = dict(params_by_cleanup or {})

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
                    sources = env_sources.setdefault(normalized_env_id, [])
                    if source not in sources:
                        sources.append(source)

        items = [
            await self._build_preview_item(env_id, tuple(sources))
            for env_id, sources in sorted(env_sources.items(), key=lambda item: item[0])
        ]
        return EnvCleanupPreview(items=tuple(items), errors=tuple(errors))

    async def cleanup(self, params_by_cleanup: dict[str, dict[str, Any]] | None = None) -> EnvCleanupExecutionResult:
        """Rescan cleanup candidates and destroy only currently eligible environments."""

        plan = await self.preview(params_by_cleanup)
        results: list[EnvCleanupExecutionItem] = []
        for item in plan.items:
            fresh = await self._build_preview_item(item.env_id, item.sources)
            if not fresh.eligible:
                results.append(self._execution_item_from_preview(fresh, outcome="skipped", reason=fresh.reason))
                continue
            try:
                success = await self._environment_manager.destroy_env(fresh.env_id)
            except Exception as exc:
                logger.warning("[REM] 批量清理环境失败: env_id=%s error=%s", fresh.env_id, exc)
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

    async def _build_preview_item(
        self,
        env_id: int,
        sources: tuple[EnvCleanupSource, ...],
    ) -> EnvCleanupPreviewItem:
        env = await self._environment_manager.pool.get(env_id)
        if env is None:
            return EnvCleanupPreviewItem(
                env_id=env_id,
                sources=sources,
                eligible=False,
                reason="环境不存在或已清理",
            )
        eligible, reason = self._eligibility(env)
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
    def _eligibility(env: Environment) -> tuple[bool, str]:
        if env.status not in SAFE_CLEANUP_STATUSES:
            return False, f"状态不允许清理: {env.status.value}"
        if env.lease_id:
            return False, f"环境存在租约: {env.lease_id}"
        if env.task_run_id:
            return False, f"环境关联任务: {env.task_run_id}"
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

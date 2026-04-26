"""环境管理器 - 统一门面。

规格参考: docs/02-requirements/reference-srs/05-framework-core/05-2-runtime-environment-management.md

EnvironmentManager 是 REM 的统一入口，提供：
    - acquire: 申请环境租约
    - release: 释放环境租约
    - startup: 初始化与崩溃恢复
    - run_gc: 垃圾回收
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Any

from src.core.foundation.logging import logger
from src.core.persistence.database import STATE_DB, get_connection
from src.core.rem.ip_pool import get_ip_pool_manager
from src.core.rem.models import (
    Environment,
    EnvKind,
    EnvLease,
    EnvRequirement,
    EnvStatus,
    EnvUnavailableError,
)
from src.core.rem.pool import EnvPool, LeaseManager
from src.core.rem.provider import BaseProvider, get_provider, list_providers

FINGERPRINT_BROWSER_PROVIDERS = {"bitbrowser", "virtualbrowser"}
DEFAULT_PROVIDER_RUNTIME_TIMEOUT = 30
RECOVERY_PROVIDER_RUNTIME_TIMEOUT = 3
RESOURCE_POOL_METADATA_NAMESPACE = "scheduler.resource_pool"
EXISTING_ENV_IMPORT_METADATA_NAMESPACE = "existing_env_import"
GC_REAPABLE_STATUSES = frozenset(
    {
        EnvStatus.CREATING,
        EnvStatus.DEAD,
        EnvStatus.ERROR,
        EnvStatus.TERMINATING,
    }
)


def _get_env_name_prefix(now: datetime | None = None) -> str:
    """构造当天环境名称前缀。"""
    current = now or datetime.now()
    return f"env-{current.strftime('%Y%m%d')}-"


def _get_next_env_name(existing_names: list[str], now: datetime | None = None) -> str:
    """基于现有名称计算下一个默认环境名。"""
    prefix = _get_env_name_prefix(now)
    prefix_len = len(prefix)
    max_seq = 0

    for name in existing_names:
        if len(name) <= prefix_len:
            continue
        try:
            seq = int(name[prefix_len:])
        except ValueError:
            continue
        if seq > max_seq:
            max_seq = seq

    return f"{prefix}{max_seq + 1}"


def peek_next_env_name(now: datetime | None = None) -> str:
    """读取当前数据库状态下的下一个默认环境名。"""
    prefix = _get_env_name_prefix(now)

    with get_connection(STATE_DB) as conn:
        cursor = conn.execute(
            "SELECT name FROM environments WHERE name LIKE ?",
            (f"{prefix}%",),
        )
        existing_names = [row[0] for row in cursor.fetchall()]

    return _get_next_env_name(existing_names, now)


def normalize_resource_pool_module_name(module_name: str) -> str:
    return str(module_name or "").strip().split(".")[0]


def build_resource_pool_metadata_key(module_name: str, pool_name: str) -> str:
    normalized_module = normalize_resource_pool_module_name(module_name)
    normalized_pool = str(pool_name or "").strip()
    if not normalized_module or not normalized_pool:
        raise ValueError("module_name and pool_name are required")
    return f"{normalized_module}:{normalized_pool}"


def build_resource_pool_card(
    module_name: str,
    pool_name: str,
    *,
    eligible: bool,
    reason: str = "",
    exclusive: bool = True,
    updated_at: int | None = None,
) -> dict[str, object]:
    return {
        "module_name": normalize_resource_pool_module_name(module_name),
        "pool_name": str(pool_name or "").strip(),
        "eligible": bool(eligible),
        "reason": str(reason or ""),
        "exclusive": bool(exclusive),
        "updated_at": int(updated_at or time.time()),
    }


def is_gc_reapable_status(status: EnvStatus) -> bool:
    return status in GC_REAPABLE_STATUSES


def _normalize_env_name(name: object) -> str:
    return str(name or "").strip()


class EnvironmentManager:
    """环境管理器。
    
    规格 5.2.1.2: 核心承诺是为每一次任务运行提供满足约束的环境租约。
    
    Usage:
        manager = EnvironmentManager()
        await manager.startup()
        
        # 申请环境
        requirement = EnvRequirement(kind=EnvKind.BROWSER)
        lease = await manager.acquire(requirement)
        
        # 使用环境...
        env = await manager.get_env(lease.env_id)
        
        # 释放环境
        await manager.release(lease)
    """
    
    def __init__(self):
        """初始化环境管理器。"""
        from src.core.system.preferences_service import (
            PreferenceKey,
            get_preferences_service,
        )
        
        prefs = get_preferences_service()
        max_instances = prefs.get(PreferenceKey.ENV_MAX_INSTANCES, 50)
        
        self.pool = EnvPool(max_instances=max_instances)
        self.lease_manager = LeaseManager(self.pool)
        self._reservation_lock = asyncio.Lock()
        self.last_destroy_error = ""
    
    async def startup(self, *, recover_crashed: bool = True) -> None:
        """启动环境管理器。
        
        执行：
            1. 从数据库恢复环境状态
            2. 处理崩溃残留
            3. 完成基础依赖初始化
        """
        logger.info("[REM] 环境管理器启动中...")
        
        # 从数据库恢复
        await self.pool.load_from_db()
        
        # 初始化 IP 池管理器
        await get_ip_pool_manager().startup()

        # 处理崩溃残留
        if recover_crashed:
            await self._recover_crashed()
        
        logger.info(f"[REM] 环境管理器启动完成, 环境数: {len(await self.pool.list_all())}")
        
    async def acquire(
        self,
        requirement: EnvRequirement,
        default_provider: str = "playwright_local",
    ) -> EnvLease:
        """申请环境租约。
        
        规格 5.2.3.3 Acquire 流程：
            1. 在 READY 实例中挑选匹配项
            2. 若无匹配，按策略 spawn 新实例
            3. 发放租约，将实例置为 BUSY
        
        Args:
            requirement: 环境需求
            default_provider: 默认提供者
        
        Returns:
            环境租约
        
        Raises:
            EnvUnavailableError: 无可用环境
        """
        # 1. 查找可用环境
        env = await self.pool.find_available(requirement)
        
        # 2. 无可用环境则尝试创建
        if not env:
            if not self.pool.can_create():
                from src.core.rem.models import EnvUnavailableError
                raise EnvUnavailableError(
                    "无可用环境且达到配额上限",
                    stage="ACQUIRE",
                    hint="请等待其他任务完成或增加配额"
                )
            
            provider = get_provider(default_provider)
            if not provider:
                from src.core.rem.models import EnvUnavailableError
                raise EnvUnavailableError(
                    f"Provider 未注册: {default_provider}",
                    stage="CREATE",
                    hint="请检查 Provider 配置"
                )
            
            env = await self._create_env(provider, proxy_config=requirement.proxy_config)

        # 3. 发放租约
        if env.lease_id is None and env.status == EnvStatus.RUNNING:
            lease = await self.lease_manager.claim_created_env(
                env,
                requirement.task_run_id,
                timeout=requirement.timeout,
            )
        else:
            lease = await self.lease_manager.acquire(
                env,
                requirement.task_run_id,
                timeout=requirement.timeout,
            )
        
        return lease

    async def acquire_atomic(
        self,
        requirement: EnvRequirement,
        timeout: int = 60,
    ) -> EnvLease:
        """原子申请环境租约 (V2 Mode).
        
        直接通过 DB 锁抢占环境，适用于高并发场景。
        """
        return await self.lease_manager.acquire_atomic(requirement, timeout)
    
    async def recycle_env(self, env: Environment) -> bool:
        """关闭窗口并回收到 READY，不清理浏览器持久数据。"""
    
        provider = get_provider(env.provider)
        # 关闭窗口
        if provider:
            try:
                closed = await provider.close(env)
                if not closed:
                    await self.pool.update_status(env.id, env.status)
                    logger.warning(f"[REM] 关闭窗口失败，环境保持原状态: id={env.id} status={env.status.value}")
                    return False
            except Exception as e:
                logger.warning(f"[REM] 关闭窗口失败: {e}")
                await self.pool.update_status(env.id, env.status)
                self._emit_error(env, "close", str(e))
                return False
        # 清空租约绑定，避免 READY 状态残留旧 lease/task 标记。
        env.lease_id = None
        env.task_run_id = None
        await self.pool.update_status(env.id, EnvStatus.READY)
        logger.info(f"[REM] 环境已回收: id={env.id}")
        return True
    
    async def release(self, lease: EnvLease) -> bool:
        """释放环境租约。
        
        Release 流程：
            1. 验证令牌
            2. 关闭窗口
            3. 恢复为 READY
        
        Args:
            lease: 租约
        
        Returns:
            是否释放成功
        """
        env = await self.lease_manager.release(lease, lease.token)
        if not env:
            return False
        return await self.recycle_env(env)

    async def release_keep_alive(self, lease: EnvLease) -> bool:
        """释放租约但保持环境当前运行状态。"""
        env = await self.lease_manager.release(lease, lease.token)
        if not env:
            return False
        await self.pool.update_status(env.id, env.status)
        logger.info(f"[REM] 环境租约已释放并保持状态: id={env.id}, status={env.status.value}")
        return True
    
    async def get_env(self, env_id: int | str) -> Environment | None:
        """获取环境实例。"""
        return await self.pool.get(env_id)
    
    async def list_envs(self) -> list[Environment]:
        """列出所有环境。"""
        return await self.pool.list_all()

    def list_existing_env_import_sources(self) -> list[dict[str, str]]:
        """列出支持“从已有环境导入”的来源。"""
        sources: list[dict[str, str]] = []
        for provider_name in list_providers():
            provider = get_provider(provider_name)
            if provider and provider.supports_existing_env_import():
                sources.append(
                    {
                        "provider": provider.name,
                        "label": provider.display_name or provider.name,
                    }
                )
        sources.sort(key=lambda item: item["label"].lower())
        return sources

    async def get_env_by_provider_name(
        self,
        provider_name: str,
        name: str,
    ) -> Environment | None:
        """按 provider/name 查找宿主环境。"""
        target_provider = str(provider_name or "").strip()
        target_name = _normalize_env_name(name)
        if not target_provider or not target_name:
            return None
        for env in await self.list_envs():
            if env.provider == target_provider and _normalize_env_name(env.name) == target_name:
                return env
        return None

    async def list_unsynced_provider_envs(self, provider_name: str):
        """列出来源系统中尚未导入宿主环境表的环境。"""
        provider = get_provider(provider_name)
        if not provider or not provider.supports_existing_env_import():
            raise ValueError(f"Provider 不支持已有环境导入: {provider_name}")
        provider_key = str(getattr(provider, "name", provider_name) or provider_name).strip()
        existing_names = {
            (env.provider, _normalize_env_name(env.name))
            for env in await self.list_envs()
            if _normalize_env_name(env.name)
        }
        items = await provider.list_existing_envs()
        return [
            item
            for item in items
            if _normalize_env_name(item.name)
            and (
                str(item.provider or provider_key).strip(),
                _normalize_env_name(item.name),
            )
            not in existing_names
        ]

    async def import_existing_env(self, provider_name: str, name: str) -> Environment:
        """把来源系统中的已有环境导入到宿主环境表。"""
        provider = get_provider(provider_name)
        if not provider or not provider.supports_existing_env_import():
            raise ValueError(f"Provider 不支持已有环境导入: {provider_name}")
        provider_key = str(getattr(provider, "name", provider_name) or provider_name).strip()
        target_name = _normalize_env_name(name)
        if not target_name:
            raise ValueError("来源环境名称不能为空")

        existing = await self.get_env_by_provider_name(provider_key, target_name)
        if existing:
            return existing

        info = await provider.get_existing_env(target_name)
        if not info:
            raise ValueError(f"来源环境不存在: {provider_name}/{target_name}")

        source_name = _normalize_env_name(info.name)
        if not source_name:
            raise ValueError(f"来源环境名称不能为空: {provider_name}/{target_name}")
        existing = await self.get_env_by_provider_name(provider_key, source_name)
        if existing:
            return existing

        env = await provider.build_imported_environment(info)
        env.provider = provider_key
        env.external_id = str(info.external_id or "")
        env.status = EnvStatus.READY
        env.name = env.name or source_name

        await self.pool.add(env)
        return env

    async def mark_existing_env_import_state(
        self,
        env_id: int,
        *,
        status: str,
        module_name: str = "",
        workflow_name: str = "",
        task_id: str = "",
        error: str = "",
        message: str = "",
    ) -> None:
        """记录已有环境导入执行状态。"""
        payload = {
            "status": status,
            "module_name": module_name,
            "workflow_name": workflow_name,
            "task_id": task_id,
            "error": error,
            "message": message,
            "updated_at": int(time.time()),
        }
        await self.set_metadata(
            env_id,
            EXISTING_ENV_IMPORT_METADATA_NAMESPACE,
            "latest",
            payload,
            value_type="json",
        )
    
    async def run_gc(self) -> int:
        """手动触发垃圾回收。

        Returns:
            回收的环境数量
        """
        return await self._gc_once()
    
    async def health_check(self, env_id: int | str) -> bool:
        """执行健康检查，失败则标记 ERROR。
        
        规格 FR-CORE-ENV-004: 周期性或按需检测环境是否可用，不可用时标记隔离。
        
        Args:
            env_id: 环境 ID
        
        Returns:
            是否健康
        """
        env = await self.pool.get(env_id)
        if not env:
            return False
        
        provider = get_provider(env.provider)
        if not provider:
            return False
        
        try:
            is_healthy = await provider.health_check(env)
            if not is_healthy:
                await self.pool.update_status(env_id, EnvStatus.ERROR)
                logger.warning(f"[REM] 环境健康检查失败: id={env_id}")
            return is_healthy
        except Exception as e:
            logger.warning(f"[REM] 健康检查异常: {e}")
            await self.pool.update_status(env_id, EnvStatus.ERROR)
            return False
    
    async def create_env(
        self,
        provider_name: str,
        env_name: str | None = None,
        config: dict | None = None,
        requirement: EnvRequirement | None = None,
        ensure_runtime: bool = True,
    ) -> Environment:
        """创建并启动环境，直到 Playwright 可用。
        
        Args:
            provider_name: Provider 名称
            env_name: 环境名称
            config: 配置
            requirement: 要求
        """
        if not self.pool.can_create():
            raise EnvUnavailableError(
                "达到配额上限",
                stage="CREATE",
                hint="请先销毁其他环境"
            )
        
        provider = get_provider(provider_name)
        if not provider:
            raise EnvUnavailableError(
                f"Provider 未注册: {provider_name}",
                stage="CREATE",
                hint="请检查 Provider 配置"
            )

        if ensure_runtime:
            await self.ensure_provider_runtime(provider_name)
            
        final_config = config or {}
        if env_name:
            final_config["env_name"] = env_name

        proxy_config = requirement.proxy_config if requirement else None

        return await self._create_env(
            provider, 
            final_config, 
            proxy_config=proxy_config,
        )

    async def ensure_provider_runtime(
        self,
        provider_name: str,
        *,
        timeout: int = DEFAULT_PROVIDER_RUNTIME_TIMEOUT,
    ) -> None:
        """确保指定 Provider 的外部运行时已就绪（按需启动）。"""
        await self._ensure_external_provider_ready(provider_name, timeout=timeout)
    
    async def destroy_env(
        self,
        env_id: int | str,
        *,
        runtime_timeout: int = DEFAULT_PROVIDER_RUNTIME_TIMEOUT,
    ) -> bool:
        """直接销毁环境（供 UI 调用）。
        
        Args:
            env_id: 环境 ID
            runtime_timeout: 指纹浏览器 API 就绪等待超时（秒）
        
        Returns:
            是否销毁成功
        """
        env = await self.pool.get(env_id)
        if not env:
            self.last_destroy_error = f"环境不存在: {env_id}"
            return False

        logger.info(f"[REM] 销毁环境: id={env.id}")
        self.last_destroy_error = ""

        previous_status = env.status
        await self.pool.update_status(env.id, EnvStatus.TERMINATING)

        provider = get_provider(env.provider)
        if provider:
            try:
                if provider.name in FINGERPRINT_BROWSER_PROVIDERS:
                    await self.ensure_provider_runtime(provider.name, timeout=runtime_timeout)

                destroyed = await provider.destroy(env)
                if destroyed is False:
                    self.last_destroy_error = (
                        f"{provider.name} 未确认外部环境已删除，可能是外部浏览器仍在关闭或删除接口返回失败。"
                    )
                    logger.warning(
                        f"[REM] 外部环境删除未成功，保留数据库记录: id={env.id} reason={self.last_destroy_error}"
                    )
                    await self.pool.update_status(env.id, previous_status)
                    return False
            except Exception as e:
                self.last_destroy_error = str(e) or e.__class__.__name__
                logger.warning(f"[REM] 环境销毁失败: {e}")
                await self.pool.update_status(env.id, previous_status)
                return False

        await self.pool.remove(env.id)
        logger.info(f"[REM] 环境已销毁: id={env.id}")        
        return True
    
    async def start_env(self, env_id: int | str) -> bool:
        """启动环境（READY/PAUSED → BUSY，打开窗口）。
        
        Args:
            env_id: 环境 ID
        
        Returns:
            是否启动成功
        """
        env = await self.pool.get(env_id)
        if not env:
            return False
        provider = get_provider(env.provider)
        if not provider:
            return False
        if env.status == EnvStatus.RUNNING:
            return True
        if env.provider in FINGERPRINT_BROWSER_PROVIDERS:
            await self.ensure_provider_runtime(env.provider)
        if env.status == EnvStatus.BUSY:
            try:
                if await provider.is_window_open(env):
                    return await self._provider_operation(env, "connect")
            except Exception as e:
                logger.warning(f"[REM] 检查窗口状态失败，按未打开窗口处理: {e}")
            if not await self._provider_operation(env, "open"):
                return False
            return await self._provider_operation(env, "connect")
        if await self._provider_operation(env, "open"):
            return await self._provider_operation(env, "connect")
        return False    
    
    async def stop_env(self, env_id: int | str) -> bool:
        """停止环境（BUSY → READY，关闭窗口）。
        
        Args:
            env_id: 环境 ID
        
        Returns:
            是否停止成功
        """
        env = await self.pool.get(env_id)
        if not env:
            return False
        return await self._provider_operation(env, "close")
    
    async def pause_env(self, env_id: int | str) -> bool:
        """暂停环境（READY → PAUSED）。
        
        Args:
            env_id: 环境 ID
        
        Returns:
            是否暂停成功
        """
        env = await self.pool.get(env_id)
        if not env:
            return False
        return await self._provider_operation(env, "pause")
    
    async def resume_env(self, env_id: int | str) -> bool:
        """恢复环境（PAUSED → READY）。
        
        Args:
            env_id: 环境 ID
        
        Returns:
            是否恢复成功
        """
        env = await self.pool.get(env_id)
        if not env:
            return False
        return await self._provider_operation(env, "resume")
    
    # === Metadata API ===
    
    async def get_metadata(
        self, 
        env_id: int | str,
        namespace: str, 
        key: str
    ) -> Any:
        """获取环境元数据值。
        
        Args:
            env_id: 环境 ID
            namespace: 命名空间（通常为 module_name）
            key: 字段名
        
        Returns:
            元数据值，不存在返回 None
        """
        return self.pool.get_metadata(env_id, namespace, key)
    
    async def set_metadata(
        self,
        env_id: int | str,
        namespace: str,
        key: str,
        value: Any,
        value_type: str = "string",
    ) -> bool:
        """设置环境元数据值。
        
        Args:
            env_id: 环境 ID
            namespace: 命名空间（通常为 module_name）
            key: 字段名
            value: 字段值
            value_type: 类型提示 (string|int|float|bool|json)
        
        Returns:
            是否设置成功
        """
        return self.pool.set_metadata(env_id, namespace, key, value, value_type)
    
    async def list_metadata(
        self,
        env_id: int | str,
        namespace: str | None = None,
    ) -> dict:
        """列出环境元数据。
        
        Args:
            env_id: 环境 ID
            namespace: 命名空间（可选，为空则返回所有）
        
        Returns:
            元数据字典
        """
        return self.pool.list_metadata(env_id, namespace)

    async def list_allocatable_envs(
        self,
        module_name: str,
        pool_name: str,
    ) -> list[Environment]:
        """列出指定模块资源池中当前可分配的环境。"""
        metadata_key = build_resource_pool_metadata_key(module_name, pool_name)
        environments = await self.list_envs()
        allocatable: list[Environment] = []
        for env in environments:
            if env.kind != EnvKind.BROWSER or env.status != EnvStatus.READY or env.lease_id:
                continue
            card = await self.get_metadata(env.id, RESOURCE_POOL_METADATA_NAMESPACE, metadata_key)
            if isinstance(card, dict) and bool(card.get("eligible")):
                allocatable.append(env)
        return allocatable

    async def count_allocatable_envs(
        self,
        module_name: str,
        pool_name: str,
    ) -> int:
        """统计指定模块资源池中当前可分配的环境数量。"""
        environments = await self.list_allocatable_envs(module_name, pool_name)
        return len(environments)

    async def delete_metadata(
        self,
        env_id: int | str,
        namespace: str,
        key: str | None = None,
    ) -> int:
        """删除环境元数据。
        
        Args:
            env_id: 环境 ID
            namespace: 命名空间
            key: 字段名（可选，为空则删除整个 namespace）
        
        Returns:
            删除的条数
        """
        return self.pool.delete_metadata(env_id, namespace, key)
    
    # === 统一更新方法 ===
    
    async def update_env(
        self,
        env_id: int | str,
        *,
        name: str | None = None,
        proxy_value: str | None = None,
        proxy_pool_id: str | None = None,
        randomize_fingerprint: bool = False,
    ) -> bool:
        """统一更新环境配置。
        
        Args:
            env_id: 环境 ID
            name: 新名称（可选）
            proxy_value: 静态代理地址（可选）
            proxy_pool_id: 从 IP 池绑定（可选）
            randomize_fingerprint: 是否刷新指纹
        
        Returns:
            是否更新成功
        """
        env = await self.pool.get(env_id)
        if not env:
            logger.warning(f"[REM] 更新失败: 环境不存在 id={env_id}")
            return False
        
        return await self._orchestrate_update(
            env,
            name=name,
            proxy_value=proxy_value,
            proxy_pool_id=proxy_pool_id,
            randomize_fingerprint=randomize_fingerprint,
        )
    
    async def _orchestrate_update(
        self,
        env: Environment,
        *,
        name: str | None = None,
        proxy_value: str | None = None,
        proxy_pool_id: str | None = None,
        randomize_fingerprint: bool = False,
    ) -> bool:
        """统一更新编排。
        
        Returns:
            是否更新成功
        """
        from src.core.rem.models import ProxyConfig, ProxyMode
        
        updated = False
        provider = get_provider(env.provider)
        
        # 1. 更新名称
        if name:
            env.name = name
            updated = True
        
        # 2. 处理代理更新
        if proxy_value:
            if env.proxy_config is None:
                env.proxy_config = ProxyConfig(mode=ProxyMode.STATIC)
            env.proxy_config.static_value = proxy_value
            env.proxy_config.current_ip = proxy_value.split("@")[-1] if "@" in proxy_value else proxy_value
            updated = True
            logger.info(f"[REM] 代理已更新: id={env.id} value={proxy_value[:20]}...")
        
        # 3. 从 IP 池绑定
        if proxy_pool_id:
            success = await self._bind_ip_if_needed(env, proxy_pool_id)
            if success:
                updated = True
        
        # 4. 刷新指纹
        if randomize_fingerprint and provider:
            try:
                success = await provider.update(env, {"randomize_fingerprint": True})
                if success:
                    logger.info(f"[REM] 指纹已刷新: id={env.id}")
                    updated = True
            except Exception as e:
                logger.warning(f"[REM] 指纹刷新失败: {e}")
        
        # 5. 持久化
        if updated:
            await self.pool.add(env)
        
        return updated
    
    # === Layer 3: 操作层 ===
    async def _provider_operation(
        self,
        env: Environment,
        action: str,
        **kwargs,
    ) -> bool:
        """统一 Provider 操作。
        
        Args:
            provider: Provider 实例
            env: 环境实例
            action: 操作类型 (open/close/destroy/reset/update)
            **kwargs: 额外参数
        
        Returns:
            是否操作成功
            
        Note:
            失败时自动恢复原状态，并通过事件总线发送错误通知。
        """
        provider = get_provider(env.provider)
        if not provider:
            return False
        
        # 保存原始状态，用于失败时恢复
        original_status = env.status
        
        try:
            if action == "open":
                await self.pool.update_status(env.id, EnvStatus.BUSY)
                result = await provider.open(env)
                if not result:
                    # 失败：恢复原状态
                    await self.pool.update_status(env.id, original_status)
                    self._emit_error(env, "open", "外部软件启动失败，请检查软件是否安装或路径配置是否正确")
                return result
            elif action == "connect":
                result = await provider.connect(env)
                if result:
                    # 连接成功：更新使用统计并持久化
                    env.increment_usage()
                    await self.pool.update_status(env.id, EnvStatus.RUNNING)
                    await self.pool.add(env)
                else:
                    await self._handle_connect_failure(
                        env,
                        provider,
                        original_status,
                        "Playwright 连接失败",
                        preserve_window=kwargs.get("preserve_window_on_connect_failure", True),
                    )
                return result
            elif action == "disconnect":
                await self.pool.update_status(env.id, EnvStatus.BUSY)
                result = await provider.disconnect(env)
                if not result:
                    await self.pool.update_status(env.id, original_status)
                return result
            elif action == "close":
                await self.pool.update_status(env.id, EnvStatus.READY)
                result = await provider.close(env)
                if not result:
                    await self.pool.update_status(env.id, original_status)
                return result
            elif action == "pause":
                await self.pool.update_status(env.id, EnvStatus.PAUSED)
                return True
            elif action == "resume":
                await self.pool.update_status(env.id, EnvStatus.READY)
                return True
            elif action == "destroy":
                await provider.destroy(env)
                return True
            elif action == "reset":
                return await provider.reset(env)
            elif action == "update":
                return await provider.update(env, kwargs.get("config", {}))
            elif action == "health_check":
                return await provider.health_check(env)
            else:
                logger.error(f"[REM] 未知的 Provider 操作: {action}")
                return False
        except Exception as e:
            logger.warning(f"[REM] Provider 操作失败: action={action}, error={e}")
            if action == "connect":
                await self._handle_connect_failure(
                    env,
                    provider,
                    original_status,
                    str(e),
                    preserve_window=kwargs.get("preserve_window_on_connect_failure", True),
                )
            else:
                # 异常时恢复原状态
                await self.pool.update_status(env.id, original_status)
                self._emit_error(env, action, str(e))
            return False

    async def _handle_connect_failure(
        self,
        env: Environment,
        provider: BaseProvider,
        original_status: EnvStatus,
        message: str,
        *,
        preserve_window: bool = True,
    ) -> None:
        """处理 connect 失败时的状态回写。

        如果窗口实际上已经打开，则保留 `BUSY`，避免 UI 回退成 `READY`。
        """
        target_status = original_status
        error_message = message

        if preserve_window:
            try:
                if await provider.is_window_open(env):
                    target_status = EnvStatus.BUSY
                    error_message = f"{message}，但浏览器窗口已打开"
            except Exception as e:
                logger.warning(f"[REM] 检查 connect 失败后的窗口状态失败: {e}")

        await self.pool.update_status(env.id, target_status)
        self._emit_error(env, "connect", error_message)
    
    def _emit_error(self, env: Environment, action: str, message: str) -> None:
        """发送错误事件供 UI 层监听。"""
        from src.core.foundation.event_bus import Event, EventType, get_event_bus

        
        get_event_bus().publish(Event(
            type=EventType.ENV_OPERATION_FAILED,
            data={
                "env_id": env.id,
                "env_name": env.name,
                "action": action,
                "message": message,
            }
        ))

    
        
    async def _bind_ip_if_needed(
        self,
        env: Environment,
        pool_id: str,
        bind_strategy: str | None = None,
    ) -> bool:
        """IP 绑定（如果需要）。
        
        Args:
            env: 环境实例
            pool_id: IP 池 ID
        
        Returns:
            是否绑定成功
        """
        from src.core.rem.ip_pool import get_ip_pool_manager
        from src.core.rem.models import ProxyConfig, ProxyMode
        
        pool_manager = get_ip_pool_manager()
        
        # 先解绑旧 IP
        await pool_manager.unbind_ip(env.id)
        
        # 绑定新 IP
        ip = await pool_manager.bind_ip(env.id, pool_id, bind_strategy)
        if ip:
            if env.proxy_config is None:
                env.proxy_config = ProxyConfig(mode=ProxyMode.POOL)
            env.proxy_config.mode = ProxyMode.POOL
            env.proxy_config.pool_id = pool_id
            env.proxy_config.bind_strategy = bind_strategy
            env.proxy_config.current_ip = ip.address
            logger.info(f"[REM] IP 已绑定: id={env.id} ip={ip.address}")
            return True
        
        return False
    
    async def _ensure_external_provider_ready(
        self,
        provider_name: str,
        *,
        timeout: int = DEFAULT_PROVIDER_RUNTIME_TIMEOUT,
    ) -> None:
        """确保外部指纹浏览器软件已启动且 API 就绪。"""
        from src.core.system.external_app_service import ExternalApp, get_external_app_service

        app: ExternalApp | None = None
        if provider_name == "bitbrowser":
            app = ExternalApp.BITBROWSER
        elif provider_name == "virtualbrowser":
            app = ExternalApp.VIRTUALBROWSER

        if app is None:
            return

        app_service = get_external_app_service()
        result = await app_service.ensure_running(app, timeout=timeout)
        if not result.success:
            raise EnvUnavailableError(
                result.error_message or f"{app.value} 启动失败",
                stage="CREATE",
                hint="请检查外部浏览器路径、端口和启动状态",
            )

        # 防止“进程存在但 API 尚未可用”导致 create 阶段出现 502。
        ready = await app_service.wait_until_ready(app, timeout=timeout)
        if not ready:
            raise EnvUnavailableError(
                f"{app.value} API 未就绪",
                stage="CREATE",
                hint="请检查外部浏览器启动日志并确认 API 端口可访问",
            )
    
    
    # === 原有私有方法 ===
    async def _create_env(
        self,
        provider: BaseProvider,
        config: dict | None = None,
        proxy_config: Any | None = None,  # ProxyConfig
    ) -> Environment:
        """创建环境并保持为可运行状态。
        
        流程：
            1. 生成环境名称和 ID
            2. 创建占位环境并持久化
            3. 处理代理绑定（如有）
            4. 调用 Provider 创建
            5. 打开窗口并连接 Playwright
            6. 成功后保持 RUNNING
        """
        from src.core.rem.models import ProxyMode
        
        logger.info(f"[REM] 创建环境: provider={provider.name}")
        
        if config and config.get("env_name"):
            # 用户指定名称
            env_name = config["env_name"]
            skeleton_env = Environment(
                name=env_name,
                kind=provider.kind,
                provider=provider.name,
                status=EnvStatus.CREATING,
                created_at=int(time.time()),
                updated_at=int(time.time()),
                proxy_config=proxy_config,
            )
            # 持久化占位记录
            await self.pool.add(skeleton_env)
        else:
            # 自动生成名称并原子占位
            skeleton_env = await self._reserve_env_placeholder(
                provider.kind, 
                provider.name, 
                proxy_config
            )
            env_name = skeleton_env.name
        
        env_id = skeleton_env.id
        
        try:
            # 3. 处理代理绑定 (如果是 POOL 模式)
            if proxy_config and proxy_config.mode == ProxyMode.POOL and proxy_config.pool_id:
                from src.core.rem.ip_pool import get_ip_pool_manager
                ip_manager = get_ip_pool_manager()
                ip = await ip_manager.bind_ip(
                    env_id,
                    proxy_config.pool_id,
                    proxy_config.bind_strategy,
                )
                if ip:
                    proxy_config.bind_strategy = proxy_config.bind_strategy or "least_bound"
                    proxy_config.current_ip = ip.address
                    # 生成静态代理字符串供 Provider 使用
                    auth = f"{ip.username}:{ip.password}@" if ip.username else ""
                    protocol = ip.protocol or "socks5"
                    proxy_config.static_value = f"{protocol}://{auth}{ip.address}:{ip.port}"
                    logger.info(f"[REM] 环境绑定 IP: id={env_id} ip={ip.address}")
                else:
                    logger.warning(f"[REM] 环境绑定 IP 失败: id={env_id} pool={proxy_config.pool_id}")
            
            # 4. 调用 Provider 创建
            provider_config = dict(config) if config is not None else {}
            provider_config["env_id"] = env_id
            provider_config["env_name"] = env_name
            if proxy_config:
                provider_config["proxy"] = proxy_config.to_dict()
            
            # create 仅负责创建记录，不再启动 (config["launch"] 已弃用或被忽略)
            env = await provider.create(provider_config)
            
            # 修正 id
            env.id = env_id
            env.name = env_name
            
            # 手动合并 POOL 模式生成的静态代理配置
            if proxy_config and proxy_config.mode == ProxyMode.POOL and proxy_config.static_value:
                if env.proxy_config:
                    env.proxy_config.static_value = proxy_config.static_value
                    env.proxy_config.current_ip = proxy_config.current_ip

            # 5. 更新环境记录 (此时有了 external_id)
            env.status = EnvStatus.READY
            
            # 先保存到数据库以确保 ID 存在
            await self.pool.add(env) # update because add was called with skeleton
            
            logger.info(f"[REM] 环境创建成功: id={env_id} external_id={env.external_id}")

            if not await self._provider_operation(env, "open"):
                raise EnvUnavailableError(
                    "环境创建后启动失败",
                    stage="CREATE",
                    hint="请检查外部浏览器路径、启动状态和 Provider 配置",
                )

            if not await self._provider_operation(
                env,
                "connect",
                preserve_window_on_connect_failure=False,
            ):
                await self._provider_operation(env, "close")
                raise EnvUnavailableError(
                    "Playwright 连接失败",
                    stage="CREATE",
                    hint="请检查浏览器调试入口和 Playwright 连接状态",
                )

            return env
            
        except Exception:
            # 如果创建失败，清理占位环境（未在外部创建成功）
            logger.error(f"[REM] 环境创建失败，清理预创建记录: id={env_id}")
            await self.destroy_env(
                env_id,
                runtime_timeout=RECOVERY_PROVIDER_RUNTIME_TIMEOUT,
            )
            raise

    async def _reserve_env_placeholder(
        self, 
        kind: Any, # EnvKind
        provider: str,
        proxy_config: Any | None = None
    ) -> Environment:
        """原子化保留环境名称占位符（Max+1 策略）。
        
        1. 查询当天所有前缀匹配的名称
        2. 计算最大序列号 + 1
        3. 立即插入 CREATING 状态的占位记录
        
        Returns:
            已持久化的 Environment 对象 (带 id)
        """
        now = datetime.now()
        prefix = _get_env_name_prefix(now)

        async with self._reservation_lock:
            with get_connection(STATE_DB) as conn:
                # 先拿写锁，再计算序号并插入，避免并发创建拿到同一个默认名称。
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.execute(
                    "SELECT name FROM environments WHERE name LIKE ?",
                    (f"{prefix}%",)
                )
                existing_names = [row[0] for row in cursor.fetchall()]
                new_name = _get_next_env_name(existing_names, now)

                env = Environment(
                    name=new_name,
                    kind=kind,
                    provider=provider,
                    status=EnvStatus.CREATING,
                    created_at=int(time.time()),
                    updated_at=int(time.time()),
                    proxy_config=proxy_config,
                )
                proxy_config_json = json.dumps(env.proxy_config.to_dict()) if env.proxy_config else None
                cursor = conn.execute(
                    """
                    INSERT INTO environments (
                        name, kind, provider, status, external_id, lease_id, task_run_id,
                        last_used_at, daily_usage_count, daily_usage_date,
                        proxy_config_json, capabilities, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        env.name,
                        env.kind.value,
                        env.provider,
                        env.status.value,
                        env.external_id,
                        env.lease_id,
                        env.task_run_id,
                        env.last_used_at,
                        env.daily_usage_count,
                        env.daily_usage_date,
                        proxy_config_json,
                        json.dumps({"capabilities": list(env.capabilities)}),
                        env.created_at,
                        env.updated_at,
                    )
                )
                env.id = cursor.lastrowid or 0
                cache = getattr(self.pool, "_environments", None)
                if isinstance(cache, dict):
                    cache[env.id] = env

        logger.info(f"[REM] 预留环境名称: {env.name} id={env.id}")
        return env
            
    
    async def _recover_crashed(self) -> None:
        """崩溃恢复：处理非稳态环境。
        
        规格 5.2.3.3 Fail-safe:
            - CREATING 状态的环境：调用 Provider 关闭/销毁后删除记录
            - BUSY 状态的环境：检查窗口状态，优先尝试软回收（recycle_env），失败则置为 DEAD
        """
        for env in await self.pool.list_all():
            provider = get_provider(env.provider)
            if not provider:
                logger.error(f"[REM] 未找到 Provider: {env.provider}")
                await self.destroy_env(
                    env.id,
                    runtime_timeout=RECOVERY_PROVIDER_RUNTIME_TIMEOUT,
                )
            elif is_gc_reapable_status(env.status):
                # 创建中的环境视为失败，需要同步关闭并删除
                logger.warning(f"[REM] 发现未完成创建的环境: id={env.id}")
                if await self.destroy_env(
                    env.id,
                    runtime_timeout=RECOVERY_PROVIDER_RUNTIME_TIMEOUT,
                ):
                    logger.info(f"[REM] 已删除未完成创建的环境记录: id={env.id}")
                else:
                    logger.warning(f"[REM] 未完成创建的环境记录保留，等待下次重试: id={env.id}")
            elif env.status in {EnvStatus.BUSY, EnvStatus.RUNNING}:
                # 用户规范：崩溃时运行中的环境，重启后恢复为 READY
                logger.warning(f"[REM] 发现崩溃时运行中的环境: id={env.id}")
                await self.recycle_env(env)
        
    async def _gc_once(self) -> int:
        """执行一次 GC。
        
        Returns:
            回收的环境数量
        """
        count = 0
        
        for env in await self.pool.list_all():
            provider = get_provider(env.provider)
            if not provider:
                logger.error(f"[REM] 未找到 Provider: {env.provider}")
                if await self.destroy_env(
                    env.id,
                    runtime_timeout=RECOVERY_PROVIDER_RUNTIME_TIMEOUT,
                ):
                    count = count + 1
            elif is_gc_reapable_status(env.status):
                logger.warning(f"[REM] 发现未完成创建的环境: id={env.id}")
                if await self.destroy_env(
                    env.id,
                    runtime_timeout=RECOVERY_PROVIDER_RUNTIME_TIMEOUT,
                ):
                    count = count + 1
                    logger.info(f"[REM] 已删除未完成创建的环境记录: id={env.id}")
                else:
                    logger.warning(f"[REM] 未完成创建的环境记录保留，等待下次重试: id={env.id}")
            elif not await provider.exists(env):
                logger.warning(f"[REM] 发现不存在的环境: id={env.id}")
                if await self.destroy_env(
                    env.id,
                    runtime_timeout=RECOVERY_PROVIDER_RUNTIME_TIMEOUT,
                ):
                    count = count + 1
                    logger.info(f"[REM] 已删除不存在的环境记录: id={env.id}")
            elif env.status in {EnvStatus.BUSY, EnvStatus.RUNNING}:
                # 用户规范：崩溃时运行中的环境，重启后恢复为 READY
                if not await provider.is_window_open(env):
                    logger.warning(f"[REM] 发现运行中崩溃的环境: id={env.id}")
                    await self.recycle_env(env)
                    count = count + 1
            elif env.status == EnvStatus.READY:
                if await provider.is_window_open(env):
                    logger.warning(f"[REM] 发现状态不一致的环境: id={env.id}")
                    await self.recycle_env(env)
                    count = count + 1
        if count > 0:
            logger.info(f"[REM] GC 完成: 回收 {count} 个环境")
        return count

# 全局单例
_manager: EnvironmentManager | None = None


def get_environment_manager() -> EnvironmentManager:
    """获取全局 EnvironmentManager 实例。"""
    global _manager
    if _manager is None:
        _manager = EnvironmentManager()
    return _manager

"""TSM 依赖适配器。

将 REM (EnvironmentManager) 和 MMS (ModuleRegistry) 适配到
Orchestrator 所需的 IEnvironmentManager 和 IModuleExecutor 协议。
"""

from typing import Any

from src.core.foundation.logging import logger


class REMAdapter:
    """REM 适配器 - 适配 IEnvironmentManager 协议。"""

    def __init__(self, env_manager: Any):
        self._rem = env_manager
        # 缓存 lease_id -> (env_id, lease) 映射
        self._lease_cache: dict[str, tuple[str, Any]] = {}

    async def find(
        self,
        env_type: str,
        labels: dict,
        expressions: list[str],
        sort_by: str,
    ) -> list[str]:
        """查找可用环境。"""
        from src.core.rem.models import EnvStatus

        # 简化：获取 READY 状态的环境列表
        envs = [e for e in self._rem.list_envs() if e.status == EnvStatus.READY]
        
        # 返回 env_id 列表 (转为字符串)
        return [str(e.id) for e in envs]

    async def lease(self, env_id: str, task_id: str) -> str:
        """申请环境租约。"""
        from src.core.rem.models import EnvRequirement

        env = self._rem.get_env(int(env_id))
        if not env:
            raise RuntimeError(f"环境不存在: {env_id}")

        requirement = EnvRequirement(task_run_id=task_id)
        lease = await self._rem.acquire(requirement)
        
        # 缓存 lease 以便后续释放
        lease_id = str(lease.id)
        self._lease_cache[lease_id] = (env_id, lease)
        
        return lease_id

    async def release(self, lease_id: str) -> None:
        """释放环境租约。"""
        if lease_id not in self._lease_cache:
            logger.warning(f"[TSM Adapter] Lease not found: {lease_id}")
            return
        
        _, lease = self._lease_cache.pop(lease_id)
        await self._rem.release(lease)

    async def provision(self, env_type: str) -> str:
        """创建新环境。"""
        env = await self._rem.create_env(
            provider_name="playwright_local",
            env_name=None,
            post_action="none",  # 不执行后续操作
        )
        return str(env.id)

    async def destroy(self, env_id: str) -> None:
        """销毁环境。"""
        await self._rem.destroy_env(int(env_id))

    async def count_active(self) -> int:
        """统计活跃环境数。"""
        from src.core.rem.models import EnvStatus

        return sum(1 for e in self._rem.list_envs() if e.status != EnvStatus.ERROR)


class MMSAdapter:
    """MMS 适配器 - 适配 IModuleExecutor 协议。"""

    def __init__(self, module_registry: Any):
        self._mms = module_registry

    async def execute(
        self,
        module: str,
        task: str,
        env_id: str,
        params: dict,
    ) -> dict[str, Any]:
        """执行模块任务。
        
        TODO: 这里需要实现真正的模块执行逻辑。
        目前返回模拟成功结果。
        """
        logger.info(f"[TSM Adapter] Executing {module}::{task} on env {env_id}")
        
        # TODO: 实际调用 workflow 执行器
        # module_info = self._mms.get_module(module)
        # if module_info:
        #     workflow = self._find_workflow(module_info, task)
        #     return await workflow.execute(env_id, params)
        
        return {"success": True, "message": f"Executed {module}::{task}"}


def configure_orchestrator():
    """配置 Orchestrator 依赖注入。
    
    应在应用启动时调用（REM 初始化之后）。
    """
    from src.core.mms import get_module_registry
    from src.core.rem.manager import get_environment_manager
    from src.core.tsm.orchestrator import get_orchestrator

    rem = get_environment_manager()
    mms = get_module_registry()
    orchestrator = get_orchestrator()

    rem_adapter = REMAdapter(rem)
    mms_adapter = MMSAdapter(mms)

    orchestrator.configure(rem_adapter, mms_adapter)
    logger.info("[TSM] Orchestrator 依赖注入完成")

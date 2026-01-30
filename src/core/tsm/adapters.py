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
        
        Args:
            module: 模块名称
            task: 工作流名称
            env_id: 环境 ID
            params: 任务参数
            
        Returns:
            执行结果字典
        """
        import importlib
        
        from crawler4j_sdk import TaskContext
        from src.core.rem.manager import get_environment_manager
        
        logger.info(f"[TSM Adapter] Executing {module}::{task} on env {env_id}")
        
        # 1. 获取模块信息
        module_info = self._mms.get_module(module)
        if not module_info:
            return {"success": False, "error": f"Module not found: {module}"}
        
        # 2. 查找工作流
        workflow_info = None
        for wf in module_info.manifest.workflows:
            if wf.name == task:
                workflow_info = wf
                break
        
        if not workflow_info:
            return {"success": False, "error": f"Workflow not found: {task}"}
        
        # 3. 获取环境和 Page
        rem = get_environment_manager()
        env = await rem.get_env(int(env_id))
        if not env:
            return {"success": False, "error": f"Environment not found: {env_id}"}
        
        # 提取 Page（使用 BrowserHandle）
        page = None
        context = None
        if env.handle:
            page = env.handle.page
            context = env.handle.context
        
        if not page:
            return {"success": False, "error": f"Environment not connected: {env_id}"}
        
        # 4. 动态导入工作流类
        try:
            # entry_class 格式: "workflows.labor_workflow:StandardLaborWorkflow"
            entry = workflow_info.entry_class
            if ":" in entry:
                module_path, class_name = entry.split(":", 1)
            else:
                # 默认格式: 假设类名与工作流名一致
                module_path = entry
                class_name = task.title().replace("_", "")
            
            # 构造完整模块路径
            full_module_path = f"modules.{module}.{module_path}"
            mod = importlib.import_module(full_module_path)
            workflow_class = getattr(mod, class_name)
        except (ImportError, AttributeError) as e:
            return {"success": False, "error": f"Failed to import workflow: {e}"}
        
        # 5. 构造 TaskContext
        ctx = TaskContext(
            env_id=int(env_id),
            task_name=task,
            config=params,
            page=page,
            context=context,
        )
        
        # 6. 执行工作流
        try:
            workflow_instance = workflow_class()
            await workflow_instance.run(ctx)
            logger.info(f"[TSM Adapter] Workflow {module}::{task} completed")
            return {"success": True, "message": f"Executed {module}::{task}"}
        except Exception as e:
            logger.error(f"[TSM Adapter] Workflow execution failed: {e}")
            return {"success": False, "error": str(e)}


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

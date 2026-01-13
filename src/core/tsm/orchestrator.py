"""策略编排器 (V2)。

规格参考: docs/srs/05-framework-core/05-3-task-strategy-management.md (5.3.4)

StrategyOrchestrator 是 TSM 的智能决策引擎，负责:
    1. Resource Selection: 应用标签匹配和排序规则选择环境
    2. Elastic Scaling: 资源不足时自动创建并初始化
    3. Execution & Retry: 执行任务并处理重试
    4. Teardown Policy: 智能清理 (Recycle/Destroy/KeepAlive)
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.core.foundation.logging import logger
from src.core.tsm.models import (
    InstanceResult,
    OrchestratorResult,
    ScalingMode,
    TaskStrategy,
    TeardownAction,
)

# =============================================================================
# 依赖接口 (Protocol) - 模拟 REM/MMS
# =============================================================================

class IEnvironmentManager(Protocol):
    """资源环境管理器 (REM) 接口。"""

    async def find(
        self,
        env_type: str,
        labels: dict,
        expressions: list[str],
        sort_by: str,
    ) -> list[str]:  # 返回 env_ids
        ...

    async def lease(self, env_id: str, task_id: str) -> str:  # 返回 lease_id
        ...

    async def release(self, lease_id: str) -> None:
        ...

    async def provision(self, env_type: str) -> str:  # 返回 env_id
        ...
    
    async def destroy(self, env_id: str) -> None:
        ...

    async def count_active(self) -> int:
        ...


class IModuleExecutor(Protocol):
    """模块执行接口 (MMS)。"""

    async def execute(
        self,
        module: str,
        task: str,
        env_id: str,
        params: dict,
    ) -> dict[str, Any]:
        ...


# =============================================================================
# 日志事件
# =============================================================================

@dataclass
class LogEntry:
    env_id: str
    level: str
    message: str
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))

LogCallback = Any  # Callable[[LogEntry], None]


# =============================================================================
# 编排器
# =============================================================================

class StrategyOrchestrator:
    """TSM V2 智能编排器。"""

    def __init__(
        self,
        env_manager: IEnvironmentManager | None = None,
        module_executor: IModuleExecutor | None = None,
    ):
        self._rem = env_manager
        self._mms = module_executor
        self._cancel_event: asyncio.Event | None = None

    def configure(self, env_manager: IEnvironmentManager, module_executor: IModuleExecutor):
        self._rem = env_manager
        self._mms = module_executor

    async def execute(
        self,
        strategy: TaskStrategy,
        log_callback: LogCallback | None = None,
    ) -> OrchestratorResult:
        """执行策略编排。
        
        目前简化为单实例执行 (针对 Task V2 逻辑)。
        未来可扩展为多实例并发 (Orchestrator 调度多个 Worker)。
        """
        if not self._rem or not self._mms:
            raise RuntimeError("Orchestrator 依赖未注入")

        self._cancel_event = asyncio.Event()
        started_at = int(time.time())
        
        # 为了兼容 V1 接口，这里只跑一个实例用于验证 V2 逻辑
        # 实际生产应循环 strategy.concurrency 或 scaling 配置
        
        instance_result = await self._run_logic_v2(strategy, "task-001", log_callback)
        
        ended_at = int(time.time())
        return OrchestratorResult(
            strategy_id=strategy.id,
            success=instance_result.success,
            total_instances=1,
            succeeded_instances=1 if instance_result.success else 0,
            failed_instances=0 if instance_result.success else 1,
            results=[instance_result],
            started_at=started_at,
            ended_at=ended_at,
        )

    async def cancel(self):
        if self._cancel_event:
            self._cancel_event.set()

    # --- V2 Core Logic ---

    async def _run_logic_v2(
        self,
        strategy: TaskStrategy,
        task_id: str,
        cb: LogCallback | None,
    ) -> InstanceResult:
        """执行 V2 核心逻辑流: Find -> Scale -> Exec -> Retry -> Teardown"""
        
        env_id = ""
        lease_id = ""
        started_at = int(time.time())
        last_error = None
        
        attempt = 0
        max_attempts = strategy.retry.max_attempts

        while attempt < max_attempts:
            attempt += 1
            self._log(cb, "SYSTEM", "INFO", f"开始尝试 #{attempt} ...")
            
            try:
                # 1. 资源获取 (包含 Selection & Scaling)
                env_id, lease_id = await self._acquire_resource(strategy, task_id, cb)
                self._log(cb, env_id, "INFO", f"资源就绪: {env_id}")
                
                # 2. 目标执行
                if strategy.execution:
                    self._log(cb, env_id, "INFO", f"执行任务: {strategy.execution.workflow}")
                    
                    # 带有超时控制
                    result = await asyncio.wait_for(
                        self._mms.execute(
                            strategy.execution.module,
                            strategy.execution.workflow,
                            env_id,
                            strategy.execution.params
                        ),
                        timeout=strategy.execution.timeout
                    )
                    
                    # 3. 成功清理
                    await self._handle_teardown(
                        strategy.teardown.on_success, env_id, lease_id, cb
                    )
                    
                    return InstanceResult(
                        env_id=env_id,
                        success=True,
                        message="执行成功",
                        started_at=started_at,
                        ended_at=int(time.time())
                    )

            except Exception as e:
                last_error = e
                self._log(cb, env_id or "SYSTEM", "WARN", f"尝试 #{attempt} 失败: {e}")
                
                # 4. 失败清理
                # 如果要重试且换环境，先这里清理。或者最后统一清理。
                # 策略: 失败时往往需要清理当前环境 lease
                if env_id and lease_id:
                     action = strategy.teardown.on_failure
                     # 如果还要重试，强制 Recycle 释放租约，除非 KeepAlive
                     if attempt < max_attempts and action == TeardownAction.KEEP_ALIVE:
                         pass # 保留用于下次重试? 通常重试要新环境
                     else:
                         await self._handle_teardown(action, env_id, lease_id, cb)
                         env_id = ""
                         lease_id = ""

                # 检查是否可重试
                # TODO: 检查 retry_on_condition
                if attempt >= max_attempts:
                    break
                
                # 等待重试间隔
                await asyncio.sleep(2)

        return InstanceResult(
            env_id=env_id or "None",
            success=False,
            error=str(last_error),
            started_at=started_at,
            ended_at=int(time.time())
        )

    async def _acquire_resource(
        self,
        strategy: TaskStrategy,
        task_id: str,
        cb: LogCallback | None
    ) -> tuple[str, str]:
        """获取资源: 查找 -> 伸缩 -> 初始化 -> 租用"""
        
        # 1. Find Candidates
        candidates = await self._rem.find(
            strategy.selector.env_type.value,
            strategy.selector.match_labels,
            strategy.selector.match_expressions,
            strategy.selector.sort_strategy.value
        )
        
        target_env_id = None
        
        if candidates:
            target_env_id = candidates[0] # 已排序
            self._log(cb, "SYSTEM", "DEBUG", f"选中现有环境: {target_env_id}")
        else:
            # 2. Handle Scaling
            if strategy.scaling.mode == ScalingMode.ELASTIC:
                active_count = await self._rem.count_active()
                if active_count < strategy.scaling.max_concurrency:
                    # Provision
                    self._log(cb, "SYSTEM", "INFO", "触发弹性伸缩: 创建新环境...")
                    target_env_id = await self._rem.provision(strategy.selector.env_type.value)
                    
                    # Init Workflow
                    if strategy.scaling.init_workflow:
                        self._log(cb, target_env_id, "INFO", "执行初始化工作流...")
                        await self._mms.execute(
                            "ctrip", # TODO: 从 init_workflow 解析 module
                            strategy.scaling.init_workflow, # 假设是 workflow 名
                            target_env_id,
                            {}
                        )
                else:
                    raise RuntimeError("资源配额已满，无法扩容")
            else:
                # Proper wait logic needed here
                raise RuntimeError("无可用资源 (Strict Mode)")
        
        # 3. Lease
        lease_id = await self._rem.lease(target_env_id, task_id)
        return target_env_id, lease_id

    async def _handle_teardown(
        self,
        action: TeardownAction,
        env_id: str,
        lease_id: str,
        cb: LogCallback | None
    ):
        """执行清理策略"""
        self._log(cb, env_id, "INFO", f"执行清理策略: {action.value}")
        
        try:
            if action == TeardownAction.DESTROY:
                await self._rem.release(lease_id)
                await self._rem.destroy(env_id)
            elif action == TeardownAction.RECYCLE:
                # 可以在此执行清理脚本 (clear cookies)
                await self._rem.release(lease_id)
            elif action == TeardownAction.HIBERNATE:
                await self._rem.release(lease_id)
                # await self._rem.hibernate(env_id)
            elif action == TeardownAction.KEEP_ALIVE:
                # 不释放租约? 或者释放但标记保留?
                # 简单起见，释放租约以便其他人看不见它，或者仅仅 Log
                await self._rem.release(lease_id)
        except Exception as e:
            self._log(cb, env_id, "WARN", f"清理失败: {e}")

    def _log(self, cb, env, level, msg):
        full_msg = f"[V2] {msg}"
        if level == "INFO": logger.info(full_msg)
        elif level == "WARN": logger.warning(full_msg)
        elif level == "ERROR": logger.error(full_msg)
        
        if cb:
            cb(LogEntry(env_id=env, level=level, message=msg))


# 单例相关
_orchestrator: StrategyOrchestrator | None = None

def get_orchestrator() -> StrategyOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = StrategyOrchestrator()
    return _orchestrator

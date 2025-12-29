"""任务运行器模块。

封装调度器使用的环境执行包装器，负责：
1. 锁定劳保账号
2. 调用统一工作函数
3. 更新统计并释放锁
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

from src.core.events import EventType, get_event_bus
from src.core.workflow_executor import (
    WorkflowResult,
    WorkflowResultType,
    execute_environment_workflow,
)
from src.utils.logger import logger
from src.utils.storage import (
    EnvironmentRepository,
    LaborAccountRepository,
)

if TYPE_CHECKING:
    from src.core.models.environment import Environment


class TaskResultType(Enum):
    """任务执行结果类型。"""
    SUCCESS = auto()
    FAILED = auto()
    NO_TASK = auto()
    BLACKLISTED = auto()
    ERROR = auto()


@dataclass
class TaskResult:
    """任务执行结果。"""
    result_type: TaskResultType
    tasks_completed: int = 0
    message: str = ""
    ctrip_blacklisted: bool = False


class TaskRunner:
    """调度器的任务执行包装器。
    
    职责:
    1. 锁定劳保账号（确保互斥）
    2. 调用统一工作函数
    3. 更新统计并释放锁
    """
    
    def __init__(self, environment: "Environment"):
        """初始化任务运行器。
        
        Args:
            environment: 目标环境
        """
        self.env = environment
        self.env_repo = EnvironmentRepository()
        self.labor_repo = LaborAccountRepository()
        self.bus = get_event_bus()
        
        self._cancelled = False
    
    def cancel(self):
        """请求取消任务。"""
        self._cancelled = True
    
    async def run(self) -> TaskResult:
        """执行完整的任务生命周期。
        
        Returns:
            TaskResult 包含执行结果
        """
        env_id = self.env.id
        labor_id = self.env.labor_account_id
        
        if not env_id:
            return TaskResult(
                result_type=TaskResultType.ERROR,
                message="环境 ID 无效"
            )
        
        logger.info(f"🚀 TaskRunner 启动: ENV-{env_id}")
        
        try:
            # 1. 尝试锁定劳保账号
            if labor_id and not self.labor_repo.lock_account(labor_id, env_id):
                logger.warning(f"劳保账号 ID-{labor_id} 已被其他环境占用")
                return TaskResult(
                    result_type=TaskResultType.ERROR,
                    message=f"劳保账号 ID-{labor_id} 已被其他环境占用"
                )
            
            if labor_id:
                logger.info(f"🔒 已锁定劳保账号: ID-{labor_id}")
            
            # 2. 更新环境状态
            self.env_repo.update_status(env_id, "running")
            
            # 3. 调用统一工作函数（无 input_callback = 自动模式）
            workflow_result = await execute_environment_workflow(
                environment=self.env,
                input_callback=None,  # 自动模式
            )
            
            # 4. 转换结果类型
            result = self._convert_result(workflow_result)
            
            # 5. 更新统计
            if workflow_result.tasks_completed > 0 and labor_id:
                self.labor_repo.update_stats(labor_id, completed=workflow_result.tasks_completed)
                self.bus.emit(EventType.LABOR_STATS_UPDATED, {
                    "id": labor_id,
                    "completed": workflow_result.tasks_completed
                })
            
            return result
            
        except Exception as e:
            logger.error(f"ENV-{env_id} 任务执行异常: {e}")
            return TaskResult(
                result_type=TaskResultType.ERROR,
                message=str(e)
            )
        finally:
            # 6. 释放锁定
            if labor_id and env_id:
                self.labor_repo.unlock_account(labor_id, env_id)
                logger.info(f"🔓 已释放劳保账号: ID-{labor_id}")
            
            # 7. 更新环境状态
            if env_id:
                self.env_repo.update_status(env_id, "idle")
    
    def _convert_result(self, workflow_result: WorkflowResult) -> TaskResult:
        """将 WorkflowResult 转换为 TaskResult。"""
        type_mapping = {
            WorkflowResultType.SUCCESS: TaskResultType.SUCCESS,
            WorkflowResultType.NO_TASK: TaskResultType.NO_TASK,
            WorkflowResultType.CTRIP_LOGIN_FAILED: TaskResultType.FAILED,
            WorkflowResultType.LABOR_LOGIN_FAILED: TaskResultType.FAILED,
            WorkflowResultType.TASK_FAILED: TaskResultType.FAILED,
            WorkflowResultType.MANUAL_SMS_AUTO_MODE: TaskResultType.FAILED,
            WorkflowResultType.ACCOUNT_ERROR: TaskResultType.ERROR,
            WorkflowResultType.BROWSER_ERROR: TaskResultType.ERROR,
            WorkflowResultType.ERROR: TaskResultType.ERROR,
        }
        
        return TaskResult(
            result_type=type_mapping.get(workflow_result.result_type, TaskResultType.ERROR),
            tasks_completed=workflow_result.tasks_completed,
            message=workflow_result.message,
            ctrip_blacklisted=workflow_result.ctrip_blacklisted,
        )

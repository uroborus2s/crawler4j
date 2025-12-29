"""任务运行器模块。

封装调度器使用的环境执行包装器，负责：
1. 调用统一工作函数
2. 更新环境状态

注意：劳保账号的锁定/释放已移至 workflow_executor 内部处理。
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
from src.utils.storage import EnvironmentRepository

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
    1. 调用统一工作函数
    2. 更新环境状态
    3. 发送统计事件
    
    注意：劳保账号的锁定/释放在 workflow_executor 内部处理。
    """
    
    def __init__(self, environment: "Environment"):
        """初始化任务运行器。
        
        Args:
            environment: 目标环境
        """
        self.env = environment
        self.env_repo = EnvironmentRepository()
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
        
        if not env_id:
            return TaskResult(
                result_type=TaskResultType.ERROR,
                message="环境 ID 无效"
            )
        
        logger.info(f"🚀 TaskRunner 启动: ENV-{env_id}")
        
        try:
            # 1. 更新环境状态
            self.env_repo.update_status(env_id, "running")
            
            # 2. 调用统一工作函数（劳保账号锁定/释放在内部处理）
            workflow_result = await execute_environment_workflow(
                environment=self.env,
                input_callback=None,  # 自动模式
            )
            
            # 3. 转换结果类型
            result = self._convert_result(workflow_result)
            
            # 4. 发送统计事件
            if workflow_result.tasks_completed > 0 and workflow_result.labor_account_id:
                self.bus.emit(EventType.LABOR_STATS_UPDATED, {
                    "id": workflow_result.labor_account_id,
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
            # 5. 更新环境状态
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
            WorkflowResultType.NO_LABOR_ACCOUNT: TaskResultType.ERROR,
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

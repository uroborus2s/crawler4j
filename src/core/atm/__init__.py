"""自动化任务管理 (Automation Task Management)。

规格参考: docs/srs/05-framework-core/05-4-automation-task-management.md

导出:
    - TaskInstance, TaskRequest, TaskResult: 数据模型
    - TaskStatus: 状态枚举
    - TaskRepository: 任务仓库
    - TaskRunner: 任务执行器
    - TaskService: 任务服务
"""

from src.core.atm.models import (
    TaskError,
    TaskExecutionError,
    TaskInstance,
    TaskNotFoundError,
    TaskRequest,
    TaskResult,
    TaskStatus,
)
from src.core.atm.repository import (
    TaskRepository,
    get_task_repository,
)
from src.core.atm.runner import (
    TaskRunner,
    get_task_runner,
)
from src.core.atm.service import (
    TaskService,
    get_task_service,
)

__all__ = [
    # 数据模型
    "TaskInstance",
    "TaskRequest",
    "TaskResult",
    "TaskStatus",
    # 错误
    "TaskError",
    "TaskNotFoundError",
    "TaskExecutionError",
    # 仓库
    "TaskRepository",
    "get_task_repository",
    # 执行器
    "TaskRunner",
    "get_task_runner",
    # 服务
    "TaskService",
    "get_task_service",
]

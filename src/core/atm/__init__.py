"""自动化任务管理 (Automation Task Management)。

规格参考: docs/srs/05-framework-core/05-4-automation-task-management.md

导出:
    - AutomationTask, TaskRun, TaskResult: 数据模型
    - TaskStatus: 状态枚举
    - TaskRepository: 任务仓库
    - TaskService: 任务服务
"""

from src.core.atm.models import (
    AutomationTask,
    TaskNotFoundError,
    TaskResult,
    TaskRun,
    TaskStatus,
)
from src.core.atm.repository import (
    TaskRepository,
    get_task_repository,
)
from src.core.atm.service import (
    TaskService,
    get_task_service,
)

__all__ = [
    # 数据模型
    "AutomationTask",
    "TaskRun",
    "TaskResult",
    "TaskStatus",
    # 错误
    "TaskNotFoundError",
    # 仓库
    "TaskRepository",
    "get_task_repository",
    # 服务
    "TaskService",
    "get_task_service",
]

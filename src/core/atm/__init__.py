"""自动化任务管理 (Automation Task Management) V2.

规格参考: docs/design/task-engine-v2.md

导出:
    - Job, Task: 核心实体
    - JobState, TaskStatus: 状态枚举
    - job_controller: 作业控制器
    - task_service: 任务服务
"""

from src.core.atm.controller import (
    JobController,
    get_job_controller,
)
from src.core.atm.dispatcher import (
    TaskDispatcher,
    get_task_dispatcher,
)
from src.core.atm.models import (
    Job,
    JobState,
    JobType,
    Task,
    TaskStatus,
    TriggerConfig,
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
    # Models
    "Job",
    "JobState",
    "JobType",
    "Task",
    "TaskStatus",
    "TriggerConfig",
    
    # Repository
    "TaskRepository",
    "get_task_repository",
    
    # Service
    "TaskService",
    "get_task_service",
    
    # Internals (exposed for testing/admin)
    "JobController",
    "get_job_controller",
    "TaskDispatcher",
    "get_task_dispatcher",
]


from contextvars import ContextVar

# 存储当前运行的 Task ID
# 用于日志系统自动关联上下文，无需手动传参
current_task_id: ContextVar[str | None] = ContextVar("current_task_id", default=None)

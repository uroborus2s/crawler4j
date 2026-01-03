"""TaskResult - 任务执行结果。"""

from dataclasses import dataclass, field


@dataclass
class TaskResult:
    """任务执行结果
    
    Attributes:
        success: 是否成功
        tasks_completed: 完成的任务数量
        message: 结果消息
        data: 附加数据
        error: 错误信息（如有）
    """
    
    success: bool = False
    tasks_completed: int = 0
    message: str = ""
    data: dict = field(default_factory=dict)
    error: str | None = None
    
    @classmethod
    def ok(cls, tasks_completed: int = 1, message: str = "成功", **data) -> "TaskResult":
        """创建成功结果"""
        return cls(
            success=True,
            tasks_completed=tasks_completed,
            message=message,
            data=data,
        )
    
    @classmethod
    def fail(cls, message: str, error: str | None = None) -> "TaskResult":
        """创建失败结果"""
        return cls(
            success=False,
            message=message,
            error=error,
        )

"""旧数据模型命名空间兼容导出。"""

from .ctrip_account import CtripAccount
from .labor_account import LaborAccount
from .labor_task import LaborTask, TaskState

__all__ = ["CtripAccount", "LaborAccount", "LaborTask", "TaskState"]


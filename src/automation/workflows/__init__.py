"""旧工作流命名空间兼容导出。"""

from .base import BaseWorkflow
from .ctrip_search import CtripSearchWorkflow
from .labor_claim_task import LaborClaimTaskWorkflow
from .labor_login import LaborLoginWorkflow
from .labor_submit import LaborSubmitWorkflow

__all__ = [
    "BaseWorkflow",
    "CtripSearchWorkflow",
    "LaborClaimTaskWorkflow",
    "LaborLoginWorkflow",
    "LaborSubmitWorkflow",
]


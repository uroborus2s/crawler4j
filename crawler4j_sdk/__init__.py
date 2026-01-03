"""Crawler4j SDK - 任务脚本开发工具包

提供TaskScript基类和相关类型，供外部脚本项目使用。
"""

from crawler4j_sdk.base import TaskScript
from crawler4j_sdk.context import TaskContext
from crawler4j_sdk.db import DataService
from crawler4j_sdk.result import TaskResult
from crawler4j_sdk.workflow import TaskFlow

__version__ = "1.0.0"
__all__ = ["TaskScript", "TaskContext", "TaskResult", "DataService", "TaskFlow"]


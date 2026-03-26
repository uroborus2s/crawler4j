"""Crawler4j Contracts - Core <-> SDK 共享契约包。

本包只承载稳定契约类型，不包含运行时实现。
"""

from crawler4j_contracts.context import (
    DatabaseCapability,
    DefaultHttpClient,
    EnvOpsCapability,
    HttpClient,
    IPPoolCapability,
    TaskContext,
    UICapability,
)
from crawler4j_contracts.result import TaskResult

__version__ = "1.0.1"

__all__ = [
    "TaskContext",
    "TaskResult",
    "HttpClient",
    "DefaultHttpClient",
    "DatabaseCapability",
    "IPPoolCapability",
    "EnvOpsCapability",
    "UICapability",
]

"""日志系统 (Logging System)。

统一日志门面，负责日志的分级、输出与信号集成：
- 与 Python logging 模块集成
- 提供 Qt 信号用于 UI 实时显示
- 支持日志持久化回调
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from src.core.foundation.context import current_task_id
from src.core.foundation.event_bus import Event, EventType, get_event_bus


class LogLevel(str, Enum):
    """日志级别枚举。"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogEntry:
    """日志条目。"""

    def __init__(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        environment_id: int | None = None,
        task_id: str | None = None,
        timestamp: datetime | None = None,
    ):
        self.message = message
        self.level = level
        self.environment_id = environment_id
        self.task_id = task_id
        self.timestamp = timestamp or datetime.now()

    def __str__(self) -> str:
        """格式化日志条目用于显示。"""
        time_str = self.timestamp.strftime("%H:%M:%S")
        env_str = f"ENV-{self.environment_id}" if self.environment_id else "SYSTEM"
        task_str = f" [Task:{self.task_id[:8]}]" if self.task_id else ""
        return f"{time_str} [{self.level.value}] {env_str}{task_str}: {self.message}"

    def to_dict(self) -> dict:
        """转换为字典用于存储。"""
        return {
            "message": self.message,
            "level": self.level.value,
            "environment_id": self.environment_id,
            "task_id": self.task_id,
            "created_at": self.timestamp.isoformat(),
        }


class LogSignals(QObject):
    """日志事件的 Qt 信号。"""

    log_added = pyqtSignal(object)  # LogEntry


class AppLogger:
    """应用日志器，支持 Qt 信号。

    Usage:
        logger = AppLogger()
        logger.signals.log_added.connect(ui_handler)
        logger.info("Task started", environment_id=1)
    """

    _instance: "AppLogger | None" = None

    def __new__(cls):
        """单例模式。"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.signals = LogSignals()
        self._entries: list[LogEntry] = []
        self._max_entries = 1000
        self._storage_callback: Callable[[LogEntry], None] | None = None

        # 设置 Python logging
        self._setup_python_logging()
        self._initialized = True

    def _setup_python_logging(self):
        """设置 Python logging 模块。"""
        self._python_logger = logging.getLogger("crawler4j")
        self._python_logger.setLevel(logging.DEBUG)

        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        self._python_logger.addHandler(handler)

    def set_storage_callback(self, callback: Callable[[LogEntry], None]):
        """设置日志持久化回调。"""
        self._storage_callback = callback

    def _log(
        self,
        message: str,
        level: LogLevel,
        environment_id: int | None = None,
    ):
        """内部日志方法。"""
        # 自动获取当前 Task Context
        task_id = current_task_id.get()
        
        entry = LogEntry(message, level, environment_id, task_id=task_id)

        # 内存存储
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]

        # 发送 Qt 信号
        self.signals.log_added.emit(entry)

        # 发送 EventBus 事件 (如果不死循环)
        # 注意: EventBus 内部如有日志，可能会死循环。需确保 EventBus 不在发布时打大量日志。
        if task_id:
             try:
                 bus = get_event_bus()
                 bus.publish(Event(
                     type=EventType.TASK_LOG,
                     data=entry.to_dict(),
                     task_run_id=task_id
                 ))
             except Exception:
                 pass

        # Python logging
        log_func = getattr(self._python_logger, level.value.lower())
        log_func(str(entry))

        # 持久化回调
        if self._storage_callback:
            try:
                self._storage_callback(entry)
            except Exception as e:
                self._python_logger.error(f"Failed to persist log: {e}")

    def debug(self, message: str, environment_id: int | None = None):
        """记录 DEBUG 级别日志。"""
        self._log(message, LogLevel.DEBUG, environment_id)

    def info(self, message: str, environment_id: int | None = None):
        """记录 INFO 级别日志。"""
        self._log(message, LogLevel.INFO, environment_id)

    def warning(self, message: str, environment_id: int | None = None):
        """记录 WARNING 级别日志。"""
        self._log(message, LogLevel.WARNING, environment_id)

    def error(self, message: str, environment_id: int | None = None):
        """记录 ERROR 级别日志。"""
        self._log(message, LogLevel.ERROR, environment_id)

    def get_entries(
        self,
        limit: int = 100,
        level: LogLevel | None = None,
    ) -> list[LogEntry]:
        """获取最近的日志条目。

        Args:
            limit: 最大返回条目数。
            level: 按级别过滤。

        Returns:
            日志条目列表，最新的在前。
        """
        entries = self._entries[-limit:]
        if level:
            entries = [e for e in entries if e.level == level]
        return list(reversed(entries))


# 全局日志器实例
logger = AppLogger()


def setup_file_logging(
    log_dir: str | None = None,
    level: str = "INFO",
    retention_days: int = 14
):
    """设置文件日志记录。
    
    Args:
        log_dir: 日志目录路径。如果不提供，则不开启文件日志。
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR).
        retention_days: 日志保留天数.
    """
    if not log_dir:
        return

    from logging.handlers import TimedRotatingFileHandler
    from pathlib import Path

    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    log_file = log_path / "crawler4j.log"
    
    # 按天滚动，保留 retention_days 天
    handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=retention_days,
        encoding="utf-8"
    )
    
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    
    # 设置级别
    log_level = getattr(logging, level.upper(), logging.INFO)
    handler.setLevel(log_level)
    
    # 同时调整 logger 自身的级别，确保 handler 能接收到
    logger._python_logger.setLevel(min(logger._python_logger.level, log_level))
    
    # Add to python logger
    logger._python_logger.addHandler(handler)
    logger.info(f"File logging initialized: {log_file} (Level={level}, Retention={retention_days} days)")


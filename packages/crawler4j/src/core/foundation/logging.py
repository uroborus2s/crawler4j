"""日志系统 (Logging System)。

统一日志门面，负责日志的分级、输出与信号集成：
- 统一承接 AppLogger 与标准库 logging
- 提供 Qt 信号用于 UI 实时显示
- 支持文件日志与热更新
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal

from crawler4j_contracts.context import set_default_task_logger_factory
from src.core.foundation.context import current_task_id
from src.core.foundation.event_bus import Event, EventType, get_event_bus


class LogLevel(str):
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
        level: str = LogLevel.INFO,
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
        return f"{time_str} [{self.level}] {env_str}{task_str}: {self.message}"

    def to_dict(self) -> dict:
        """转换为字典用于存储。"""
        return {
            "message": self.message,
            "level": self.level,
            "environment_id": self.environment_id,
            "task_id": self.task_id,
            "created_at": self.timestamp.isoformat(),
        }


class LogSignals(QObject):
    """日志事件的 Qt 信号。"""

    log_added = pyqtSignal(object)  # LogEntry


def _normalize_log_level(level: str | int) -> int:
    if isinstance(level, int):
        return level
    return getattr(logging, str(level).upper(), logging.INFO)


def _level_name(level_no: int) -> str:
    if level_no >= logging.ERROR:
        return LogLevel.ERROR
    if level_no >= logging.WARNING:
        return LogLevel.WARNING
    if level_no >= logging.INFO:
        return LogLevel.INFO
    return LogLevel.DEBUG


_LOGGER_MIN_LEVEL_FLOORS: dict[str, int] = {
    "apscheduler": logging.WARNING,
}


class _AppLogHandler(logging.Handler):
    """把标准 logging 记录转成统一 LogEntry。"""

    def __init__(self, owner: "AppLogger"):
        super().__init__(level=logging.INFO)
        self._owner = owner
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        self._owner._consume_record(record)


class AppLogger:
    """应用日志服务。

    统一管理：
    - 内存日志缓存 / UI 信号
    - root logging handlers
    - 文件日志热更新
    """

    _instance: "AppLogger | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._signals: LogSignals | None = None
        self._entries: list[LogEntry] = []
        self._max_entries = 1000
        self._storage_callback: Callable[[LogEntry], None] | None = None

        self._root_logger = logging.getLogger()
        self._bridge_logger = logging.getLogger("crawler4j")
        self._app_handler = _AppLogHandler(self)
        self._console_handler = logging.StreamHandler()
        self._console_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        self._file_handler: logging.Handler | None = None
        self._log_dir: Path | None = None
        self._retention_days = 14
        self._level = logging.INFO

        self._bridge_logger.propagate = True
        self._bridge_logger.handlers.clear()

        self._install_base_handlers()
        self._apply_level(self._level)
        self._initialized = True

    @property
    def level(self) -> int:
        return self._level

    @property
    def signals(self) -> LogSignals:
        if self._signals is None:
            self._signals = LogSignals()
        return self._signals

    def _install_base_handlers(self) -> None:
        if self._app_handler not in self._root_logger.handlers:
            self._root_logger.addHandler(self._app_handler)
        if self._console_handler not in self._root_logger.handlers:
            self._root_logger.addHandler(self._console_handler)

    def _apply_level(self, level_no: int) -> None:
        self._level = level_no
        self._root_logger.setLevel(level_no)
        self._app_handler.setLevel(level_no)
        self._console_handler.setLevel(level_no)
        if self._file_handler is not None:
            self._file_handler.setLevel(level_no)
        self._apply_logger_min_level_floors()

    def _apply_logger_min_level_floors(self) -> None:
        for logger_name, minimum_level in _LOGGER_MIN_LEVEL_FLOORS.items():
            logging.getLogger(logger_name).setLevel(max(self._level, minimum_level))

    def _replace_file_handler(self, log_dir: str | Path | None, retention_days: int) -> None:
        if self._file_handler is not None:
            self._root_logger.removeHandler(self._file_handler)
            self._file_handler.close()
            self._file_handler = None

        if not log_dir:
            self._log_dir = None
            self._retention_days = retention_days
            return

        from logging.handlers import TimedRotatingFileHandler

        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._retention_days = retention_days

        handler = TimedRotatingFileHandler(
            self._log_dir / "crawler4j.log",
            when="midnight",
            interval=1,
            backupCount=retention_days,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        handler.setLevel(self._level)
        self._root_logger.addHandler(handler)
        self._file_handler = handler

    def configure(
        self,
        *,
        log_dir: str | Path | None = None,
        level: str | int = "INFO",
        retention_days: int = 14,
    ) -> None:
        """配置唯一日志服务。"""
        self._install_base_handlers()
        self._apply_level(_normalize_log_level(level))
        self._replace_file_handler(log_dir, retention_days)

    def set_storage_callback(self, callback: Callable[[LogEntry], None]) -> None:
        """设置日志持久化回调。"""
        self._storage_callback = callback

    def _consume_record(self, record: logging.LogRecord) -> None:
        formatter = self._app_handler.formatter or logging.Formatter("%(message)s")
        message = formatter.format(record)
        task_id = getattr(record, "task_id", None) or current_task_id.get()
        entry = LogEntry(
            message=message,
            level=_level_name(record.levelno),
            environment_id=getattr(record, "environment_id", None),
            task_id=task_id,
            timestamp=datetime.fromtimestamp(record.created),
        )

        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]

        if self._signals is not None:
            self._signals.log_added.emit(entry)

        if task_id:
            try:
                bus = get_event_bus()
                bus.publish(
                    Event(
                        type=EventType.TASK_LOG,
                        data=entry.to_dict(),
                        task_run_id=task_id,
                    )
                )
            except Exception:
                pass

        if self._storage_callback:
            try:
                self._storage_callback(entry)
            except Exception:
                pass

    def _log(self, level: int, message: str, environment_id: int | None = None, *, exc_info=None) -> None:
        extra = {"environment_id": environment_id}
        task_id = current_task_id.get()
        if task_id:
            extra["task_id"] = task_id
        self._bridge_logger.log(level, message, extra=extra, exc_info=exc_info)

    def debug(self, message: str, environment_id: int | None = None) -> None:
        self._log(logging.DEBUG, message, environment_id)

    def info(self, message: str, environment_id: int | None = None) -> None:
        self._log(logging.INFO, message, environment_id)

    def warning(self, message: str, environment_id: int | None = None) -> None:
        self._log(logging.WARNING, message, environment_id)

    def error(self, message: str, environment_id: int | None = None) -> None:
        self._log(logging.ERROR, message, environment_id)

    def exception(self, message: str, environment_id: int | None = None) -> None:
        self._log(logging.ERROR, message, environment_id, exc_info=True)

    def get_entries(self, limit: int = 100, level: str | None = None) -> list[LogEntry]:
        """获取最近的日志条目。"""
        entries = self._entries[-limit:]
        if level:
            entries = [entry for entry in entries if entry.level == level]
        return list(reversed(entries))


logger = AppLogger()
set_default_task_logger_factory(lambda: logger)


def setup_file_logging(
    log_dir: str | None = None,
    level: str = "INFO",
    retention_days: int = 14,
) -> None:
    """兼容旧调用入口，实质转发到唯一日志服务。"""
    logger.configure(log_dir=log_dir, level=level, retention_days=retention_days)

"""Logger module.

Provides timestamped logging with Qt signal integration.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Callable

from PyQt6.QtCore import QObject, pyqtSignal


class LogLevel(str, Enum):
    """Log level enumeration."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogEntry:
    """Represents a single log entry."""

    def __init__(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        environment_id: int | None = None,
        timestamp: datetime | None = None,
    ):
        self.message = message
        self.level = level
        self.environment_id = environment_id
        self.timestamp = timestamp or datetime.now()

    def __str__(self) -> str:
        """Format log entry for display."""
        time_str = self.timestamp.strftime("%H:%M:%S")
        env_str = f"ENV-{self.environment_id}" if self.environment_id else "SYSTEM"
        return f"{time_str} [{self.level.value}] {env_str}: {self.message}"

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "message": self.message,
            "level": self.level.value,
            "environment_id": self.environment_id,
            "created_at": self.timestamp.isoformat(),
        }


class LogSignals(QObject):
    """Qt signals for log events."""

    log_added = pyqtSignal(object)  # LogEntry


class AppLogger:
    """Application logger with Qt signal support.

    Usage:
        logger = AppLogger()
        logger.signals.log_added.connect(ui_handler)
        logger.info("Task started", environment_id=1)
    """

    _instance: "AppLogger | None" = None

    def __new__(cls):
        """Singleton pattern."""
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

        # Also setup Python logging
        self._setup_python_logging()
        self._initialized = True

    def _setup_python_logging(self):
        """Setup Python logging module."""
        self._python_logger = logging.getLogger("crawler4j")
        self._python_logger.setLevel(logging.DEBUG)

        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        self._python_logger.addHandler(handler)

    def set_storage_callback(self, callback: Callable[[LogEntry], None]):
        """Set callback for persisting logs to database."""
        self._storage_callback = callback

    def _log(
        self,
        message: str,
        level: LogLevel,
        environment_id: int | None = None,
    ):
        """Internal log method."""
        entry = LogEntry(message, level, environment_id)

        # Store in memory
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]

        # Emit Qt signal
        self.signals.log_added.emit(entry)

        # Python logging
        log_func = getattr(self._python_logger, level.value.lower())
        log_func(str(entry))

        # Persist to database if callback set
        if self._storage_callback:
            try:
                self._storage_callback(entry)
            except Exception as e:
                self._python_logger.error(f"Failed to persist log: {e}")

    def debug(self, message: str, environment_id: int | None = None):
        """Log debug message."""
        self._log(message, LogLevel.DEBUG, environment_id)

    def info(self, message: str, environment_id: int | None = None):
        """Log info message."""
        self._log(message, LogLevel.INFO, environment_id)

    def warning(self, message: str, environment_id: int | None = None):
        """Log warning message."""
        self._log(message, LogLevel.WARNING, environment_id)

    def error(self, message: str, environment_id: int | None = None):
        """Log error message."""
        self._log(message, LogLevel.ERROR, environment_id)

    def get_entries(
        self,
        limit: int = 100,
        level: LogLevel | None = None,
    ) -> list[LogEntry]:
        """Get recent log entries.

        Args:
            limit: Maximum number of entries to return.
            level: Filter by log level.

        Returns:
            List of log entries, newest first.
        """
        entries = self._entries[-limit:]
        if level:
            entries = [e for e in entries if e.level == level]
        return list(reversed(entries))


# Global logger instance
logger = AppLogger()

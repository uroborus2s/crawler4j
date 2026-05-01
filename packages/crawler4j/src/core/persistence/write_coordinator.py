"""SQLite write coordination for host-owned database mutations."""

from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import ExitStack
from typing import Any, Callable, TypeVar

from src.core.persistence.database import get_connection

T = TypeVar("T")


class DatabaseWriteTimeoutError(RuntimeError):
    """Raised when the host cannot obtain a SQLite write lock in time."""


def _is_sqlite_busy_error(exc: BaseException) -> bool:
    if not isinstance(exc, sqlite3.OperationalError):
        return False
    message = str(exc).lower()
    return "database is locked" in message or "database table is locked" in message or "database is busy" in message


class DbWriteCoordinator:
    """Serialize host writes and retry transient SQLite busy errors."""

    def __init__(
        self,
        *,
        max_attempts: int = 5,
        retry_delay_seconds: float = 0.05,
    ) -> None:
        self._max_attempts = max(max_attempts, 1)
        self._retry_delay_seconds = max(retry_delay_seconds, 0.0)
        self._registry_lock = threading.RLock()
        self._db_locks: dict[str, threading.RLock] = {}
        self._resource_locks: dict[str, threading.RLock] = {}

    def run_write(
        self,
        db_name: str,
        *,
        lock_keys: list[str] | tuple[str, ...] | None = None,
        operation: Callable[[Any], T],
    ) -> T:
        """Run a short host-owned write transaction under process-local locks."""

        normalized_lock_keys = sorted({str(key) for key in (lock_keys or []) if str(key)})
        last_busy_error: sqlite3.OperationalError | None = None
        for attempt in range(self._max_attempts):
            try:
                with self._held_locks(db_name, normalized_lock_keys):
                    with get_connection(db_name) as conn:
                        if not conn.in_transaction:
                            conn.execute("BEGIN IMMEDIATE")
                        return operation(conn)
            except sqlite3.OperationalError as exc:
                if not _is_sqlite_busy_error(exc):
                    raise
                last_busy_error = exc
                if attempt + 1 >= self._max_attempts:
                    break
                time.sleep(self._retry_delay_seconds * (attempt + 1))

        raise DatabaseWriteTimeoutError(
            f"数据库写入繁忙，宿主已重试 {self._max_attempts} 次仍未获得写锁"
        ) from last_busy_error

    def _held_locks(self, db_name: str, lock_keys: list[str]):
        coordinator = self

        class _HeldLocks:
            def __enter__(self):
                self._stack = ExitStack()
                self._stack.enter_context(coordinator._db_lock(db_name))
                for key in lock_keys:
                    self._stack.enter_context(coordinator._resource_lock(key))
                return self

            def __exit__(self, exc_type, exc, tb):
                return self._stack.__exit__(exc_type, exc, tb)

        return _HeldLocks()

    def _db_lock(self, db_name: str) -> threading.RLock:
        with self._registry_lock:
            lock = self._db_locks.get(db_name)
            if lock is None:
                lock = threading.RLock()
                self._db_locks[db_name] = lock
            return lock

    def _resource_lock(self, lock_key: str) -> threading.RLock:
        with self._registry_lock:
            lock = self._resource_locks.get(lock_key)
            if lock is None:
                lock = threading.RLock()
                self._resource_locks[lock_key] = lock
            return lock


_coordinator = DbWriteCoordinator()


def get_db_write_coordinator() -> DbWriteCoordinator:
    return _coordinator

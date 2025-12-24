"""Database storage operations module.

This module provides CRUD operations for all database tables.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.utils.init_db import DB_PATH, init_database


@contextmanager
def get_connection(db_path: Path | None = None):
    """Context manager for database connections.
    
    Args:
        db_path: Path to the database file. Defaults to DB_PATH.
        
    Yields:
        sqlite3.Connection: Database connection with row factory.
    """
    path = db_path or DB_PATH
    if not path.exists():
        init_database(path)
    
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class BaseRepository:
    """Base class for repository operations."""
    
    table_name: str = ""
    
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or DB_PATH
    
    def _execute(self, query: str, params: tuple = ()) -> list[sqlite3.Row]:
        """Execute a query and return results."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
    
    def _execute_one(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        """Execute a query and return single result."""
        results = self._execute(query, params)
        return results[0] if results else None
    
    def _execute_write(self, query: str, params: tuple = ()) -> int:
        """Execute a write query and return lastrowid."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.lastrowid
    
    def get_by_id(self, id: int) -> dict | None:
        """Get record by ID."""
        row = self._execute_one(
            f"SELECT * FROM {self.table_name} WHERE id = ?", (id,)
        )
        return dict(row) if row else None
    
    def get_all(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Get all records with pagination."""
        rows = self._execute(
            f"SELECT * FROM {self.table_name} LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return [dict(row) for row in rows]
    
    def count(self, where: str = "", params: tuple = ()) -> int:
        """Count records with optional filter."""
        query = f"SELECT COUNT(*) as cnt FROM {self.table_name}"
        if where:
            query += f" WHERE {where}"
        row = self._execute_one(query, params)
        return row["cnt"] if row else 0
    
    def delete(self, id: int) -> bool:
        """Delete record by ID."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (id,)
            )
            conn.commit()
            return cursor.rowcount > 0


class CtripAccountRepository(BaseRepository):
    """Repository for ctrip_accounts table."""
    
    table_name = "ctrip_accounts"
    
    def create(
        self,
        phone: str,
        password: str | None = None,
        sms_platform_url: str | None = None,
        sms_platform_key: str | None = None,
        sms_platform_type: str | None = None,
    ) -> int:
        """Create a new Ctrip account."""
        return self._execute_write(
            """INSERT INTO ctrip_accounts 
               (phone, password, sms_platform_url, sms_platform_key, sms_platform_type)
               VALUES (?, ?, ?, ?, ?)""",
            (phone, password, sms_platform_url, sms_platform_key, sms_platform_type)
        )
    
    def update_status(self, id: int, status: str) -> bool:
        """Update account status."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE ctrip_accounts 
                   SET status = ?, updated_at = CURRENT_TIMESTAMP 
                   WHERE id = ?""",
                (status, id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_active(self) -> list[dict]:
        """Get all active accounts."""
        rows = self._execute(
            "SELECT * FROM ctrip_accounts WHERE status = 'active'"
        )
        return [dict(row) for row in rows]
    
    def get_by_phone(self, phone: str) -> dict | None:
        """Get account by phone number."""
        row = self._execute_one(
            "SELECT * FROM ctrip_accounts WHERE phone = ?", (phone,)
        )
        return dict(row) if row else None


class LaborAccountRepository(BaseRepository):
    """Repository for labor_accounts table."""
    
    table_name = "labor_accounts"
    
    def create(self, phone: str, password: str) -> int:
        """Create a new Labor account."""
        return self._execute_write(
            "INSERT INTO labor_accounts (phone, password) VALUES (?, ?)",
            (phone, password)
        )
    
    def update_stats(
        self,
        id: int,
        completed: int = 0,
        discarded: int = 0,
        approved: int = 0,
        rejected: int = 0,
    ) -> bool:
        """Increment statistics for an account."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE labor_accounts SET
                   completed_count = completed_count + ?,
                   discarded_count = discarded_count + ?,
                   approved_count = approved_count + ?,
                   rejected_count = rejected_count + ?,
                   updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (completed, discarded, approved, rejected, id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_active_unbound(self) -> list[dict]:
        """Get active accounts not bound to any environment."""
        rows = self._execute(
            """SELECT la.* FROM labor_accounts la
               LEFT JOIN environments e ON la.id = e.labor_account_id
               WHERE la.status = 'active' AND e.id IS NULL"""
        )
        return [dict(row) for row in rows]


class EnvironmentRepository(BaseRepository):
    """Repository for environments table."""
    
    table_name = "environments"
    
    def create(
        self,
        ctrip_account_id: int,
        labor_account_id: int,
        browser_profile_id: str,
    ) -> int:
        """Create a new environment."""
        return self._execute_write(
            """INSERT INTO environments 
               (ctrip_account_id, labor_account_id, browser_profile_id)
               VALUES (?, ?, ?)""",
            (ctrip_account_id, labor_account_id, browser_profile_id)
        )
    
    def update_status(self, id: int, status: str) -> bool:
        """Update environment status."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE environments SET status = ? WHERE id = ?",
                (status, id)
            )
            conn.commit()
            return cursor.rowcount > 0
    
    def get_by_ctrip_account(self, ctrip_account_id: int) -> dict | None:
        """Get environment by Ctrip account ID."""
        row = self._execute_one(
            "SELECT * FROM environments WHERE ctrip_account_id = ?",
            (ctrip_account_id,)
        )
        return dict(row) if row else None
    
    def get_idle(self) -> list[dict]:
        """Get all idle environments."""
        rows = self._execute(
            "SELECT * FROM environments WHERE status = 'idle'"
        )
        return [dict(row) for row in rows]
    
    def get_running_count(self) -> int:
        """Get count of running environments."""
        return self.count("status = 'running'")


class TaskLogRepository(BaseRepository):
    """Repository for task_logs table."""
    
    table_name = "task_logs"
    
    def create(
        self,
        message: str,
        level: str = "INFO",
        environment_id: int | None = None,
    ) -> int:
        """Create a new log entry."""
        return self._execute_write(
            "INSERT INTO task_logs (environment_id, level, message) VALUES (?, ?, ?)",
            (environment_id, level, message)
        )
    
    def get_recent(self, limit: int = 100, level: str | None = None) -> list[dict]:
        """Get recent log entries."""
        if level:
            rows = self._execute(
                """SELECT * FROM task_logs 
                   WHERE level = ? 
                   ORDER BY created_at DESC LIMIT ?""",
                (level, limit)
            )
        else:
            rows = self._execute(
                "SELECT * FROM task_logs ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
        return [dict(row) for row in rows]


class SettingsRepository(BaseRepository):
    """Repository for settings table."""
    
    table_name = "settings"
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        row = self._execute_one(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        if row:
            try:
                return json.loads(row["value"])
            except json.JSONDecodeError:
                return row["value"]
        return default
    
    def set(self, key: str, value: Any) -> None:
        """Set a setting value."""
        json_value = json.dumps(value)
        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                (key, json_value)
            )
            conn.commit()
    
    def get_all(self) -> dict[str, Any]:
        """Get all settings as a dictionary."""
        rows = self._execute("SELECT key, value FROM settings")
        result = {}
        for row in rows:
            try:
                result[row["key"]] = json.loads(row["value"])
            except json.JSONDecodeError:
                result[row["key"]] = row["value"]
        return result

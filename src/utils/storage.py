"""Database storage operations module.

This module provides CRUD operations for all database tables.
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from src.utils.init_db import DB_PATH, init_database

# Thread-local storage for database connections
_thread_local = threading.local()


@contextmanager
def get_connection(db_path: Path | None = None):
    """Context manager for thread-local database connections.
    
    Reuses the connection if it exists for the current thread.
    Ensures transactions are committed or rolled back.
    """
    path = db_path or DB_PATH
    if not path.exists():
        init_database(path)

    # Initialize connection for this thread if strictly needed or if path changed
    # Note: We assume DB_PATH is constant for the app mostly. 
    # If path changes, we force new connection (simple safety).
    
    if not hasattr(_thread_local, "conn") or _thread_local.conn is None:
        _thread_local.conn = sqlite3.connect(path)
        _thread_local.conn.row_factory = sqlite3.Row
        # Enable WAL mode for each new connection just to be sure
        _thread_local.conn.execute("PRAGMA journal_mode=WAL;")
    
    conn = _thread_local.conn
    
    try:
        yield conn
        # Optionally commit here to ensure transaction is closed? 
        # Writing methods usually commit explicitly in this codebase, 
        # but pure reads might leave an open transaction in Python sqlite3.
        # It's safer to commit to release read locks (though WAL handles readers well).
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    # Do NOT close the connection, keep it for reuse in this thread


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

    def _execute_write(self, query: str, params: tuple = ()) -> Any:
        """Execute a write query and return lastrowid."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(query, params)
            conn.commit()
            return cursor.lastrowid

    def get_by_id(self, id: int) -> dict | None:
        """Get record by ID."""
        row = self._execute_one(f"SELECT * FROM {self.table_name} WHERE id = ?", (id,))
        return dict(row) if row else None

    def get_all(self, limit: int = 100, offset: int = 0) -> list[dict]:
        """Get all records with pagination."""
        rows = self._execute(
            f"SELECT * FROM {self.table_name} LIMIT ? OFFSET ?", (limit, offset)
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
            cursor = conn.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (id,))
            conn.commit()
            return cursor.rowcount > 0


class CtripAccountRepository(BaseRepository):
    """Repository for ctrip_accounts table."""

    table_name = "ctrip_accounts"

    def create(
        self,
        phone_number: str,
        country_code: str = "+86",
        password: str | None = None,
        status: str = "idle",
        account_type: str = "manual",
        sms_verify_type: str = "manual",
        sms_platform_url: str | None = None,
        sms_platform_key: str | None = None,
        sms_platform_type: str | None = None,
        consecutive_task_count: int = 5,
        task_interval_max: int = 15,
    ) -> int:
        """Create a new Ctrip account."""
        return self._execute_write(
            """INSERT INTO ctrip_accounts 
               (country_code, phone_number, password, status, account_type, sms_verify_type, 
                sms_platform_url, sms_platform_key, sms_platform_type, consecutive_task_count, task_interval_max)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                country_code,
                phone_number,
                password,
                status,
                account_type,
                sms_verify_type,
                sms_platform_url,
                sms_platform_key,
                sms_platform_type,
                consecutive_task_count,
                task_interval_max,
            ),
        )

    def update(self, id: int, data: dict) -> bool:
        """更新账号字段。"""
        if not data:
            return False
        columns = list(data.keys())
        set_clause = ", ".join([f"{col} = ?" for col in columns])
        values = list(data.values())
        values.append(id)

        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE ctrip_accounts SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                tuple(values),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_status(self, id: int, status: str) -> bool:
        """Update account status."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE ctrip_accounts 
                   SET status = ?, updated_at = CURRENT_TIMESTAMP 
                   WHERE id = ?""",
                (status, id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_idle(self) -> list[dict]:
        """获取所有空闲（可绑定）的账号。"""
        rows = self._execute("SELECT * FROM ctrip_accounts WHERE status = 'idle'")
        return [dict(row) for row in rows]

    def get_active(self) -> list[dict]:
        """Get all active accounts."""
        rows = self._execute("SELECT * FROM ctrip_accounts WHERE status = 'active'")
        return [dict(row) for row in rows]

    def get_by_phone(self, phone_number: str, country_code: str = "+86") -> dict | None:
        """Get account by phone number."""
        row = self._execute_one(
            "SELECT * FROM ctrip_accounts WHERE country_code = ? AND phone_number = ?",
            (country_code, phone_number),
        )
        return dict(row) if row else None

    def set_registered_at(self, id: int) -> bool:
        """设置账号注册时间为当前时间（仅在 registered_at 为空时）。"""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE ctrip_accounts 
                   SET registered_at = CURRENT_TIMESTAMP 
                   WHERE id = ? AND registered_at IS NULL""",
                (id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def is_cooldown_passed(self, id: int, cooldown_days: int = 2) -> bool:
        """检查账号是否已过冷却期。

        Args:
            id: 账号 ID
            cooldown_days: 冷却天数，默认 2 天

        Returns:
            True 如果已过冷却期或非 API 账号，False 如果仍在冷却期
        """
        row = self._execute_one(
            "SELECT account_type, registered_at FROM ctrip_accounts WHERE id = ?", (id,)
        )
        if not row:
            return False

        account_type = row["account_type"]
        registered_at = row["registered_at"]

        # 非 API 账号无冷却期
        if account_type != "api":
            return True

        # API 账号未注册过，冷却期未开始
        if not registered_at:
            return False

        # 检查是否已过冷却期
        from datetime import datetime, timedelta

        try:
            reg_time = datetime.fromisoformat(registered_at.replace("Z", "+00:00"))
            cooldown_end = reg_time + timedelta(days=cooldown_days)
            return datetime.now(reg_time.tzinfo) >= cooldown_end
        except Exception:
            return False


class LaborAccountRepository(BaseRepository):
    """Repository for labor_accounts table."""

    table_name = "labor_accounts"

    def create(self, phone: str, password: str) -> int:
        """Create a new Labor account."""
        return self._execute_write(
            "INSERT INTO labor_accounts (phone, password) VALUES (?, ?)",
            (phone, password),
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
                (completed, discarded, approved, rejected, id),
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

    def get_least_bound(self) -> dict | None:
        """Get active labor account with least bind_count.

        Returns:
            The account with minimum bind_count, or None if no active accounts.
        """
        row = self._execute_one(
            """SELECT * FROM labor_accounts 
               WHERE status = 'active' 
               ORDER BY bind_count ASC, RANDOM()
               LIMIT 1"""
        )
        return dict(row) if row else None

    def increment_bind_count(self, id: int) -> bool:
        """Increment bind_count for an account."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE labor_accounts SET bind_count = bind_count + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def decrement_bind_count(self, id: int) -> bool:
        """Decrement bind_count for an account (minimum 0)."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE labor_accounts 
                   SET bind_count = MAX(0, bind_count - 1), updated_at = CURRENT_TIMESTAMP 
                   WHERE id = ?""",
                (id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    # ==================== 互斥锁定方法 ====================

    def lock_account(self, labor_id: int, env_id: int) -> bool:
        """原子锁定劳保账号。

        仅当账号未被锁定时成功。使用条件 UPDATE 实现原子操作。

        Args:
            labor_id: 劳保账号 ID
            env_id: 环境 ID

        Returns:
            True if locked successfully, False if already locked.
        """
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE labor_accounts 
                   SET locked_by_env_id = ?, locked_at = CURRENT_TIMESTAMP
                   WHERE id = ? AND locked_by_env_id IS NULL""",
                (env_id, labor_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def unlock_account(self, labor_id: int, env_id: int) -> bool:
        """释放劳保账号锁定。

        仅释放由指定环境锁定的账号（安全释放）。

        Args:
            labor_id: 劳保账号 ID
            env_id: 持有锁的环境 ID

        Returns:
            True if unlocked successfully.
        """
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE labor_accounts 
                   SET locked_by_env_id = NULL, locked_at = NULL
                   WHERE id = ? AND locked_by_env_id = ?""",
                (labor_id, env_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_available_account(self) -> dict | None:
        """获取未锁定且绑定次数最少的活跃账号。

        Returns:
            未锁定的活跃账号，优先选择 bind_count 最小的。
        """
        row = self._execute_one(
            """SELECT * FROM labor_accounts 
               WHERE status = 'active' AND locked_by_env_id IS NULL
               ORDER BY bind_count ASC, RANDOM()
               LIMIT 1"""
        )
        return dict(row) if row else None

    def force_unlock_by_env(self, env_id: int) -> int:
        """强制释放某环境的所有账号锁定。

        用于环境异常退出后的清理。

        Args:
            env_id: 环境 ID

        Returns:
            释放的账号数量。
        """
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE labor_accounts 
                   SET locked_by_env_id = NULL, locked_at = NULL 
                   WHERE locked_by_env_id = ?""",
                (env_id,),
            )
            conn.commit()
            return cursor.rowcount

    def cleanup_stale_locks(self, timeout_minutes: int = 30) -> int:
        """清理超时的旧锁。

        释放锁定时间超过指定分钟数的账号。

        Args:
            timeout_minutes: 锁定超时时间（分钟）

        Returns:
            释放的账号数量。
        """
        with get_connection(self.db_path) as conn:
            # 使用 'localtime' 确保与 locked_at 的本地时间正确比较
            cursor = conn.execute(
                """UPDATE labor_accounts 
                   SET locked_by_env_id = NULL, locked_at = NULL 
                   WHERE locked_by_env_id IS NOT NULL 
                   AND datetime(locked_at, '+' || ? || ' minutes') < datetime('now', 'localtime')""",
                (timeout_minutes,),
            )
            conn.commit()
            return cursor.rowcount

    def is_locked(self, labor_id: int) -> bool:
        """检查账号是否被锁定。"""
        row = self._execute_one(
            "SELECT locked_by_env_id FROM labor_accounts WHERE id = ?", (labor_id,)
        )
        return row is not None and row["locked_by_env_id"] is not None

    def get_active(self) -> list[dict]:
        """Get all active labor accounts."""
        rows = self._execute("SELECT * FROM labor_accounts WHERE status = 'active'")
        return [dict(row) for row in rows]

    def force_unlock_all(self) -> int:
        """强制释放所有账号锁定。
        
        仅在程序启动时调用，用于清理上次运行留下的残留锁定。
        """
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE labor_accounts SET locked_by_env_id = NULL, locked_at = NULL WHERE locked_by_env_id IS NOT NULL"
            )
            conn.commit()
            return cursor.rowcount


class ProxyIPRepository(BaseRepository):
    """Repository for proxy_ips table."""

    table_name = "proxy_ips"

    def create(
        self,
        ip: str,
        port: str,
        user: str | None = None,
        password: str | None = None,
        protocol: str = "http",
    ) -> int:
        """Add a new Proxy IP."""
        return self._execute_write(
            """INSERT INTO proxy_ips (ip, port, user, password, protocol)
               VALUES (?, ?, ?, ?, ?)""",
            (ip, port, user, password, protocol),
        )

    def get_least_used(self) -> dict | None:
        """Get active proxy IP with least usage count (random selection)."""
        # Selection strategy: status active, min usage, random among ties
        row = self._execute_one(
            """SELECT * FROM proxy_ips 
               WHERE status = 'active' 
               AND usage_count = (SELECT MIN(usage_count) FROM proxy_ips WHERE status = 'active')
               ORDER BY RANDOM()
               LIMIT 1"""
        )
        return dict(row) if row else None

    def increment_usage(self, id: int) -> bool:
        """Increment usage count for an IP."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE proxy_ips SET usage_count = usage_count + 1 WHERE id = ?", (id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    def decrement_usage(self, id: int) -> bool:
        """Decrement usage count for an IP."""
        with get_connection(self.db_path) as conn:
            # Prevent negative count just in case
            cursor = conn.execute(
                "UPDATE proxy_ips SET usage_count = MAX(0, usage_count - 1) WHERE id = ?",
                (id,),
            )
            conn.commit()
            return cursor.rowcount > 0


class EnvironmentRepository(BaseRepository):
    """Repository for environments table."""

    table_name = "environments"

    def create(
        self,
        ctrip_account_id: int | None,
        labor_account_id: int | None,
        browser_profile_id: str,
        browser_type: str = "bitbrowser",
        proxy_ip_id: int | None = None,
        daily_open_limit: int = 0,
    ) -> int:
        """Create a new environment."""
        return self._execute_write(
            """INSERT INTO environments 
               (ctrip_account_id, labor_account_id, browser_profile_id, browser_type, proxy_ip_id, daily_open_limit)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                ctrip_account_id,
                labor_account_id,
                browser_profile_id,
                browser_type,
                proxy_ip_id,
                daily_open_limit,
            ),
        )

    def check_and_increment_daily_usage(self, env_id: int) -> bool:
        """Check if environment can be opened based on daily limit logic.

        Logic:
        1. If last_open_date != today: reset count to 0, update date.
        2. If limit > 0 and count >= limit: return False.
        3. Increment count.
        4. Return True.
        """
        from datetime import date

        today = date.today().isoformat()

        with get_connection(self.db_path) as conn:
            # 1. Get current stats
            row = conn.execute(
                "SELECT daily_open_limit, daily_open_count, last_open_date FROM environments WHERE id = ?",
                (env_id,),
            ).fetchone()

            if not row:
                return False

            limit = row["daily_open_limit"] or 0
            count = row["daily_open_count"] or 0
            last_date = row["last_open_date"]

            # 2. Reset if needed
            if last_date != today:
                count = 0

            # 3. Check limit
            if limit > 0 and count >= limit:
                return False

            # 4. Increment and Update
            conn.execute(
                """UPDATE environments 
                   SET daily_open_count = ?, last_open_date = ? 
                   WHERE id = ?""",
                (count + 1, today, env_id),
            )
            conn.commit()
            return True

    def update_status(
        self, id: int, status: str, last_run_at: str | None = None
    ) -> bool:
        """Update environment status and optionally last_run_at."""
        query = "UPDATE environments SET status = ?"
        params: list[str | int] = [status]

        if last_run_at:
            query += ", last_run_at = ?"
            params.append(last_run_at)

        query += " WHERE id = ?"
        params.append(id)

        with get_connection(self.db_path) as conn:
            cursor = conn.execute(query, tuple(params))
            conn.commit()
            return cursor.rowcount > 0

    def update_connection_info(
        self,
        id: int,
        ws_endpoint: str | None,
        http_endpoint: str | None,
        pid: str | None,
    ) -> bool:
        """Update browser connection info."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE environments 
                   SET ws_endpoint = ?, http_endpoint = ?, pid = ?
                   WHERE id = ?""",
                (ws_endpoint, http_endpoint, pid, id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_ctrip_login_at(self, id: int) -> bool:
        """更新携程登录时间为当前时间（仅在 ctrip_login_at 为空时）。"""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE environments 
                   SET ctrip_login_at = CURRENT_TIMESTAMP 
                   WHERE id = ? AND ctrip_login_at IS NULL""",
                (id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update(self, id: int, data: dict) -> bool:
        """Generic update environment fields."""
        if not data:
            return False

        columns = list(data.keys())
        set_clause = ", ".join([f"{col} = ?" for col in columns])
        values = list(data.values())
        values.append(id)

        query = f"UPDATE environments SET {set_clause} WHERE id = ?"

        with get_connection(self.db_path) as conn:
            cursor = conn.execute(query, tuple(values))
            conn.commit()
            return cursor.rowcount > 0

    def get_by_ctrip_account(self, ctrip_account_id: int) -> dict | None:
        """Get environment by Ctrip account ID."""
        row = self._execute_one(
            "SELECT * FROM environments WHERE ctrip_account_id = ?", (ctrip_account_id,)
        )
        return dict(row) if row else None

    def get_idle(self) -> list[dict]:
        """Get all idle environments."""
        rows = self._execute("SELECT * FROM environments WHERE status = 'idle'")
        return [dict(row) for row in rows]

    def get_running_count(self) -> int:
        """Get count of running environments."""
        return self.count("status = 'running'")

    def reset_all_to_idle(self) -> int:
        """重置所有环境为 idle 状态。
        
        并清理连接信息，仅在启动时调用。
        """
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE environments 
                   SET status = 'idle', ws_endpoint = NULL, http_endpoint = NULL, pid = NULL 
                   WHERE status != 'idle'"""
            )
            conn.commit()
            return cursor.rowcount


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
            (environment_id, level, message),
        )

    def log_operation(
        self,
        environment_id: int,
        operation_type: str,
        operation_details: dict,
        level: str = "INFO",
        message: str | None = None,
    ) -> int:
        """Log an operation with structured details.

        Args:
            environment_id: The environment this operation belongs to.
            operation_type: Type of operation (e.g., 'openEnvironment', 'login', 'task').
            operation_details: Dictionary with operation details (will be JSON serialized).
            level: Log level (INFO, WARNING, ERROR, DEBUG).
            message: Optional human-readable message.

        Returns:
            ID of the created log entry.
        """
        import json

        details_json = json.dumps(operation_details, ensure_ascii=False)

        return self._execute_write(
            """INSERT INTO task_logs 
               (environment_id, level, message, operation_type, operation_details) 
               VALUES (?, ?, ?, ?, ?)""",
            (
                environment_id,
                level,
                message or f"Operation: {operation_type}",
                operation_type,
                details_json,
            ),
        )

    def get_recent(self, limit: int = 100, level: str | None = None) -> list[dict]:
        """Get recent log entries."""
        if level:
            rows = self._execute(
                """SELECT * FROM task_logs 
                   WHERE level = ? 
                   ORDER BY created_at DESC LIMIT ?""",
                (level, limit),
            )
        else:
            rows = self._execute(
                "SELECT * FROM task_logs ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        return [dict(row) for row in rows]


class SettingsRepository(BaseRepository):
    """Repository for settings table."""

    table_name = "settings"

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        row = self._execute_one("SELECT value FROM settings WHERE key = ?", (key,))
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
                (key, json_value),
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

    # SMS Limit Counters

    def get_sms_creation_count_today(self) -> int:
        """获取今日通过接码平台创建环境的数量。
        
        如果日期不是今天，会自动重置计数。
        """
        import datetime
        today = datetime.date.today().isoformat()
        
        stored_date = self.get("sms_env_creation_date")
        if stored_date != today:
            self.reset_sms_creation_count()
            return 0
            
        return int(self.get("sms_env_creation_count", 0))

    def increment_sms_creation_count(self) -> int:
        """增加今日接码创建计数。"""
        current = self.get_sms_creation_count_today()
        new_val = current + 1
        self.set("sms_env_creation_count", new_val)
        return new_val

    def reset_sms_creation_count(self) -> None:
        """重置接码创建计数。"""
        import datetime
        today = datetime.date.today().isoformat()
        self.set("sms_env_creation_count", 0)
        self.set("sms_env_creation_date", today)

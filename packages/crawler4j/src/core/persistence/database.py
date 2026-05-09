"""数据库连接管理。

规格参考: docs/02-requirements/reference-srs/05-framework-core/05-9-data-persistence.md

存储分层:
    - config.db: 配置数据（读多写少）
    - state.db: 运行时状态 KV（高频读写）
    - data.db: 业务数据（只写/批量读）
"""

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from src.utils import paths

# 数据库文件
CONFIG_DB = "config.db"
STATE_DB = "state.db"
DATA_DB = "data.db"
DB_BUSY_TIMEOUT_SECONDS = 5.0
DB_BUSY_TIMEOUT_MS = int(DB_BUSY_TIMEOUT_SECONDS * 1000)

# 线程本地存储
_thread_local = threading.local()

_MODULE_DATASET_REQUIRED_COLUMNS = {
    "module_name",
    "dataset_name",
    "record_index",
    "record_key",
    "run_status",
    "record_status",
    "record_json",
    "created_at",
    "updated_at",
}
_MODULE_DATASET_PRIMARY_KEY = {
    "module_name": 1,
    "dataset_name": 2,
    "record_index": 3,
}
_MODULE_DATA_RESOURCE_REQUIRED_COLUMNS = {
    "module_name",
    "resource_id",
    "storage_mode",
    "logical_name",
    "physical_table_name",
    "record_key_field",
    "schema_version",
    "schema_json",
    "indexes_json",
    "cleanup_policy",
    "created_at",
    "updated_at",
}
_MODULE_DB_VIEW_REQUIRED_COLUMNS = {
    "module_name",
    "view_id",
    "view_kind",
    "physical_view_name",
    "source_resource_ids_json",
    "select_sql_template",
    "columns_json",
    "schema_version",
    "cleanup_policy",
    "created_at",
    "updated_at",
}


def get_db_path(db_name: str) -> Path:
    """获取数据库文件路径。
    
    Args:
        db_name: 数据库文件名（config.db/state.db/data.db）。
    
    Returns:
        数据库文件绝对路径。
    """
    data_dir = paths.get_app_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / db_name


@contextmanager
def get_connection(db_name: str = CONFIG_DB) -> Generator[sqlite3.Connection, None, None]:
    """获取数据库连接的上下文管理器。
    
    使用线程本地存储复用连接，确保事务正确提交或回滚。
    
    Args:
        db_name: 数据库文件名。
    
    Yields:
        sqlite3.Connection 对象。
    
    Example:
        >>> with get_connection(CONFIG_DB) as conn:
        ...     cursor = conn.execute("SELECT * FROM config_entries")
        ...     rows = cursor.fetchall()
    """
    db_path = get_db_path(db_name)
    
    # 获取或创建线程本地连接
    conn_key = f"conn_{db_name}"
    conn_path_key = f"{conn_key}_path"
    conn = getattr(_thread_local, conn_key, None)
    conn_path = getattr(_thread_local, conn_path_key, None)

    if conn is not None and conn_path != str(db_path):
        try:
            conn.close()
        except Exception:
            pass
        conn = None
    
    if conn is None:
        conn = sqlite3.connect(str(db_path), timeout=DB_BUSY_TIMEOUT_SECONDS, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA busy_timeout={DB_BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA foreign_keys=ON")
        setattr(_thread_local, conn_key, conn)
        setattr(_thread_local, conn_path_key, str(db_path))
    
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_database() -> None:
    """初始化所有数据库表结构。
    
    在应用启动时调用，创建所需的表。
    """
    _init_config_db()
    _init_state_db()
    _init_data_db()


def _create_module_datasets_table(conn: sqlite3.Connection, table_name: str = "module_datasets") -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            module_name TEXT NOT NULL,
            dataset_name TEXT NOT NULL,
            record_index INTEGER NOT NULL,
            record_key TEXT,
            run_status TEXT NOT NULL DEFAULT '不占用',
            record_status TEXT NOT NULL DEFAULT '',
            record_json TEXT NOT NULL,
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            updated_at INTEGER DEFAULT (strftime('%s', 'now')),
            PRIMARY KEY (module_name, dataset_name, record_index)
        )
        """
    )


def _create_module_data_resources_table(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS module_data_resources (
            module_name TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            storage_mode TEXT NOT NULL CHECK (storage_mode IN ('managed_dataset', 'custom_table')),
            logical_name TEXT NOT NULL,
            physical_table_name TEXT NOT NULL,
            record_key_field TEXT,
            schema_version INTEGER NOT NULL DEFAULT 1,
            schema_json TEXT NOT NULL DEFAULT '{}',
            indexes_json TEXT NOT NULL DEFAULT '{}',
            cleanup_policy TEXT NOT NULL CHECK (cleanup_policy IN ('delete_rows', 'drop_table', 'keep')),
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            updated_at INTEGER DEFAULT (strftime('%s', 'now')),
            PRIMARY KEY (module_name, resource_id)
        );

        CREATE INDEX IF NOT EXISTS idx_module_data_resources_module
        ON module_data_resources(module_name);

        CREATE INDEX IF NOT EXISTS idx_module_data_resources_module_mode
        ON module_data_resources(module_name, storage_mode);
        """
    )


def _create_module_db_views_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS module_db_views (
            module_name TEXT NOT NULL,
            view_id TEXT NOT NULL,
            view_kind TEXT NOT NULL CHECK (view_kind = 'sql_view'),
            physical_view_name TEXT NOT NULL,
            source_resource_ids_json TEXT NOT NULL DEFAULT '[]',
            select_sql_template TEXT NOT NULL,
            columns_json TEXT NOT NULL DEFAULT '[]',
            schema_version INTEGER NOT NULL DEFAULT 1,
            cleanup_policy TEXT NOT NULL CHECK (cleanup_policy IN ('drop_view', 'keep')),
            created_at INTEGER DEFAULT (strftime('%s', 'now')),
            updated_at INTEGER DEFAULT (strftime('%s', 'now')),
            PRIMARY KEY (module_name, view_id)
        )
        """
    )


def _create_module_db_views_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_module_db_views_module
        ON module_db_views(module_name)
        """
    )


def _create_module_datasets_indexes(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_module_datasets_module
        ON module_datasets(module_name)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_module_datasets_dataset
        ON module_datasets(module_name, dataset_name)
        """
    )


def _table_info_rows(conn: sqlite3.Connection, table_name: str) -> list[sqlite3.Row]:
    return conn.execute(f"PRAGMA table_info({table_name})").fetchall()


def _module_datasets_matches_current_schema(table_info_rows: list[sqlite3.Row]) -> bool:
    existing_columns = {row["name"] for row in table_info_rows}
    if existing_columns != _MODULE_DATASET_REQUIRED_COLUMNS:
        return False

    primary_key = {
        row["name"]: row["pk"]
        for row in table_info_rows
        if row["pk"]
    }
    return primary_key == _MODULE_DATASET_PRIMARY_KEY


def _ensure_module_data_resources_table(conn: sqlite3.Connection) -> None:
    table_exists = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'module_data_resources'
        """
    ).fetchone()
    if not table_exists:
        _create_module_data_resources_table(conn)
        return

    table_info_rows = _table_info_rows(conn, "module_data_resources")
    existing_columns = {row["name"] for row in table_info_rows}
    if existing_columns != _MODULE_DATA_RESOURCE_REQUIRED_COLUMNS:
        raise RuntimeError(
            "Only crawler4j 0.4.0 module_data_resources schema is supported: "
            f"existing_columns={sorted(existing_columns)}"
        )

    _create_module_data_resources_table(conn)


def _ensure_module_db_views_table(conn: sqlite3.Connection) -> None:
    table_exists = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'module_db_views'
        """
    ).fetchone()
    if not table_exists:
        _create_module_db_views_table(conn)
        _create_module_db_views_indexes(conn)
        return

    table_info_rows = _table_info_rows(conn, "module_db_views")
    existing_columns = {row["name"] for row in table_info_rows}
    if existing_columns != _MODULE_DB_VIEW_REQUIRED_COLUMNS:
        raise RuntimeError(
            "Only crawler4j 0.4.0 module_db_views schema is supported: "
            f"existing_columns={sorted(existing_columns)}"
        )

    row = conn.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = 'module_db_views'
        """
    ).fetchone()
    table_sql = str(row["sql"] or "").lower() if row else ""
    if "materialized_view" in table_sql or "drop_table" in table_sql:
        raise RuntimeError("Only crawler4j 0.4.0 module_db_views schema is supported")

    _create_module_db_views_table(conn)
    _create_module_db_views_indexes(conn)


def _ensure_module_datasets_table(conn: sqlite3.Connection) -> None:
    table_exists = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = 'module_datasets'
        """
    ).fetchone()
    if not table_exists:
        _create_module_datasets_table(conn)
        _create_module_datasets_indexes(conn)
        return

    table_info_rows = _table_info_rows(conn, "module_datasets")
    existing_columns = {row["name"] for row in table_info_rows}
    if _module_datasets_matches_current_schema(table_info_rows):
        _create_module_datasets_indexes(conn)
        return

    primary_key = {
        row["name"]: row["pk"]
        for row in table_info_rows
        if row["pk"]
    }
    raise RuntimeError(
        "Only crawler4j 0.4.0 module_datasets schema is supported: "
        f"columns={sorted(existing_columns)}, primary_key={primary_key}"
    )


def _init_config_db() -> None:
    """初始化配置数据库。"""
    with get_connection(CONFIG_DB) as conn:
        conn.executescript("""
            -- 宿主配置中心条目表（按 namespace + key_path 路径化存储）
            CREATE TABLE IF NOT EXISTS config_entries (
                namespace TEXT NOT NULL,
                scope_type TEXT NOT NULL DEFAULT 'global',
                scope_name TEXT NOT NULL DEFAULT '',
                key_path TEXT NOT NULL,
                value_json TEXT NOT NULL,
                value_type TEXT NOT NULL,
                updated_at INTEGER DEFAULT (strftime('%s', 'now')),
                PRIMARY KEY (namespace, scope_type, scope_name, key_path)
            );

            -- 模块配置条目表（按模块/工作流 + key_path 扁平化存储）
            CREATE TABLE IF NOT EXISTS module_config_entries (
                module_name TEXT NOT NULL,
                scope_type TEXT NOT NULL,
                scope_name TEXT NOT NULL DEFAULT '',
                key_path TEXT NOT NULL,
                value_json TEXT NOT NULL,
                value_type TEXT NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now')),
                PRIMARY KEY (module_name, scope_type, scope_name, key_path)
            );

            CREATE INDEX IF NOT EXISTS idx_module_config_scope
            ON module_config_entries(module_name, scope_type, scope_name);
        """)
        _migrate_legacy_settings_to_config_entries(conn)
        _delete_removed_host_config_entries(conn)


def _split_legacy_setting_key(key: str) -> tuple[str, str]:
    parts = [part for part in str(key or "").strip().split(".") if part]
    if len(parts) >= 2 and parts[0] in {"browser", "mms"}:
        return ".".join(parts[:2]), ".".join(parts[2:]) or parts[-1]
    if len(parts) >= 2:
        return parts[0], ".".join(parts[1:])
    return "system", parts[0] if parts else "unknown"


def _infer_legacy_setting_type(value_json: str) -> str:
    try:
        value = json.loads(value_json)
    except Exception:
        return "string"
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _migrate_legacy_settings_to_config_entries(conn: sqlite3.Connection) -> None:
    legacy_table = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'settings'"
    ).fetchone()
    if legacy_table is None:
        return
    rows = conn.execute("SELECT key, value, updated_at FROM settings").fetchall()
    for row in rows:
        namespace, key_path = _split_legacy_setting_key(row["key"])
        conn.execute(
            """
            INSERT INTO config_entries (
                namespace, scope_type, scope_name, key_path, value_json, value_type, updated_at
            ) VALUES (?, 'global', '', ?, ?, ?, ?)
            ON CONFLICT(namespace, scope_type, scope_name, key_path) DO UPDATE SET
                value_json = excluded.value_json,
                value_type = excluded.value_type,
                updated_at = excluded.updated_at
            """,
            (
                namespace,
                key_path,
                row["value"],
                _infer_legacy_setting_type(row["value"]),
                row["updated_at"],
            ),
        )
    conn.execute("DROP TABLE settings")


def _delete_removed_host_config_entries(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        DELETE FROM config_entries
        WHERE namespace = 'system'
          AND scope_type = 'global'
          AND scope_name = ''
          AND key_path IN ('autostart', 'minimize_on_start')
        """
    )


def _init_state_db() -> None:
    """初始化状态数据库。"""
    with get_connection(STATE_DB) as conn:
        conn.executescript("""
            -- KV 存储表（支持 TTL）
            CREATE TABLE IF NOT EXISTS kv_store (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                expires_at INTEGER,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            );
            
            CREATE INDEX IF NOT EXISTS idx_kv_expires ON kv_store(expires_at);
            
            -- 环境表（REM）
            CREATE TABLE IF NOT EXISTS environments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                kind TEXT NOT NULL,
                provider TEXT NOT NULL,
                status TEXT NOT NULL,
                external_id TEXT,
                lease_id TEXT,
                task_run_id TEXT,
                last_used_at INTEGER,
                daily_usage_count INTEGER DEFAULT 0,
                daily_usage_date TEXT,
                proxy_config_json TEXT,
                capabilities TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            );
            
            CREATE INDEX IF NOT EXISTS idx_env_status ON environments(status);
            CREATE INDEX IF NOT EXISTS idx_env_external ON environments(external_id);
            CREATE INDEX IF NOT EXISTS idx_env_last_used ON environments(last_used_at);
            
            -- IP 池表
            CREATE TABLE IF NOT EXISTS ip_pools (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                strategy TEXT DEFAULT 'least_bound',
                config_json TEXT,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            );
            
            -- IP 条目表
            CREATE TABLE IF NOT EXISTS ip_entries (
                id TEXT PRIMARY KEY,
                pool_id TEXT NOT NULL REFERENCES ip_pools(id) ON DELETE CASCADE,
                address TEXT NOT NULL,
                protocol TEXT NOT NULL,
                port INTEGER NOT NULL,
                username TEXT,
                password TEXT,
                bound_count INTEGER DEFAULT 0,
                safety_score INTEGER DEFAULT 100,
                expires_at INTEGER,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            );
            
            CREATE INDEX IF NOT EXISTS idx_ip_pool ON ip_entries(pool_id);
            CREATE INDEX IF NOT EXISTS idx_ip_bound ON ip_entries(bound_count);

            -- 环境元数据表（动态扩展字段）
            CREATE TABLE IF NOT EXISTS env_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                env_id TEXT NOT NULL REFERENCES environments(id) ON DELETE CASCADE,
                namespace TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                value_type TEXT DEFAULT 'string',
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now')),
                
                UNIQUE(env_id, namespace, key)
            );
            
            CREATE INDEX IF NOT EXISTS idx_meta_env ON env_metadata(env_id);
            CREATE INDEX IF NOT EXISTS idx_meta_ns_key ON env_metadata(namespace, key);
        """)
        existing_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(environments)").fetchall()
        }
        obsolete_env_columns = {
            "provider_env_id",
            "provider_env_name",
            "provider_group",
            "provider_proxy",
            "provider_raw_meta",
            "imported_at",
        }
        conn.execute("DROP INDEX IF EXISTS idx_env_provider_env_id")
        conn.execute("DROP INDEX IF EXISTS idx_env_provider_env_name")
        conn.execute("DROP INDEX IF EXISTS idx_env_provider_source_key")
        for column_name in obsolete_env_columns & existing_columns:
            conn.execute(f"ALTER TABLE environments DROP COLUMN {column_name}")
        conn.execute(
            """
            UPDATE environments
            SET name = TRIM(name)
            WHERE name IS NOT NULL
            """
        )
        conn.execute(
            """
            UPDATE environments
            SET name = NULL
            WHERE name IS NOT NULL
              AND name <> ''
              AND id NOT IN (
                  SELECT MIN(id)
                  FROM environments
                  WHERE name IS NOT NULL
                    AND name <> ''
                  GROUP BY provider, name
              )
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_env_provider_name
            ON environments(provider, name)
            WHERE name IS NOT NULL
              AND name <> ''
            """
        )


def _init_data_db() -> None:
    """初始化业务数据数据库。"""
    with get_connection(DATA_DB) as conn:
        _ensure_module_data_resources_table(conn)
        _ensure_module_db_views_table(conn)
        _ensure_module_datasets_table(conn)
        conn.execute("DROP TABLE IF EXISTS module_dataset_manifests")
        conn.executescript("""
            -- 模块数据资源登记表统一管理 managed dataset 与 custom table。

            -- 模块宿主页 schema
            CREATE TABLE IF NOT EXISTS module_pages (
                module_name TEXT NOT NULL,
                page_id TEXT NOT NULL,
                schema_json TEXT NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now')),
                PRIMARY KEY (module_name, page_id)
            );

            CREATE INDEX IF NOT EXISTS idx_module_pages_module
            ON module_pages(module_name);

            -- 模块审计事件（append-only）
            CREATE TABLE IF NOT EXISTS module_audit_events (
                id TEXT PRIMARY KEY,
                module_name TEXT NOT NULL,
                dataset_name TEXT NOT NULL,
                entity_key TEXT,
                event_type TEXT NOT NULL,
                run_id TEXT,
                previous_status TEXT,
                next_status TEXT,
                result TEXT,
                reason TEXT,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now'))
            );

            CREATE INDEX IF NOT EXISTS idx_module_audit_events_module_dataset_time
            ON module_audit_events(module_name, dataset_name, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_module_audit_events_entity_time
            ON module_audit_events(module_name, dataset_name, entity_key, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_module_audit_events_type_time
            ON module_audit_events(module_name, dataset_name, event_type, created_at DESC);
        """)

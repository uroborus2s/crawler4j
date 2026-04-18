"""数据库连接管理。

规格参考: docs/02-requirements/reference-srs/05-framework-core/05-9-data-persistence.md

存储分层:
    - config.db: 配置数据（读多写少）
    - state.db: 运行时状态 KV（高频读写）
    - data.db: 业务数据（只写/批量读）
"""

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

# 线程本地存储
_thread_local = threading.local()


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
        ...     cursor = conn.execute("SELECT * FROM configs")
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
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
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


def _init_config_db() -> None:
    """初始化配置数据库。"""
    with get_connection(CONFIG_DB) as conn:
        conn.executescript("""
            -- 配置表（模块配置、全局设置）
            CREATE TABLE IF NOT EXISTS configs (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
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
            
            -- 设置表（系统设置）
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at INTEGER DEFAULT (strftime('%s', 'now'))
            );
        """)


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
            
            -- 环境-IP 绑定表
            CREATE TABLE IF NOT EXISTS env_ip_bindings (
                env_id TEXT PRIMARY KEY REFERENCES environments(id) ON DELETE CASCADE,
                ip_id TEXT NOT NULL REFERENCES ip_entries(id) ON DELETE CASCADE,
                bound_at INTEGER NOT NULL
            );
            
            CREATE INDEX IF NOT EXISTS idx_binding_ip ON env_ip_bindings(ip_id);
            
            
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


def _init_data_db() -> None:
    """初始化业务数据数据库。"""
    with get_connection(DATA_DB) as conn:
        conn.executescript("""
            -- 模块数据集（当前按 module + dataset 聚合存储）
            CREATE TABLE IF NOT EXISTS module_datasets (
                module_name TEXT NOT NULL,
                dataset_name TEXT NOT NULL,
                records_json TEXT NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now')),
                PRIMARY KEY (module_name, dataset_name)
            );

            CREATE INDEX IF NOT EXISTS idx_module_datasets_module
            ON module_datasets(module_name);

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

            -- 模块数据表视图元数据
            CREATE TABLE IF NOT EXISTS module_data_table_views (
                module_name TEXT NOT NULL,
                view_id TEXT NOT NULL,
                schema_json TEXT NOT NULL,
                created_at INTEGER DEFAULT (strftime('%s', 'now')),
                updated_at INTEGER DEFAULT (strftime('%s', 'now')),
                PRIMARY KEY (module_name, view_id)
            );

            CREATE INDEX IF NOT EXISTS idx_module_data_views_module
            ON module_data_table_views(module_name);
        """)

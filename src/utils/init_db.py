"""Database schema and initialization module.

This module contains the database schema definitions and initialization function.
These are required at runtime when the application first starts.

For schema migrations, use: uv run python -m migrations.migrate upgrade
"""

import sqlite3
from pathlib import Path

from src.utils.paths import get_db_path

# Database path (stored in user data directory for portability and write access)
DB_PATH = get_db_path()

SCHEMA = """
-- 携程账号表
CREATE TABLE IF NOT EXISTS ctrip_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT DEFAULT '+86',
    phone_number TEXT NOT NULL,
    password TEXT,
    status TEXT DEFAULT 'idle' CHECK(status IN ('idle', 'active', 'running', 'blacklisted', 'disabled')),
    account_type TEXT DEFAULT 'manual' CHECK(account_type IN ('manual', 'api')),
    sms_verify_type TEXT DEFAULT 'manual' CHECK(sms_verify_type IN ('manual', 'auto')),
    sms_platform_url TEXT,
    sms_platform_key TEXT,
    sms_platform_type TEXT,
    consecutive_task_count INTEGER DEFAULT 5,
    task_interval_max INTEGER DEFAULT 15,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, phone_number)
);

-- 劳保平台账号表
CREATE TABLE IF NOT EXISTS labor_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'blacklisted', 'disabled')),
    bind_count INTEGER DEFAULT 0,
    completed_count INTEGER DEFAULT 0,
    discarded_count INTEGER DEFAULT 0,
    approved_count INTEGER DEFAULT 0,
    rejected_count INTEGER DEFAULT 0,
    -- 互斥锁定字段
    locked_by_env_id INTEGER DEFAULT NULL,
    locked_at TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);


-- 代理IP表
CREATE TABLE IF NOT EXISTS proxy_ips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip TEXT NOT NULL,
    port TEXT NOT NULL,
    user TEXT,
    password TEXT,
    protocol TEXT DEFAULT 'http',  -- http, socks5
    usage_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'disabled')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 环境表
CREATE TABLE IF NOT EXISTS environments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ctrip_account_id INTEGER UNIQUE,
    labor_account_id INTEGER,
    browser_profile_id TEXT NOT NULL,
    browser_type TEXT DEFAULT 'bitbrowser',
    proxy_ip_id INTEGER,
    status TEXT DEFAULT 'idle' CHECK(status IN ('idle', 'running', 'error')),
    ws_endpoint TEXT,
    http_endpoint TEXT,
    pid TEXT,
    daily_open_limit INTEGER DEFAULT 0,
    daily_open_count INTEGER DEFAULT 0,
    last_open_date DATE,
    last_run_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ctrip_account_id) REFERENCES ctrip_accounts(id) ON DELETE SET NULL,
    FOREIGN KEY (labor_account_id) REFERENCES labor_accounts(id) ON DELETE SET NULL,
    FOREIGN KEY (proxy_ip_id) REFERENCES proxy_ips(id) ON DELETE SET NULL
);

-- 任务日志表
CREATE TABLE IF NOT EXISTS task_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    environment_id INTEGER,
    level TEXT CHECK(level IN ('INFO', 'WARNING', 'ERROR', 'DEBUG')),
    message TEXT,
    operation_type TEXT,
    operation_details TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE SET NULL
);

-- 设置表
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_ctrip_status ON ctrip_accounts(status);
CREATE INDEX IF NOT EXISTS idx_labor_status ON labor_accounts(status);
CREATE INDEX IF NOT EXISTS idx_labor_bind_count ON labor_accounts(bind_count);
CREATE INDEX IF NOT EXISTS idx_labor_locked ON labor_accounts(locked_by_env_id);
CREATE INDEX IF NOT EXISTS idx_env_status ON environments(status);
CREATE INDEX IF NOT EXISTS idx_logs_env ON task_logs(environment_id);
CREATE INDEX IF NOT EXISTS idx_logs_created ON task_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_proxy_usage ON proxy_ips(usage_count);

-- 初始化默认设置
INSERT OR IGNORE INTO settings (key, value) VALUES ('browser_type', '"bitbrowser"');
INSERT OR IGNORE INTO settings (key, value) VALUES ('browser_api_url', '"http://127.0.0.1:54345"');
INSERT OR IGNORE INTO settings (key, value) VALUES ('concurrency_limit', '10');
INSERT OR IGNORE INTO settings (key, value) VALUES ('task_interval', '5');
INSERT OR IGNORE INTO settings (key, value) VALUES ('retry_count', '3');
INSERT OR IGNORE INTO settings (key, value) VALUES ('schema_version', '1');
INSERT OR IGNORE INTO settings (key, value) VALUES ('lock_timeout_minutes', '30');
"""


def init_database(db_path: Path | None = None) -> None:
    """Initialize the database with the schema.
    
    This is called automatically when the application starts and no database exists.
    
    Args:
        db_path: Path to the database file. Defaults to DB_PATH.
    """
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()

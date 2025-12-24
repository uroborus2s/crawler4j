"""Database initialization script.

This module creates the SQLite database schema for the crawler application.
Tables: ctrip_accounts, labor_accounts, environments, task_logs, settings
"""

import sqlite3
from pathlib import Path

# Database path (relative to project root)
DB_PATH = Path(__file__).parent.parent.parent / "crawler.db"

SCHEMA = """
-- 携程账号表
CREATE TABLE IF NOT EXISTS ctrip_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE NOT NULL,
    password TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'blacklisted', 'disabled')),
    sms_platform_url TEXT,
    sms_platform_key TEXT,
    sms_platform_type TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 劳保平台账号表
CREATE TABLE IF NOT EXISTS labor_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'blacklisted', 'disabled')),
    completed_count INTEGER DEFAULT 0,
    discarded_count INTEGER DEFAULT 0,
    approved_count INTEGER DEFAULT 0,
    rejected_count INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 环境表
CREATE TABLE IF NOT EXISTS environments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ctrip_account_id INTEGER UNIQUE NOT NULL,
    labor_account_id INTEGER UNIQUE NOT NULL,
    browser_profile_id TEXT NOT NULL,
    status TEXT DEFAULT 'idle' CHECK(status IN ('idle', 'running', 'error')),
    last_run_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ctrip_account_id) REFERENCES ctrip_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (labor_account_id) REFERENCES labor_accounts(id) ON DELETE CASCADE
);

-- 任务日志表
CREATE TABLE IF NOT EXISTS task_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    environment_id INTEGER,
    level TEXT CHECK(level IN ('INFO', 'WARNING', 'ERROR')),
    message TEXT,
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
CREATE INDEX IF NOT EXISTS idx_env_status ON environments(status);
CREATE INDEX IF NOT EXISTS idx_logs_env ON task_logs(environment_id);
CREATE INDEX IF NOT EXISTS idx_logs_created ON task_logs(created_at);

-- 初始化默认设置
INSERT OR IGNORE INTO settings (key, value) VALUES ('browser_type', '"bitbrowser"');
INSERT OR IGNORE INTO settings (key, value) VALUES ('browser_api_url', '"http://127.0.0.1:54345"');
INSERT OR IGNORE INTO settings (key, value) VALUES ('concurrency_limit', '10');
INSERT OR IGNORE INTO settings (key, value) VALUES ('task_interval', '5');
INSERT OR IGNORE INTO settings (key, value) VALUES ('retry_count', '3');
"""


def init_database(db_path: Path | None = None) -> None:
    """Initialize the database with the schema.
    
    Args:
        db_path: Path to the database file. Defaults to DB_PATH.
    """
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        print(f"✅ Database initialized: {path}")
    finally:
        conn.close()


def reset_database(db_path: Path | None = None) -> None:
    """Drop all tables and reinitialize the database.
    
    Args:
        db_path: Path to the database file. Defaults to DB_PATH.
    """
    path = db_path or DB_PATH
    if path.exists():
        path.unlink()
        print(f"🗑️ Deleted existing database: {path}")
    init_database(path)


if __name__ == "__main__":
    init_database()

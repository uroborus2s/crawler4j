"""Database initialization and management script.

This module handles database creation, schema definitions, and migration tools.
Usage:
    python -m src.utils.init_db [init|reset|migrate]
"""

import argparse
import sqlite3
from pathlib import Path

# Database path (relative to project root)
DB_PATH = Path(__file__).parent.parent.parent / "crawler.db"

SCHEMA = """
-- 携程账号表
CREATE TABLE IF NOT EXISTS ctrip_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT DEFAULT '+86',
    phone_number TEXT NOT NULL,
    password TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'blacklisted', 'disabled')),
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
"""


def init_database(db_path: Path | None = None) -> None:
    """Initialize the database with the schema (No migration).
    
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
    
    print(f"✅ Database initialized: {path}")


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


def migrate_db(db_path: Path | None = None) -> None:
    """Manually run database migrations for development.
    
    Updates schema including new connection info columns.
    """
    path = db_path or DB_PATH
    if not path.exists():
        print(f"❌ Database not found at {path}. Please run init first.")
        return

    conn = sqlite3.connect(path)
    try:
        cursor = conn.cursor()
        
        # 0. Check and add proxy_ips table if missing
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='proxy_ips'")
        if not cursor.fetchone():
            print("🔧 Creating proxy_ips table...")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS proxy_ips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip TEXT NOT NULL,
                    port TEXT NOT NULL,
                    user TEXT,
                    password TEXT,
                    protocol TEXT DEFAULT 'http',
                    usage_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'disabled')),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_proxy_usage ON proxy_ips(usage_count);
            """)

        # 1. Update environments table with new columns
        cursor.execute("PRAGMA table_info(environments)")
        columns = [c[1] for c in cursor.fetchall()]
        
        # Helper to add column if missing
        def add_column_if_missing(col_name, col_def):
            if col_name not in columns:
                print(f"Migrating: Adding {col_name} to environments...")
                cursor.execute(f"ALTER TABLE environments ADD COLUMN {col_name} {col_def}")
                return True
            return False
            
        updated = False
        updated |= add_column_if_missing("proxy_ip_id", "INTEGER REFERENCES proxy_ips(id) ON DELETE SET NULL")
        updated |= add_column_if_missing("ws_endpoint", "TEXT")
        updated |= add_column_if_missing("http_endpoint", "TEXT")
        updated |= add_column_if_missing("pid", "TEXT")
        updated |= add_column_if_missing("daily_open_limit", "INTEGER DEFAULT 0")
        updated |= add_column_if_missing("daily_open_count", "INTEGER DEFAULT 0")
        updated |= add_column_if_missing("last_open_date", "DATE")
        
        # 2. Update labor_accounts table with bind_count column
        cursor.execute("PRAGMA table_info(labor_accounts)")
        labor_columns = [c[1] for c in cursor.fetchall()]
        
        if "bind_count" not in labor_columns:
            print("Migrating: Adding bind_count to labor_accounts...")
            cursor.execute("ALTER TABLE labor_accounts ADD COLUMN bind_count INTEGER DEFAULT 0")
            updated = True
        
        # Create index for bind_count if not exists
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_labor_bind_count ON labor_accounts(bind_count)")
        
        # 3. Migrate ctrip_accounts: split phone into country_code + phone_number
        cursor.execute("PRAGMA table_info(ctrip_accounts)")
        ctrip_columns = [c[1] for c in cursor.fetchall()]
        
        if "phone" in ctrip_columns and "phone_number" not in ctrip_columns:
            print("Migrating: Splitting phone into country_code + phone_number...")
            
            # Create new table with split fields
            cursor.executescript("""
                CREATE TABLE ctrip_accounts_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    country_code TEXT DEFAULT '+86',
                    phone_number TEXT NOT NULL,
                    password TEXT,
                    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'blacklisted', 'disabled')),
                    sms_platform_url TEXT,
                    sms_platform_key TEXT,
                    sms_platform_type TEXT,
                    consecutive_task_count INTEGER DEFAULT 5,
                    task_interval_max INTEGER DEFAULT 15,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(country_code, phone_number)
                );
            """)
            
            # Migrate data: parse phone field
            cursor.execute("SELECT id, phone, password, status, sms_platform_url, sms_platform_key, sms_platform_type, created_at, updated_at FROM ctrip_accounts")
            rows = cursor.fetchall()
            
            import re
            for row in rows:
                phone = row[1] or ""
                # Parse phone: +86xxx -> country_code=+86, phone_number=xxx
                match = re.match(r"(\+\d+)(.*)", phone)
                if match:
                    country_code = match.group(1)
                    phone_number = match.group(2)
                else:
                    country_code = "+86"
                    phone_number = phone
                
                cursor.execute("""
                    INSERT INTO ctrip_accounts_new 
                    (id, country_code, phone_number, password, status, sms_platform_url, sms_platform_key, sms_platform_type, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (row[0], country_code, phone_number, row[2], row[3], row[4], row[5], row[6], row[7], row[8]))
            
            cursor.execute("DROP TABLE ctrip_accounts")
            cursor.execute("ALTER TABLE ctrip_accounts_new RENAME TO ctrip_accounts")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ctrip_status ON ctrip_accounts(status)")
            updated = True
            print("✅ ctrip_accounts phone field split completed")
        
        # Add new columns to ctrip_accounts if missing
        cursor.execute("PRAGMA table_info(ctrip_accounts)")
        ctrip_columns = [c[1] for c in cursor.fetchall()]
        if "consecutive_task_count" not in ctrip_columns:
            cursor.execute("ALTER TABLE ctrip_accounts ADD COLUMN consecutive_task_count INTEGER DEFAULT 5")
            updated = True
        if "task_interval_max" not in ctrip_columns:
            cursor.execute("ALTER TABLE ctrip_accounts ADD COLUMN task_interval_max INTEGER DEFAULT 15")
            updated = True
        
        # 4. Update task_logs table with new columns
        cursor.execute("PRAGMA table_info(task_logs)")
        log_columns = [c[1] for c in cursor.fetchall()]
        if "operation_type" not in log_columns:
            print("Migrating: Adding operation_type to task_logs...")
            cursor.execute("ALTER TABLE task_logs ADD COLUMN operation_type TEXT")
            updated = True
        if "operation_details" not in log_columns:
            print("Migrating: Adding operation_details to task_logs...")
            cursor.execute("ALTER TABLE task_logs ADD COLUMN operation_details TEXT")
            updated = True
        
        # 5. Remove UNIQUE constraint from labor_account_id in environments table (legacy)
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='environments'")
        table_sql = cursor.fetchone()
        if table_sql and "labor_account_id INTEGER UNIQUE" in table_sql[0]:
            print("Migrating: Removing UNIQUE constraint from labor_account_id...")
            
            cursor.executescript("""
                CREATE TABLE environments_new (
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
                
                INSERT INTO environments_new (id, ctrip_account_id, labor_account_id, browser_profile_id, browser_type, proxy_ip_id, status, ws_endpoint, http_endpoint, pid, last_run_at, created_at)
                SELECT id, ctrip_account_id, labor_account_id, browser_profile_id, browser_type, proxy_ip_id, status, ws_endpoint, http_endpoint, pid, last_run_at, created_at FROM environments;
                
                DROP TABLE environments;
                ALTER TABLE environments_new RENAME TO environments;
                CREATE INDEX IF NOT EXISTS idx_env_status ON environments(status);
            """)
            updated = True
            print("✅ UNIQUE constraint removed from labor_account_id")
        
        if updated:
            conn.commit()
            print("✅ Database migration completed.")
        else:
            print("✨ Database is already up to date.")

    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Database management tool")
    parser.add_argument(
        "action", 
        choices=["init", "reset", "migrate"], 
        help="Action to perform: init (create if missing), reset (delete and recreate), migrate (apply schema updates)"
    )
    args = parser.parse_args()
    
    if args.action == "init":
        init_database()
    elif args.action == "reset":
        reset_database()
    elif args.action == "migrate":
        migrate_db()

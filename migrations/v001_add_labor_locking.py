"""Migration v001: Add labor account locking fields.

Adds fields to support labor account mutual exclusion during concurrent environment execution:
- locked_by_env_id: Environment ID that currently holds the lock
- locked_at: Timestamp when the lock was acquired
"""

import sqlite3

version = 1
description = "Add labor account locking fields for mutual exclusion"


def upgrade(conn: sqlite3.Connection) -> None:
    """Apply the migration."""
    cursor = conn.cursor()
    
    # Check existing columns
    cursor.execute("PRAGMA table_info(labor_accounts)")
    columns = [c[1] for c in cursor.fetchall()]
    
    # Add locked_by_env_id if missing
    if "locked_by_env_id" not in columns:
        print("   Adding locked_by_env_id column...")
        cursor.execute(
            "ALTER TABLE labor_accounts ADD COLUMN locked_by_env_id INTEGER DEFAULT NULL"
        )
    
    # Add locked_at if missing
    if "locked_at" not in columns:
        print("   Adding locked_at column...")
        cursor.execute(
            "ALTER TABLE labor_accounts ADD COLUMN locked_at TEXT DEFAULT NULL"
        )
    
    # Create index for faster lock queries
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_labor_locked ON labor_accounts(locked_by_env_id)"
    )
    
    conn.commit()

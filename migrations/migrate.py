"""Database migration manager.

Development-only tool for database schema migrations.
This module should NOT be packaged into the production application.

Usage:
    uv run python -m migrations.migrate [upgrade|current|history]
"""

import argparse
import importlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

# Import from src package for database path
from src.utils.paths import get_db_path


@dataclass
class MigrationInfo:
    """Migration information wrapper."""
    version: int
    description: str
    upgrade_fn: Callable[[sqlite3.Connection], None]
    
    def upgrade(self, conn: sqlite3.Connection) -> None:
        """Apply the migration."""
        self.upgrade_fn(conn)


def get_migrations_dir() -> Path:
    """Get the migrations directory path."""
    return Path(__file__).parent


def get_current_version(conn: sqlite3.Connection) -> int:
    """Get current database schema version."""
    try:
        cursor = conn.execute(
            "SELECT value FROM settings WHERE key = 'schema_version'"
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        # settings table doesn't exist yet
        return 0


def set_version(conn: sqlite3.Connection, version: int) -> None:
    """Set the database schema version."""
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('schema_version', ?)",
        (str(version),)
    )
    conn.commit()


def load_migrations() -> list[MigrationInfo]:
    """Load all migration modules from migrations directory."""
    migrations_dir = get_migrations_dir()
    migrations: list[MigrationInfo] = []
    
    for path in sorted(migrations_dir.glob("v*.py")):
        if path.name.startswith("__"):
            continue
        
        # Extract version from filename: v001_description.py -> 1
        version_str = path.stem.split("_")[0][1:]  # Remove 'v' prefix
        try:
            version = int(version_str)
        except ValueError:
            continue
        
        # Import module (now from migrations package, not src.db.migrations)
        module_name = f"migrations.{path.stem}"
        module = importlib.import_module(module_name)
        
        if hasattr(module, "upgrade"):
            info = MigrationInfo(
                version=version,
                description=getattr(module, "description", path.stem),
                upgrade_fn=module.upgrade,
            )
            migrations.append(info)
    
    return sorted(migrations, key=lambda m: m.version)


def upgrade(db_path: Path | None = None) -> None:
    """Run all pending migrations."""
    path = db_path or get_db_path()
    
    if not path.exists():
        print(f"❌ Database not found: {path}")
        print("   Run 'uv run python -m src.utils.init_db init' first.")
        return
    
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    
    try:
        current = get_current_version(conn)
        migrations = load_migrations()
        pending = [m for m in migrations if m.version > current]
        
        if not pending:
            print(f"✨ Database is up to date (version {current})")
            return
        
        print(f"📦 Current version: {current}")
        print(f"🔄 Pending migrations: {len(pending)}")
        
        for migration in pending:
            print(f"\n🚀 Applying v{migration.version:03d}: {migration.description}")
            try:
                migration.upgrade(conn)
                set_version(conn, migration.version)
                print("   ✅ Applied successfully")
            except Exception as e:
                conn.rollback()
                print(f"   ❌ Failed: {e}")
                raise
        
        print(f"\n✅ Database upgraded to version {pending[-1].version}")
        
    finally:
        conn.close()


def current(db_path: Path | None = None) -> None:
    """Show current database version."""
    path = db_path or get_db_path()
    
    if not path.exists():
        print(f"❌ Database not found: {path}")
        return
    
    conn = sqlite3.connect(path)
    try:
        version = get_current_version(conn)
        print(f"📦 Current schema version: {version}")
    finally:
        conn.close()


def history(db_path: Path | None = None) -> None:
    """Show all available migrations."""
    migrations = load_migrations()
    
    if not migrations:
        print("No migrations found.")
        return
    
    path = db_path or get_db_path()
    current_version = 0
    if path.exists():
        conn = sqlite3.connect(path)
        try:
            current_version = get_current_version(conn)
        finally:
            conn.close()
    
    print("📜 Migration History:")
    for m in migrations:
        status = "✅" if m.version <= current_version else "⏳"
        print(f"  {status} v{m.version:03d}: {m.description}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Database migration manager (development only)")
    parser.add_argument(
        "action",
        choices=["upgrade", "current", "history"],
        help="Action to perform"
    )
    args = parser.parse_args()
    
    if args.action == "upgrade":
        upgrade()
    elif args.action == "current":
        current()
    elif args.action == "history":
        history()

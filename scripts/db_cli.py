#!/usr/bin/env python
"""Database management CLI tool.

Development-only script for database initialization and reset.
This script should NOT be packaged into the production application.

Usage:
    uv run python scripts/db_cli.py [init|reset]
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.init_db import DB_PATH, init_database


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
    print(f"✅ Database reset complete: {path}")


def main():
    parser = argparse.ArgumentParser(description="Database management tool (development only)")
    parser.add_argument(
        "action", 
        choices=["init", "reset"], 
        help="Action to perform: init (create if missing), reset (delete and recreate)"
    )
    args = parser.parse_args()
    
    if args.action == "init":
        init_database()
        print(f"✅ Database initialized: {DB_PATH}")
    elif args.action == "reset":
        reset_database()


if __name__ == "__main__":
    main()

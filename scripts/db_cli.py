#!/usr/bin/env python
"""Development-only database management helper.

This script is intentionally kept at the workspace root because it is a
maintainer tool, not part of the publishable app package.

Usage:
    uv run python scripts/db_cli.py [init|reset]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j"
sys.path.insert(0, str(APP_ROOT))

def reset_database() -> None:
    """Delete framework database files and recreate schema."""
    from src.core.persistence.database import (
        CONFIG_DB,
        DATA_DB,
        STATE_DB,
        get_db_path,
        init_database,
    )

    for db_name in (CONFIG_DB, STATE_DB, DATA_DB):
        db_path = get_db_path(db_name)
        if db_path.exists():
            db_path.unlink()
            print(f"Deleted existing database: {db_path}")
    init_database()
    print("Database reset complete")


def main() -> None:
    from src.core.persistence.database import CONFIG_DB, get_db_path, init_database

    parser = argparse.ArgumentParser(description="Database management tool (development only)")
    parser.add_argument(
        "action",
        choices=["init", "reset"],
        help="Action to perform: init (create if missing), reset (delete and recreate)",
    )
    args = parser.parse_args()

    if args.action == "init":
        init_database()
        print(f"Database initialized: {get_db_path(CONFIG_DB).parent}")
    elif args.action == "reset":
        reset_database()


if __name__ == "__main__":
    main()

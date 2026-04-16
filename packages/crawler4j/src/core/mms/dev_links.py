"""开发链接模块存储。"""

from __future__ import annotations

import time
from pathlib import Path

from src.core.mms.models import DevModuleLink
from src.core.persistence.database import CONFIG_DB, get_connection


class DevModuleLinkStore:
    """持久化开发链接模块映射。"""

    def __init__(self):
        self._ensure_table()

    def _ensure_table(self) -> None:
        with get_connection(CONFIG_DB) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dev_module_links (
                    module_name TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )

    def upsert_link(self, module_name: str, source_path: str | Path) -> DevModuleLink:
        self._ensure_table()
        now = int(time.time())
        normalized = str(Path(source_path).expanduser().resolve())
        with get_connection(CONFIG_DB) as conn:
            conn.execute(
                """
                INSERT INTO dev_module_links (module_name, source_path, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(module_name) DO UPDATE SET
                    source_path = excluded.source_path,
                    updated_at = excluded.updated_at
                """,
                (module_name, normalized, now, now),
            )
        return self.get_link(module_name) or DevModuleLink(
            module_name=module_name,
            source_path=normalized,
            created_at=now,
            updated_at=now,
        )

    def get_link(self, module_name: str) -> DevModuleLink | None:
        self._ensure_table()
        with get_connection(CONFIG_DB) as conn:
            row = conn.execute(
                """
                SELECT module_name, source_path, created_at, updated_at
                FROM dev_module_links
                WHERE module_name = ?
                """,
                (module_name,),
            ).fetchone()
        if not row:
            return None
        return DevModuleLink(
            module_name=row["module_name"],
            source_path=row["source_path"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_links(self) -> list[DevModuleLink]:
        self._ensure_table()
        with get_connection(CONFIG_DB) as conn:
            rows = conn.execute(
                """
                SELECT module_name, source_path, created_at, updated_at
                FROM dev_module_links
                ORDER BY module_name ASC
                """
            ).fetchall()
        return [
            DevModuleLink(
                module_name=row["module_name"],
                source_path=row["source_path"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def delete_link(self, module_name: str) -> bool:
        self._ensure_table()
        with get_connection(CONFIG_DB) as conn:
            cursor = conn.execute(
                "DELETE FROM dev_module_links WHERE module_name = ?",
                (module_name,),
            )
        return cursor.rowcount > 0


_store: DevModuleLinkStore | None = None


def get_dev_module_link_store() -> DevModuleLinkStore:
    global _store
    if _store is None:
        _store = DevModuleLinkStore()
    return _store

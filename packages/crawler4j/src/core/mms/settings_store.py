"""MMS settings store.

规格参考: docs/02-requirements/reference-srs/05-framework-core/05-1-module-management.md (5.1.3.3)

负责：
    - 模块级 settings 的读写
    - 工作流级 settings 的读写
    - 模块启停状态的持久化
    - 模块 settings 的导出
"""

from __future__ import annotations

import json
import time
from typing import Any

from src.core.mms.models import ModuleStatus
from src.core.persistence.database import CONFIG_DB, get_connection


class ModuleSettingsStore:
    """MMS 设置存储。

    使用 `config.db` 的 `configs` 表承载持久化配置。
    """

    MODULE_SCOPE = "module"
    WORKFLOW_SCOPE = "workflow"
    MODULE_STATUS_SCOPE = "module_status"

    _PREFIXES = {
        MODULE_SCOPE: "mms:module_settings:",
        WORKFLOW_SCOPE: "mms:workflow_settings:",
        MODULE_STATUS_SCOPE: "mms:module_status:",
    }

    def _build_key(self, scope: str, key: str) -> str:
        prefix = self._PREFIXES.get(scope)
        if not prefix:
            raise ValueError(f"Unsupported settings scope: {scope}")
        return f"{prefix}{key}"

    def read_settings(self, scope: str, key: str) -> Any:
        """读取指定 scope/key 的设置。"""
        db_key = self._build_key(scope, key)
        with get_connection(CONFIG_DB) as conn:
            cursor = conn.execute("SELECT value FROM configs WHERE key = ?", (db_key,))
            row = cursor.fetchone()

        if row:
            return json.loads(row["value"])

        return None

    def write_settings(self, scope: str, key: str, value: Any) -> bool:
        """写入指定 scope/key 的设置。"""
        now = int(time.time())
        db_key = self._build_key(scope, key)
        payload = json.dumps(value, ensure_ascii=False)

        with get_connection(CONFIG_DB) as conn:
            conn.execute(
                """
                INSERT INTO configs (key, value, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (db_key, payload, now, now),
            )
        return True

    def delete_settings(self, scope: str, key: str) -> bool:
        """删除指定 scope/key 的设置。"""
        db_key = self._build_key(scope, key)
        with get_connection(CONFIG_DB) as conn:
            cursor = conn.execute("DELETE FROM configs WHERE key = ?", (db_key,))
            deleted = cursor.rowcount > 0

        return deleted

    def read_module_settings(self, module_name: str) -> dict[str, Any]:
        value = self.read_settings(self.MODULE_SCOPE, module_name)
        return value if isinstance(value, dict) else {}

    def write_module_settings(self, module_name: str, value: dict[str, Any]) -> bool:
        return self.write_settings(self.MODULE_SCOPE, module_name, value)

    def read_workflow_settings(self, module_name: str, workflow_name: str) -> dict[str, Any]:
        value = self.read_settings(self.WORKFLOW_SCOPE, f"{module_name}:{workflow_name}")
        return value if isinstance(value, dict) else {}

    def write_workflow_settings(
        self,
        module_name: str,
        workflow_name: str,
        value: dict[str, Any],
    ) -> bool:
        return self.write_settings(self.WORKFLOW_SCOPE, f"{module_name}:{workflow_name}", value)

    def list_workflow_settings(self, module_name: str) -> dict[str, dict[str, Any]]:
        prefix = self._build_key(self.WORKFLOW_SCOPE, f"{module_name}:")
        with get_connection(CONFIG_DB) as conn:
            cursor = conn.execute(
                "SELECT key, value FROM configs WHERE key LIKE ? ORDER BY key",
                (f"{prefix}%",),
            )
            rows = cursor.fetchall()

        workflows: dict[str, dict[str, Any]] = {}
        for row in rows:
            workflow_name = row["key"][len(prefix):]
            workflows[workflow_name] = json.loads(row["value"])
        return workflows

    def export_module_settings(self, module_name: str) -> dict[str, Any]:
        """导出模块 settings。"""
        return {
            "module": self.read_module_settings(module_name),
            "workflows": self.list_workflow_settings(module_name),
        }

    def get_module_status(self, module_name: str) -> ModuleStatus | None:
        value = self.read_settings(self.MODULE_STATUS_SCOPE, module_name)
        if not isinstance(value, str):
            return None

        try:
            status = ModuleStatus(value)
        except ValueError:
            return None

        if status in {ModuleStatus.ENABLED, ModuleStatus.DISABLED}:
            return status
        return None

    def set_module_status(self, module_name: str, status: ModuleStatus) -> bool:
        if status not in {ModuleStatus.ENABLED, ModuleStatus.DISABLED}:
            raise ValueError(f"Unsupported persisted module status: {status}")
        return self.write_settings(self.MODULE_STATUS_SCOPE, module_name, status.value)

    def clear_module_status(self, module_name: str) -> bool:
        return self.delete_settings(self.MODULE_STATUS_SCOPE, module_name)

    def clear_module_records(self, module_name: str, *, keep_settings: bool = False) -> bool:
        """清理模块相关持久化记录。"""
        changed = False

        if not keep_settings:
            changed = self.delete_settings(self.MODULE_SCOPE, module_name) or changed

            workflow_prefix = self._build_key(self.WORKFLOW_SCOPE, f"{module_name}:")
            with get_connection(CONFIG_DB) as conn:
                cursor = conn.execute(
                    "DELETE FROM configs WHERE key LIKE ?",
                    (f"{workflow_prefix}%",),
                )
                changed = cursor.rowcount > 0 or changed

        changed = self.clear_module_status(module_name) or changed
        return changed


_module_settings_store: ModuleSettingsStore | None = None


def get_module_settings_store() -> ModuleSettingsStore:
    global _module_settings_store
    if _module_settings_store is None:
        _module_settings_store = ModuleSettingsStore()
    return _module_settings_store

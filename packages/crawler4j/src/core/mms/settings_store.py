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


def _deep_merge_dict(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge_dict(result[key], value)
        else:
            result[key] = value
    return result


class ModuleSettingsStore:
    """MMS 设置存储。

    模块配置与工作流配置使用 `config.db.module_config_entries`
    做路径化持久化；不再读取或迁移旧 `mms:*` KV 兼容键。
    """

    MODULE_SCOPE = "module"
    WORKFLOW_SCOPE = "workflow"
    MODULE_STATUS_SCOPE = "module_status"

    def _infer_value_type(self, value: Any) -> str:
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int) and not isinstance(value, bool):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return type(value).__name__

    def _flatten_entries(self, value: dict[str, Any], *, prefix: str = "") -> list[tuple[str, Any, str]]:
        rows: list[tuple[str, Any, str]] = []
        for key, child in value.items():
            key_str = str(key).strip()
            if not key_str:
                continue
            key_path = f"{prefix}.{key_str}" if prefix else key_str
            if isinstance(child, dict):
                if child:
                    rows.extend(self._flatten_entries(child, prefix=key_path))
                else:
                    rows.append((key_path, {}, "object"))
                continue
            rows.append((key_path, child, self._infer_value_type(child)))
        return rows

    def _assign_nested(self, target: dict[str, Any], key_path: str, value: Any) -> None:
        parts = [part for part in key_path.split(".") if part]
        if not parts:
            return
        cursor = target
        for part in parts[:-1]:
            existing = cursor.get(part)
            if not isinstance(existing, dict):
                existing = {}
                cursor[part] = existing
            cursor = existing
        cursor[parts[-1]] = value

    def _rebuild_entries(self, rows: list[Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for row in rows:
            self._assign_nested(payload, row["key_path"], json.loads(row["value_json"]))
        return payload

    def _delete_scope_rows(self, module_name: str, scope: str, scope_name: str = "") -> int:
        with get_connection(CONFIG_DB) as conn:
            cursor = conn.execute(
                """
                DELETE FROM module_config_entries
                WHERE module_name = ? AND scope_type = ? AND scope_name = ?
                """,
                (module_name, scope, scope_name),
            )
            return cursor.rowcount or 0

    def _write_scope_rows(
        self,
        scope: str,
        module_name: str,
        scope_name: str,
        value: dict[str, Any],
    ) -> bool:
        now = int(time.time())
        rows = self._flatten_entries(value)
        with get_connection(CONFIG_DB) as conn:
            conn.execute(
                """
                DELETE FROM module_config_entries
                WHERE module_name = ? AND scope_type = ? AND scope_name = ?
                """,
                (module_name, scope, scope_name),
            )
            for key_path, raw_value, value_type in rows:
                conn.execute(
                    """
                    INSERT INTO module_config_entries (
                        module_name, scope_type, scope_name, key_path, value_json, value_type, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(module_name, scope_type, scope_name, key_path) DO UPDATE SET
                        value_json = excluded.value_json,
                        value_type = excluded.value_type,
                        updated_at = excluded.updated_at
                    """,
                    (
                        module_name,
                        scope,
                        scope_name,
                        key_path,
                        json.dumps(raw_value, ensure_ascii=False),
                        value_type,
                        now,
                        now,
                    ),
                )
        return True

    def _read_scope_rows(self, scope: str, module_name: str, scope_name: str = "") -> list[Any]:
        with get_connection(CONFIG_DB) as conn:
            cursor = conn.execute(
                """
                SELECT key_path, value_json, value_type
                FROM module_config_entries
                WHERE module_name = ? AND scope_type = ? AND scope_name = ?
                ORDER BY key_path
                """,
                (module_name, scope, scope_name),
            )
            return cursor.fetchall()

    def _read_scope_dict(self, scope: str, module_name: str, scope_name: str = "") -> dict[str, Any]:
        rows = self._read_scope_rows(scope, module_name, scope_name)
        return self._rebuild_entries(rows) if rows else {}

    def read_settings(self, scope: str, key: str) -> Any:
        """读取指定 scope/key 的设置。"""
        if scope == self.MODULE_SCOPE:
            return self.read_module_settings(key)
        if scope == self.WORKFLOW_SCOPE:
            module_name, _, workflow_name = key.partition(":")
            return self.read_workflow_settings(module_name, workflow_name)
        if scope == self.MODULE_STATUS_SCOPE:
            payload = self._read_scope_dict(self.MODULE_STATUS_SCOPE, key)
            value = payload.get("status")
            return value if isinstance(value, str) else None
        raise ValueError(f"Unsupported settings scope: {scope}")

    def write_settings(self, scope: str, key: str, value: Any) -> bool:
        """写入指定 scope/key 的设置。"""
        if scope == self.MODULE_SCOPE:
            if not isinstance(value, dict):
                raise ValueError("module settings must be a dict")
            return self.write_module_settings(key, value)
        if scope == self.WORKFLOW_SCOPE:
            if not isinstance(value, dict):
                raise ValueError("workflow settings must be a dict")
            module_name, _, workflow_name = key.partition(":")
            return self.write_workflow_settings(module_name, workflow_name, value)
        if scope == self.MODULE_STATUS_SCOPE:
            if not isinstance(value, str):
                raise ValueError("module status must be a string")
            return self._write_scope_rows(self.MODULE_STATUS_SCOPE, key, "", {"status": value})
        raise ValueError(f"Unsupported settings scope: {scope}")

    def delete_settings(self, scope: str, key: str) -> bool:
        """删除指定 scope/key 的设置。"""
        if scope == self.MODULE_SCOPE:
            return self._delete_scope_rows(scope=scope, module_name=key) > 0
        if scope == self.WORKFLOW_SCOPE:
            module_name, _, workflow_name = key.partition(":")
            return self._delete_scope_rows(scope=scope, module_name=module_name, scope_name=workflow_name) > 0
        if scope == self.MODULE_STATUS_SCOPE:
            return self._delete_scope_rows(scope=scope, module_name=key) > 0
        raise ValueError(f"Unsupported settings scope: {scope}")

    def read_module_settings(self, module_name: str) -> dict[str, Any]:
        return self._read_scope_dict(self.MODULE_SCOPE, module_name)

    def write_module_settings(self, module_name: str, value: dict[str, Any]) -> bool:
        return self._write_scope_rows(self.MODULE_SCOPE, module_name, "", value)

    def read_workflow_settings(self, module_name: str, workflow_name: str) -> dict[str, Any]:
        return self._read_scope_dict(self.WORKFLOW_SCOPE, module_name, workflow_name)

    def write_workflow_settings(
        self,
        module_name: str,
        workflow_name: str,
        value: dict[str, Any],
    ) -> bool:
        return self._write_scope_rows(self.WORKFLOW_SCOPE, module_name, workflow_name, value)

    def build_task_config(self, module_name: str, workflow_name: str = "") -> dict[str, Any]:
        module_settings = self.read_module_settings(module_name)
        if not workflow_name:
            return module_settings
        workflow_settings = self.read_workflow_settings(module_name, workflow_name)
        if not workflow_settings:
            return module_settings
        return _deep_merge_dict(module_settings, workflow_settings)

    def list_workflow_settings(self, module_name: str) -> dict[str, dict[str, Any]]:
        with get_connection(CONFIG_DB) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT scope_name
                FROM module_config_entries
                WHERE module_name = ? AND scope_type = ?
                ORDER BY scope_name
                """,
                (module_name, self.WORKFLOW_SCOPE),
            ).fetchall()

        workflows: dict[str, dict[str, Any]] = {}
        for row in rows:
            workflow_name = row["scope_name"]
            workflows[workflow_name] = self.read_workflow_settings(module_name, workflow_name)
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
            with get_connection(CONFIG_DB) as conn:
                cursor = conn.execute(
                    "DELETE FROM module_config_entries WHERE module_name = ?",
                    (module_name,),
                )
                changed = bool(cursor.rowcount) or changed
        else:
            changed = self.clear_module_status(module_name) or changed
        return changed


_module_settings_store: ModuleSettingsStore | None = None


def get_module_settings_store() -> ModuleSettingsStore:
    global _module_settings_store
    if _module_settings_store is None:
        _module_settings_store = ModuleSettingsStore()
    return _module_settings_store

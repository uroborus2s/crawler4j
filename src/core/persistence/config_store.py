"""配置存储服务。

规格参考: docs/srs/05-framework-core/05-9-data-persistence.md (5.9.2)

提供配置数据的读写能力，支持模块配置和全局设置。
"""

import json
import time
from typing import Any

from src.core.persistence.database import CONFIG_DB, get_connection


class ConfigStore:
    """配置存储服务。
    
    管理模块配置和全局设置。
    
    Example:
        >>> config = ConfigStore()
        >>> config.set_module_config("ctrip", {"account_pool": [...]})
        >>> ctrip_config = config.get_module_config("ctrip")
    """
    
    # === 模块配置 ===
    
    def get_module_config(self, module_name: str) -> dict[str, Any]:
        """获取模块配置。
        
        Args:
            module_name: 模块名。
        
        Returns:
            配置字典，若不存在返回空字典。
        """
        key = f"module:{module_name}:config"
        return self._get_config(key) or {}
    
    def set_module_config(self, module_name: str, config: dict[str, Any]) -> bool:
        """设置模块配置。
        
        Args:
            module_name: 模块名。
            config: 配置字典。
        
        Returns:
            是否设置成功。
        """
        key = f"module:{module_name}:config"
        return self._set_config(key, config)
    
    # === 全局设置 ===
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """获取全局设置。
        
        Args:
            key: 设置键名。
            default: 默认值。
        
        Returns:
            设置值或默认值。
        """
        with get_connection(CONFIG_DB) as conn:
            cursor = conn.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            
            if row:
                try:
                    return json.loads(row["value"])
                except json.JSONDecodeError:
                    return row["value"]
            return default
    
    def set_setting(self, key: str, value: Any) -> bool:
        """设置全局设置。
        
        Args:
            key: 设置键名。
            value: 设置值。
        
        Returns:
            是否设置成功。
        """
        now = int(time.time())
        value_json = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        
        with get_connection(CONFIG_DB) as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value_json, now)
            )
        return True
    
    # === 私有方法 ===
    
    def _get_config(self, key: str) -> dict[str, Any] | None:
        """获取配置。"""
        with get_connection(CONFIG_DB) as conn:
            cursor = conn.execute(
                "SELECT value FROM configs WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            
            if row:
                return json.loads(row["value"])
            return None
    
    def _set_config(self, key: str, value: dict[str, Any]) -> bool:
        """设置配置。"""
        now = int(time.time())
        value_json = json.dumps(value, ensure_ascii=False)
        
        with get_connection(CONFIG_DB) as conn:
            conn.execute(
                """
                INSERT INTO configs (key, value, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value_json, now, now)
            )
        return True


# 全局单例
_config_store: ConfigStore | None = None


def get_config_store() -> ConfigStore:
    """获取全局 ConfigStore 实例。"""
    global _config_store
    if _config_store is None:
        _config_store = ConfigStore()
    return _config_store

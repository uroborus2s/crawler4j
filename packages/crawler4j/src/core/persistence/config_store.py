"""配置存储服务。

规格参考: docs/02-requirements/reference-srs/05-framework-core/05-9-data-persistence.md (5.9.2)

提供系统设置的读写能力，使用 settings 表（一 key 一 value）。
模块配置已迁移到 kv_store。
"""

import time

from src.core.persistence.database import CONFIG_DB, get_connection


class ConfigStore:
    """配置存储服务。
    
    仅管理系统设置（settings 表）。
    模块配置请使用 kv_store。
    
    Example:
        >>> config = ConfigStore()
        >>> config.set_setting("browser.bitbrowser.port", "54345")
        >>> port = config.get_setting("browser.bitbrowser.port")
    """
    
    # === 系统设置 (settings 表) ===
    
    def get_setting(self, key: str) -> str | None:
        """获取系统设置值。
        
        Args:
            key: 设置键。
        
        Returns:
            设置值（JSON 字符串），若不存在返回 None。
        """
        with get_connection(CONFIG_DB) as conn:
            cursor = conn.execute(
                "SELECT value FROM settings WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            return row["value"] if row else None
    
    def set_setting(self, key: str, value: str) -> bool:
        """设置系统设置值。
        
        Args:
            key: 设置键。
            value: 设置值（应为 JSON 字符串）。
        
        Returns:
            是否设置成功。
        """
        now = int(time.time())
        with get_connection(CONFIG_DB) as conn:
            conn.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now)
            )
        return True
    
    def get_all_settings(self) -> dict[str, str]:
        """获取所有系统设置。
        
        Returns:
            key -> value 的字典。
        """
        with get_connection(CONFIG_DB) as conn:
            cursor = conn.execute("SELECT key, value FROM settings")
            return {row["key"]: row["value"] for row in cursor}


# 全局单例
_config_store: ConfigStore | None = None


def get_config_store() -> ConfigStore:
    """获取全局 ConfigStore 实例。"""
    global _config_store
    if _config_store is None:
        _config_store = ConfigStore()
    return _config_store

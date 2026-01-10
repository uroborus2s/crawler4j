"""KV Store 键值存储（支持 TTL）。

规格参考: docs/srs/05-framework-core/05-9-data-persistence.md (5.9.3)

提供运行时状态的键值存储能力，支持过期时间。
适用于: Cookies, Tokens, Session, 增量游标等。
"""

import json
import time
from typing import Any

from src.core.persistence.database import STATE_DB, get_connection


class KVStore:
    """键值存储服务。
    
    支持 TTL 的 KV 存储，用于运行时状态管理。
    
    Example:
        >>> kv = KVStore()
        >>> kv.set("account:user_a:cookies", {"session": "abc"}, ttl=86400)
        >>> cookies = kv.get("account:user_a:cookies")
    """
    
    def get(self, key: str) -> Any:
        """获取值。
        
        Args:
            key: 键名。
        
        Returns:
            JSON 反序列化后的值，若不存在或已过期返回 None。
        """
        now = int(time.time())
        
        with get_connection(STATE_DB) as conn:
            cursor = conn.execute(
                """
                SELECT value FROM kv_store 
                WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)
                """,
                (key, now)
            )
            row = cursor.fetchone()
            
            if row:
                return json.loads(row["value"])
            return None
    
    def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """设置值。
        
        Args:
            key: 键名。
            value: 值（必须 JSON 可序列化）。
            ttl: 过期时间（秒），None 表示永不过期。
        
        Returns:
            是否设置成功。
        """
        now = int(time.time())
        expires_at = now + ttl if ttl else None
        value_json = json.dumps(value, ensure_ascii=False)
        
        with get_connection(STATE_DB) as conn:
            conn.execute(
                """
                INSERT INTO kv_store (key, value, expires_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    expires_at = excluded.expires_at,
                    updated_at = excluded.updated_at
                """,
                (key, value_json, expires_at, now)
            )
        return True
    
    def delete(self, key: str) -> bool:
        """删除值。
        
        Args:
            key: 键名。
        
        Returns:
            是否删除成功。
        """
        with get_connection(STATE_DB) as conn:
            cursor = conn.execute("DELETE FROM kv_store WHERE key = ?", (key,))
            return cursor.rowcount > 0
    
    def exists(self, key: str) -> bool:
        """检查键是否存在且未过期。
        
        Args:
            key: 键名。
        
        Returns:
            是否存在。
        """
        return self.get(key) is not None
    
    def cleanup_expired(self) -> int:
        """清理过期的键。
        
        Returns:
            清理的键数量。
        """
        now = int(time.time())
        
        with get_connection(STATE_DB) as conn:
            cursor = conn.execute(
                "DELETE FROM kv_store WHERE expires_at IS NOT NULL AND expires_at <= ?",
                (now,)
            )
            return cursor.rowcount
    
    def keys(self, pattern: str = "%") -> list[str]:
        """列出匹配的键。
        
        Args:
            pattern: SQL LIKE 模式，默认匹配所有。
        
        Returns:
            键名列表。
        """
        now = int(time.time())
        
        with get_connection(STATE_DB) as conn:
            cursor = conn.execute(
                """
                SELECT key FROM kv_store 
                WHERE key LIKE ? AND (expires_at IS NULL OR expires_at > ?)
                """,
                (pattern, now)
            )
            return [row["key"] for row in cursor.fetchall()]


# 全局单例
_kv_store: KVStore | None = None


def get_kv_store() -> KVStore:
    """获取全局 KVStore 实例。"""
    global _kv_store
    if _kv_store is None:
        _kv_store = KVStore()
    return _kv_store

"""KV Store 单元测试。"""

import time
from unittest.mock import patch

import pytest


# 在导入前 mock 路径
@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    """为每个测试创建临时数据目录。"""
    with patch("src.utils.paths.get_app_data_dir", return_value=tmp_path):
        # 导入后初始化数据库
        from src.core.persistence.database import init_database
        init_database()
        yield tmp_path


class TestKVStore:
    """测试 KVStore。"""
    
    def test_set_and_get(self, temp_data_dir):
        """测试基本的 set/get。"""
        from src.core.persistence.kv_store import KVStore
        kv = KVStore()
        
        kv.set("test_key", {"foo": "bar"})
        result = kv.get("test_key")
        
        assert result == {"foo": "bar"}
    
    def test_get_nonexistent(self, temp_data_dir):
        """测试获取不存在的键。"""
        from src.core.persistence.kv_store import KVStore
        kv = KVStore()
        
        result = kv.get("nonexistent")
        
        assert result is None
    
    def test_set_with_ttl_not_expired(self, temp_data_dir):
        """测试 TTL 未过期。"""
        from src.core.persistence.kv_store import KVStore
        kv = KVStore()
        
        kv.set("ttl_key", "value", ttl=3600)  # 1小时后过期
        result = kv.get("ttl_key")
        
        assert result == "value"
    
    def test_set_with_ttl_expired(self, temp_data_dir):
        """测试 TTL 已过期。"""
        from src.core.persistence.kv_store import KVStore
        kv = KVStore()
        
        # 设置已过期的值（通过直接操作数据库）
        import json

        from src.core.persistence.database import STATE_DB, get_connection
        
        with get_connection(STATE_DB) as conn:
            conn.execute(
                "INSERT INTO kv_store (key, value, expires_at) VALUES (?, ?, ?)",
                ("expired_key", json.dumps("old_value"), int(time.time()) - 100)
            )
        
        result = kv.get("expired_key")
        
        assert result is None
    
    def test_delete(self, temp_data_dir):
        """测试删除。"""
        from src.core.persistence.kv_store import KVStore
        kv = KVStore()
        
        kv.set("to_delete", "value")
        assert kv.get("to_delete") == "value"
        
        result = kv.delete("to_delete")
        
        assert result is True
        assert kv.get("to_delete") is None
    
    def test_exists(self, temp_data_dir):
        """测试 exists。"""
        from src.core.persistence.kv_store import KVStore
        kv = KVStore()
        
        kv.set("exists_key", "value")
        
        assert kv.exists("exists_key") is True
        assert kv.exists("nonexistent") is False
    
    def test_update_existing(self, temp_data_dir):
        """测试更新已存在的键。"""
        from src.core.persistence.kv_store import KVStore
        kv = KVStore()
        
        kv.set("update_key", "old_value")
        kv.set("update_key", "new_value")
        
        result = kv.get("update_key")
        
        assert result == "new_value"
    
    def test_cleanup_expired(self, temp_data_dir):
        """测试清理过期键。"""
        import json

        from src.core.persistence.database import STATE_DB, get_connection
        from src.core.persistence.kv_store import KVStore
        
        kv = KVStore()
        
        # 插入已过期的键
        with get_connection(STATE_DB) as conn:
            conn.execute(
                "INSERT INTO kv_store (key, value, expires_at) VALUES (?, ?, ?)",
                ("expired1", json.dumps("v1"), int(time.time()) - 100)
            )
            conn.execute(
                "INSERT INTO kv_store (key, value, expires_at) VALUES (?, ?, ?)",
                ("expired2", json.dumps("v2"), int(time.time()) - 200)
            )
        
        count = kv.cleanup_expired()
        
        assert count >= 2  # 至少清理我们插入的 2 条
    
    def test_keys(self, temp_data_dir):
        """测试列出键。"""
        from src.core.persistence.kv_store import KVStore
        kv = KVStore()
        
        kv.set("prefix:a", "1")
        kv.set("prefix:b", "2")
        kv.set("other:c", "3")
        
        keys = kv.keys("prefix:%")
        
        assert sorted(keys) == ["prefix:a", "prefix:b"]

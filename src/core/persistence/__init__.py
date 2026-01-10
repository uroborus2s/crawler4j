"""数据持久化层。

规格参考: docs/srs/05-framework-core/05-9-data-persistence.md

导出:
    - init_database: 初始化数据库
    - get_connection: 获取数据库连接
    - KVStore / get_kv_store: KV 存储
    - ConfigStore / get_config_store: 配置存储
"""

from src.core.persistence.config_store import ConfigStore, get_config_store
from src.core.persistence.database import (
    CONFIG_DB,
    DATA_DB,
    STATE_DB,
    get_connection,
    get_db_path,
    init_database,
)
from src.core.persistence.kv_store import KVStore, get_kv_store

__all__ = [
    # 数据库
    "init_database",
    "get_connection",
    "get_db_path",
    "CONFIG_DB",
    "STATE_DB",
    "DATA_DB",
    # KV Store
    "KVStore",
    "get_kv_store",
    # Config Store
    "ConfigStore",
    "get_config_store",
]

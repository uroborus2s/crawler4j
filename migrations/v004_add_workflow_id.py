"""迁移 v004: 环境表添加 workflow_id 字段

用于绑定环境与任务链。
"""

import sqlite3


def migrate(conn: sqlite3.Connection) -> None:
    """执行迁移"""
    cursor = conn.cursor()
    
    # 检查列是否已存在
    cursor.execute("PRAGMA table_info(environments)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if "workflow_id" not in columns:
        cursor.execute("""
            ALTER TABLE environments 
            ADD COLUMN workflow_id TEXT DEFAULT NULL
        """)
        print("✅ 添加 environments.workflow_id 列")
    else:
        print("⏭️ environments.workflow_id 列已存在")
    
    conn.commit()


def rollback(conn: sqlite3.Connection) -> None:
    """回滚迁移（SQLite不支持DROP COLUMN，需重建表）"""
    print("⚠️ SQLite 不支持删除列，需手动重建表")

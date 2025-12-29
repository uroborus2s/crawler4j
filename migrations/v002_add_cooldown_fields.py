"""数据库迁移 v002: 添加API账号冷却期字段。

- environments.ctrip_login_at: 携程账号首次登录时间
- ctrip_accounts.registered_at: 账号注册时间
"""


def upgrade(conn):
    """执行迁移。"""
    cursor = conn.cursor()
    
    # 检查 environments.ctrip_login_at 是否存在
    cursor.execute("PRAGMA table_info(environments)")
    env_columns = [col[1] for col in cursor.fetchall()]
    
    if "ctrip_login_at" not in env_columns:
        cursor.execute("ALTER TABLE environments ADD COLUMN ctrip_login_at TEXT")
        print("✅ 添加 environments.ctrip_login_at 字段")
    else:
        print("⏭️ environments.ctrip_login_at 字段已存在")
    
    # 检查 ctrip_accounts.registered_at 是否存在
    cursor.execute("PRAGMA table_info(ctrip_accounts)")
    ctrip_columns = [col[1] for col in cursor.fetchall()]
    
    if "registered_at" not in ctrip_columns:
        cursor.execute("ALTER TABLE ctrip_accounts ADD COLUMN registered_at TEXT")
        print("✅ 添加 ctrip_accounts.registered_at 字段")
    else:
        print("⏭️ ctrip_accounts.registered_at 字段已存在")
    
    conn.commit()


def downgrade(conn):
    """回滚迁移（SQLite 不支持 DROP COLUMN）。"""
    print("⚠️ SQLite 不支持删除列，跳过回滚")

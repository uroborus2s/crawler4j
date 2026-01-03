"""数据库迁移 v003: 添加任务插件系统表。

新增表：
- task_templates: 任务模板表
- task_configs: 任务配置表
- task_flows: 任务流表
- environment_hooks: 环境生命周期钩子表
- environment_tasks: 环境关联任务表
"""


def upgrade(conn):
    """执行迁移。"""
    cursor = conn.cursor()

    # 1. 任务模板表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            display_name TEXT NOT NULL,
            description TEXT,
            plugin_type TEXT NOT NULL,
            default_config TEXT,
            is_system INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ 创建 task_templates 表")

    # 2. 任务配置表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            template_id INTEGER,
            config TEXT NOT NULL DEFAULT '{}',
            enabled INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (template_id) REFERENCES task_templates(id)
        )
    """)
    print("✅ 创建 task_configs 表")

    # 3. 任务流表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_flows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            flow_data TEXT NOT NULL DEFAULT '{}',
            enabled INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("✅ 创建 task_flows 表")

    # 4. 环境生命周期钩子表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS environment_hooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            environment_id INTEGER,
            hook_type TEXT NOT NULL,
            handler_type TEXT DEFAULT 'predefined',
            handler_code TEXT NOT NULL,
            priority INTEGER DEFAULT 0,
            enabled INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE
        )
    """)
    print("✅ 创建 environment_hooks 表")

    # 5. 环境关联任务表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS environment_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            environment_id INTEGER NOT NULL,
            task_flow_id INTEGER NOT NULL,
            priority INTEGER DEFAULT 0,
            FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE,
            FOREIGN KEY (task_flow_id) REFERENCES task_flows(id) ON DELETE CASCADE
        )
    """)
    print("✅ 创建 environment_tasks 表")

    # 6. 扩展 environments 表
    cursor.execute("PRAGMA table_info(environments)")
    env_columns = [col[1] for col in cursor.fetchall()]

    if "task_flow_id" not in env_columns:
        cursor.execute("ALTER TABLE environments ADD COLUMN task_flow_id INTEGER REFERENCES task_flows(id)")
        print("✅ 添加 environments.task_flow_id 字段")

    if "hooks_enabled" not in env_columns:
        cursor.execute("ALTER TABLE environments ADD COLUMN hooks_enabled INTEGER DEFAULT 1")
        print("✅ 添加 environments.hooks_enabled 字段")

    # 7. 创建索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_configs_template ON task_configs(template_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_env_hooks_env ON environment_hooks(environment_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_env_hooks_type ON environment_hooks(hook_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_env_tasks_env ON environment_tasks(environment_id)")
    print("✅ 创建索引")

    # 8. 插入默认携程任务模板
    cursor.execute("""
        INSERT OR IGNORE INTO task_templates (name, display_name, description, plugin_type, is_system, default_config)
        VALUES (
            'ctrip_hotel_collect',
            '携程酒店采集',
            '携程酒店房型数据采集任务，配合劳保平台使用',
            'ctrip_task',
            1,
            '{"max_consecutive_tasks": 10, "task_interval_min": 1, "task_interval_max": 5}'
        )
    """)
    print("✅ 插入默认携程任务模板")

    conn.commit()


def downgrade(conn):
    """回滚迁移。"""
    cursor = conn.cursor()

    # 删除表（按依赖顺序）
    cursor.execute("DROP TABLE IF EXISTS environment_tasks")
    cursor.execute("DROP TABLE IF EXISTS environment_hooks")
    cursor.execute("DROP TABLE IF EXISTS task_flows")
    cursor.execute("DROP TABLE IF EXISTS task_configs")
    cursor.execute("DROP TABLE IF EXISTS task_templates")

    print("✅ 已删除任务插件系统相关表")
    conn.commit()

"""任务插件系统Repository类。

提供任务模板、任务配置、任务流、Hooks的数据库操作。
"""

import json

from src.utils.storage import BaseRepository, get_connection


class TaskTemplateRepository(BaseRepository):
    """任务模板表操作。"""

    table_name = "task_templates"

    def create(
        self,
        name: str,
        display_name: str,
        plugin_type: str,
        description: str = "",
        default_config: dict | None = None,
        is_system: bool = False,
    ) -> int:
        """创建任务模板。"""
        config_json = json.dumps(default_config or {}, ensure_ascii=False)
        return self._execute_write(
            """INSERT INTO task_templates 
               (name, display_name, description, plugin_type, default_config, is_system)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, display_name, description, plugin_type, config_json, 1 if is_system else 0),
        )

    def get_by_name(self, name: str) -> dict | None:
        """根据名称获取模板。"""
        row = self._execute_one(
            "SELECT * FROM task_templates WHERE name = ?", (name,)
        )
        return dict(row) if row else None

    def get_enabled(self) -> list[dict]:
        """获取所有模板。"""
        rows = self._execute("SELECT * FROM task_templates ORDER BY is_system DESC, name")
        return [dict(row) for row in rows]

    def update(self, id: int, data: dict) -> bool:
        """更新模板。"""
        if not data:
            return False
        if "default_config" in data and isinstance(data["default_config"], dict):
            data["default_config"] = json.dumps(data["default_config"], ensure_ascii=False)
        
        columns = list(data.keys())
        set_clause = ", ".join([f"{col} = ?" for col in columns])
        values = list(data.values())
        values.append(id)

        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE task_templates SET {set_clause} WHERE id = ?",
                tuple(values),
            )
            conn.commit()
            return cursor.rowcount > 0


class TaskConfigRepository(BaseRepository):
    """任务配置表操作。"""

    table_name = "task_configs"

    def create(
        self,
        name: str,
        template_id: int | None = None,
        config: dict | None = None,
        enabled: bool = True,
    ) -> int:
        """创建任务配置。"""
        config_json = json.dumps(config or {}, ensure_ascii=False)
        return self._execute_write(
            """INSERT INTO task_configs (name, template_id, config, enabled)
               VALUES (?, ?, ?, ?)""",
            (name, template_id, config_json, 1 if enabled else 0),
        )

    def get_enabled(self) -> list[dict]:
        """获取所有启用的配置。"""
        rows = self._execute(
            "SELECT * FROM task_configs WHERE enabled = 1 ORDER BY name"
        )
        return [dict(row) for row in rows]

    def get_with_template(self, id: int) -> dict | None:
        """获取配置及其关联的模板信息。"""
        row = self._execute_one(
            """SELECT tc.*, tt.name as template_name, tt.plugin_type
               FROM task_configs tc
               LEFT JOIN task_templates tt ON tc.template_id = tt.id
               WHERE tc.id = ?""",
            (id,),
        )
        return dict(row) if row else None

    def update(self, id: int, data: dict) -> bool:
        """更新配置。"""
        if not data:
            return False
        if "config" in data and isinstance(data["config"], dict):
            data["config"] = json.dumps(data["config"], ensure_ascii=False)

        columns = list(data.keys())
        set_clause = ", ".join([f"{col} = ?" for col in columns])
        values = list(data.values())
        values.append(id)

        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE task_configs SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                tuple(values),
            )
            conn.commit()
            return cursor.rowcount > 0


class TaskFlowRepository(BaseRepository):
    """任务流表操作。"""

    table_name = "task_flows"

    def create(
        self,
        name: str,
        description: str = "",
        flow_data: dict | None = None,
        enabled: bool = True,
    ) -> int:
        """创建任务流。"""
        flow_json = json.dumps(flow_data or {"nodes": [], "start_node_id": None}, ensure_ascii=False)
        return self._execute_write(
            """INSERT INTO task_flows (name, description, flow_data, enabled)
               VALUES (?, ?, ?, ?)""",
            (name, description, flow_json, 1 if enabled else 0),
        )

    def get_by_name(self, name: str) -> dict | None:
        """根据名称获取任务流。"""
        row = self._execute_one(
            "SELECT * FROM task_flows WHERE name = ?", (name,)
        )
        return dict(row) if row else None

    def get_enabled(self) -> list[dict]:
        """获取所有启用的任务流。"""
        rows = self._execute(
            "SELECT * FROM task_flows WHERE enabled = 1 ORDER BY name"
        )
        return [dict(row) for row in rows]

    def update(self, id: int, data: dict) -> bool:
        """更新任务流。"""
        if not data:
            return False
        if "flow_data" in data and isinstance(data["flow_data"], dict):
            data["flow_data"] = json.dumps(data["flow_data"], ensure_ascii=False)

        columns = list(data.keys())
        set_clause = ", ".join([f"{col} = ?" for col in columns])
        values = list(data.values())
        values.append(id)

        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE task_flows SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                tuple(values),
            )
            conn.commit()
            return cursor.rowcount > 0


class EnvironmentHooksRepository(BaseRepository):
    """环境Hooks表操作。"""

    table_name = "environment_hooks"

    def create(
        self,
        hook_type: str,
        handler_code: str,
        environment_id: int | None = None,
        handler_type: str = "predefined",
        priority: int = 0,
        enabled: bool = True,
    ) -> int:
        """创建Hook。"""
        return self._execute_write(
            """INSERT INTO environment_hooks 
               (environment_id, hook_type, handler_type, handler_code, priority, enabled)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (environment_id, hook_type, handler_type, handler_code, priority, 1 if enabled else 0),
        )

    def get_by_environment(self, environment_id: int | None) -> list[dict]:
        """获取指定环境的Hooks（包括全局Hooks）。"""
        if environment_id is None:
            # 仅获取全局Hooks
            rows = self._execute(
                """SELECT * FROM environment_hooks 
                   WHERE environment_id IS NULL AND enabled = 1
                   ORDER BY priority DESC"""
            )
        else:
            # 获取全局Hooks + 环境特定Hooks
            rows = self._execute(
                """SELECT * FROM environment_hooks 
                   WHERE (environment_id IS NULL OR environment_id = ?) AND enabled = 1
                   ORDER BY priority DESC""",
                (environment_id,),
            )
        return [dict(row) for row in rows]

    def get_by_type(self, hook_type: str, environment_id: int | None = None) -> list[dict]:
        """获取指定类型的Hooks。"""
        if environment_id is None:
            rows = self._execute(
                """SELECT * FROM environment_hooks 
                   WHERE hook_type = ? AND environment_id IS NULL AND enabled = 1
                   ORDER BY priority DESC""",
                (hook_type,),
            )
        else:
            rows = self._execute(
                """SELECT * FROM environment_hooks 
                   WHERE hook_type = ? AND (environment_id IS NULL OR environment_id = ?) AND enabled = 1
                   ORDER BY priority DESC""",
                (hook_type, environment_id),
            )
        return [dict(row) for row in rows]

    def update(self, id: int, data: dict) -> bool:
        """更新Hook。"""
        if not data:
            return False

        columns = list(data.keys())
        set_clause = ", ".join([f"{col} = ?" for col in columns])
        values = list(data.values())
        values.append(id)

        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE environment_hooks SET {set_clause} WHERE id = ?",
                tuple(values),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_by_environment(self, environment_id: int) -> int:
        """删除指定环境的所有Hooks。"""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM environment_hooks WHERE environment_id = ?",
                (environment_id,),
            )
            conn.commit()
            return cursor.rowcount


class EnvironmentTasksRepository(BaseRepository):
    """环境关联任务表操作。"""

    table_name = "environment_tasks"

    def create(self, environment_id: int, task_flow_id: int, priority: int = 0) -> int:
        """创建环境任务关联。"""
        return self._execute_write(
            "INSERT INTO environment_tasks (environment_id, task_flow_id, priority) VALUES (?, ?, ?)",
            (environment_id, task_flow_id, priority),
        )

    def get_by_environment(self, environment_id: int) -> list[dict]:
        """获取环境关联的任务流。"""
        rows = self._execute(
            """SELECT et.*, tf.name as flow_name, tf.description, tf.flow_data
               FROM environment_tasks et
               JOIN task_flows tf ON et.task_flow_id = tf.id
               WHERE et.environment_id = ? AND tf.enabled = 1
               ORDER BY et.priority DESC""",
            (environment_id,),
        )
        return [dict(row) for row in rows]

    def delete_by_environment(self, environment_id: int) -> int:
        """删除环境的所有任务关联。"""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM environment_tasks WHERE environment_id = ?",
                (environment_id,),
            )
            conn.commit()
            return cursor.rowcount

    def set_environment_flow(self, environment_id: int, task_flow_id: int) -> bool:
        """设置环境的任务流（替换现有关联）。"""
        with get_connection(self.db_path) as conn:
            # 删除现有关联
            conn.execute(
                "DELETE FROM environment_tasks WHERE environment_id = ?",
                (environment_id,),
            )
            # 创建新关联
            conn.execute(
                "INSERT INTO environment_tasks (environment_id, task_flow_id) VALUES (?, ?)",
                (environment_id, task_flow_id),
            )
            conn.commit()
            return True

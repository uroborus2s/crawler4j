"""任务仓库（持久化）。

规格参考: docs/srs/05-framework-core/05-4-automation-task-management.md (5.4.4)

负责：
    - 任务配置 (AutomationTask) 的 CRUD
    - 任务运行历史 (TaskRun) 的 CRUD
"""

import asyncio
import json
from typing import Any

from src.core.atm.models import AutomationTask, TaskResult, TaskRun, TaskStatus

# from src.core.foundation.logging import logger  # Removed unused import
from src.core.persistence.database import STATE_DB, get_connection


class TaskRepository:
    """任务仓库。
    
    管理 `automation_tasks` 和 `task_runs` 两张表。
    """
    
    async def _run_async(self, func, *args):
        """Run synchronous DB operation in thread pool."""
        return await asyncio.get_running_loop().run_in_executor(None, func, *args)

    def __init__(self):
        self._ensure_tables()

    def _ensure_tables(self):
        """确保表存在。"""
        with get_connection(STATE_DB) as conn:
            # 1. 任务配置表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS automation_tasks (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    strategy_id TEXT,
                    cron_expression TEXT,
                    default_params TEXT,
                    created_at INTEGER,
                    updated_at INTEGER
                )
            """)
            
            # 2. 任务运行表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_runs (
                    id TEXT PRIMARY KEY,
                    task_id TEXT,
                    status TEXT,
                    trigger_type TEXT,
                    env_id TEXT,
                    result TEXT,
                    error TEXT,
                    start_time INTEGER,
                    end_time INTEGER,
                    FOREIGN KEY(task_id) REFERENCES automation_tasks(id)
                )
            """)

    # === AutomationTask Methods ===
    
    async def save_task(self, task: AutomationTask) -> None:
        """保存任务配置。"""
        def _do():
            with get_connection(STATE_DB) as conn:
                conn.execute(
                    """
                    INSERT INTO automation_tasks (id, name, strategy_id, cron_expression, default_params, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        strategy_id = excluded.strategy_id,
                        cron_expression = excluded.cron_expression,
                        default_params = excluded.default_params,
                        updated_at = excluded.updated_at
                    """,
                    (
                        task.id,
                        task.name,
                        task.strategy_id,
                        task.cron_expression,
                        json.dumps(task.default_params, ensure_ascii=False),
                        task.created_at,
                        task.updated_at,
                    )
                )
        await self._run_async(_do)

    async def get_task(self, task_id: str) -> AutomationTask | None:
        """获取任务配置。"""
        def _do():
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute("SELECT * FROM automation_tasks WHERE id = ?", (task_id,))
                row = cursor.fetchone()
                if row:
                    return self._row_to_automation_task(row)
                return None
        return await self._run_async(_do)

    async def list_tasks(self) -> list[AutomationTask]:
        """列出所有任务配置。"""
        def _do():
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute("SELECT * FROM automation_tasks ORDER BY created_at DESC")
                return [self._row_to_automation_task(row) for row in cursor.fetchall()]
        return await self._run_async(_do)

    async def delete_task(self, task_id: str) -> bool:
        """删除任务配置。"""
        def _do():
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute("DELETE FROM automation_tasks WHERE id = ?", (task_id,))
                return cursor.rowcount > 0
        return await self._run_async(_do)

    # === TaskRun Methods ===

    async def save_run(self, run: TaskRun) -> None:
        """保存运行记录。"""
        def _do():
            with get_connection(STATE_DB) as conn:
                conn.execute(
                    """
                    INSERT INTO task_runs (id, task_id, status, trigger_type, env_id, result, error, start_time, end_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        status = excluded.status,
                        env_id = excluded.env_id,
                        result = excluded.result,
                        error = excluded.error,
                        start_time = excluded.start_time,
                        end_time = excluded.end_time
                    """,
                    (
                        run.id,
                        run.task_id,
                        run.status.value,
                        run.trigger_type,
                        run.env_id,
                        json.dumps(run.result.to_dict(), ensure_ascii=False) if run.result else None,
                        run.error,
                        run.start_time,
                        run.end_time,
                    )
                )
        await self._run_async(_do)

    async def get_run(self, run_id: str) -> TaskRun | None:
        """获取运行记录。"""
        def _do():
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute("SELECT * FROM task_runs WHERE id = ?", (run_id,))
                row = cursor.fetchone()
                if row:
                    return self._row_to_task_run(row)
                return None
        return await self._run_async(_do)

    async def list_runs_by_task(self, task_id: str, limit: int = 50) -> list[TaskRun]:
        """获取指定任务的运行历史。"""
        def _do():
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute(
                    "SELECT * FROM task_runs WHERE task_id = ? ORDER BY start_time DESC LIMIT ?",
                    (task_id, limit)
                )
                return [self._row_to_task_run(row) for row in cursor.fetchall()]
        return await self._run_async(_do)

    
    async def list_runs_by_status(self, status: TaskStatus) -> list[TaskRun]:
        """按状态列出运行记录。"""
        def _do():
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute(
                    "SELECT * FROM task_runs WHERE status = ?",
                    (status.value,)
                )
                return [self._row_to_task_run(row) for row in cursor.fetchall()]
        return await self._run_async(_do)

    async def list_recent_runs(self, limit: int = 50) -> list[TaskRun]:
        """获取最近的所有运行记录。"""
        def _do():
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute(
                    "SELECT * FROM task_runs ORDER BY start_time DESC LIMIT ?",
                    (limit,)
                )
                return [self._row_to_task_run(row) for row in cursor.fetchall()]
        return await self._run_async(_do)
    
    async def get_last_run(self, task_id: str) -> TaskRun | None:
        """获取任务的最后一次运行记录。"""
        # list_runs_by_task is now async
        runs = await self.list_runs_by_task(task_id, limit=1)
        return runs[0] if runs else None

    # === Helpers ===

    def _row_to_automation_task(self, row: Any) -> AutomationTask:
        params_data = row["default_params"]
        params = json.loads(params_data) if params_data else {}
        return AutomationTask(
            id=row["id"],
            name=row["name"],
            strategy_id=row["strategy_id"],
            cron_expression=row["cron_expression"],
            default_params=params,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_task_run(self, row: Any) -> TaskRun:
        result_data = row["result"]
        result = TaskResult.from_dict(json.loads(result_data)) if result_data else None
        
        return TaskRun(
            id=row["id"],
            task_id=row["task_id"],
            status=TaskStatus(row["status"]),
            trigger_type=row["trigger_type"],
            env_id=row["env_id"],
            result=result,
            error=row["error"],
            start_time=row["start_time"],
            end_time=row["end_time"],
        )


# 全局单例
_repository: TaskRepository | None = None


def get_task_repository() -> TaskRepository:
    """获取全局 TaskRepository 实例。"""
    global _repository
    if _repository is None:
        _repository = TaskRepository()
    return _repository

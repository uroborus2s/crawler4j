"""任务仓库（持久化）。

规格参考: docs/srs/05-framework-core/05-4-automation-task-management.md (5.4.4)

负责：
    - 任务状态变更实时写入 SQLite
    - 任务查询与列表
    - 崩溃恢复
"""

import json
from typing import Any

from src.core.atm.models import TaskInstance, TaskResult, TaskStatus
from src.core.foundation.logging import logger
from src.core.persistence.database import STATE_DB, get_connection


class TaskRepository:
    """任务仓库。
    
    规格 5.4.4: 任务状态变更实时写入存储。
    """
    
    def save(self, task: TaskInstance) -> None:
        """保存任务（插入或更新）。"""
        with get_connection(STATE_DB) as conn:
            conn.execute(
                """
                INSERT INTO tasks (id, module, workflow, name, status, params, result, error, env_id, created_at, started_at, ended_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    result = excluded.result,
                    error = excluded.error,
                    env_id = excluded.env_id,
                    started_at = excluded.started_at,
                    ended_at = excluded.ended_at
                """,
                (
                    task.id,
                    task.module,
                    task.workflow,
                    task.name,
                    task.status.value,
                    json.dumps(task.params, ensure_ascii=False),
                    json.dumps(task.result.to_dict(), ensure_ascii=False) if task.result else None,
                    task.error,
                    task.env_id,
                    task.created_at,
                    task.started_at,
                    task.ended_at,
                )
            )
    
    def get(self, task_id: str) -> TaskInstance | None:
        """获取任务。"""
        with get_connection(STATE_DB) as conn:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return self._row_to_task(row)
            return None
    
    def list_by_status(self, status: TaskStatus) -> list[TaskInstance]:
        """按状态列出任务。"""
        with get_connection(STATE_DB) as conn:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
                (status.value,)
            )
            return [self._row_to_task(row) for row in cursor.fetchall()]
    
    def list_by_module(self, module_name: str, limit: int = 100) -> list[TaskInstance]:
        """按模块列出任务。"""
        with get_connection(STATE_DB) as conn:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE module = ? ORDER BY created_at DESC LIMIT ?",
                (module_name, limit)
            )
            return [self._row_to_task(row) for row in cursor.fetchall()]
    
    def list_recent(self, limit: int = 50) -> list[TaskInstance]:
        """列出最近的任务。"""
        with get_connection(STATE_DB) as conn:
            cursor = conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                (limit,)
            )
            return [self._row_to_task(row) for row in cursor.fetchall()]
    
    def delete(self, task_id: str) -> bool:
        """删除任务。"""
        with get_connection(STATE_DB) as conn:
            cursor = conn.execute(
                "DELETE FROM tasks WHERE id = ?",
                (task_id,)
            )
            return cursor.rowcount > 0
    
    def count_by_status(self, status: TaskStatus) -> int:
        """按状态统计任务数量。"""
        with get_connection(STATE_DB) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as cnt FROM tasks WHERE status = ?",
                (status.value,)
            )
            row = cursor.fetchone()
            return row["cnt"] if row else 0
    
    def recover_interrupted(self) -> list[TaskInstance]:
        """恢复中断的任务（崩溃恢复）。
        
        规格 5.4.3 FR-ATM-004:
            系统重启时，检查处于 RUNNING 状态的任务，标记为 INTERRUPTED。
        """
        interrupted = []
        
        with get_connection(STATE_DB) as conn:
            # 查找正在运行的任务
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE status = ?",
                (TaskStatus.RUNNING.value,)
            )
            
            for row in cursor.fetchall():
                task = self._row_to_task(row)
                task.status = TaskStatus.INTERRUPTED
                self.save(task)
                interrupted.append(task)
                logger.warning(f"[ATM] 恢复中断任务: {task.id[:8]}...")
        
        return interrupted
    
    def _row_to_task(self, row: Any) -> TaskInstance:
        """将数据库行转换为 TaskInstance。"""
        result_data = row["result"]
        result = TaskResult.from_dict(json.loads(result_data)) if result_data else None
        
        params_data = row["params"]
        params = json.loads(params_data) if params_data else {}
        
        return TaskInstance(
            id=row["id"],
            module=row["module"],
            workflow=row["workflow"] or "",
            name=row["name"],
            status=TaskStatus(row["status"]),
            params=params,
            result=result,
            error=row["error"] or "",
            env_id=row["env_id"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
        )


# 全局单例
_repository: TaskRepository | None = None


def get_task_repository() -> TaskRepository:
    """获取全局 TaskRepository 实例。"""
    global _repository
    if _repository is None:
        _repository = TaskRepository()
    return _repository

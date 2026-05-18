"""ATM 持久化层 (V2)。

规格参考: docs/03-solution/reference-design/task-engine-v2.md

负责:
    - Job (作业配置) CRUD
    - Task (运行实例) CRUD
    - 原子化资源抢占 (Atomic Leasing)
"""

import asyncio
import json
import time
from typing import Any, List

from src.core.atm.models import Job, JobState, JobType, Task, TaskStatus, TriggerConfig
from src.core.atm.run_profile import RunProfile
from src.core.persistence.database import STATE_DB, get_connection, get_db_path


class TaskRepository:
    """Task Engine V2 Repository."""

    def __init__(self):
        self._db_path = str(get_db_path(STATE_DB))
        self._ensure_tables()

    async def _run_async(self, func, *args):
        return await asyncio.get_running_loop().run_in_executor(None, func, *args)

    def _ensure_tables(self):
        """初始化 V2 表结构。"""
        with get_connection(STATE_DB) as conn:
            # 1. Jobs 表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    run_profile_json TEXT,
                    trigger_config TEXT,
                    concurrency_target INTEGER,
                    params TEXT,
                    state TEXT,
                    created_at INTEGER,
                    updated_at INTEGER
                )
            """)
            existing_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "run_profile_json" not in existing_columns:
                conn.execute("ALTER TABLE jobs ADD COLUMN run_profile_json TEXT")
            
            # 2. Tasks 表 (因 SQLite 无 FOR UPDATE SKIP LOCKED，需依赖单线程写入或应用层锁保证安全)
            # 但在此架构中，Task 创建通常由 Controller 发起，写入量尚可接受。
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    job_id TEXT,
                    status TEXT,
                    env_id TEXT,
                    lease_id TEXT,
                    result TEXT,
                    error TEXT,
                    created_at INTEGER,
                    waiting_since INTEGER,
                    started_at INTEGER,
                    finished_at INTEGER,
                    FOREIGN KEY(job_id) REFERENCES jobs(id)
                )
            """)
            task_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(tasks)").fetchall()
            }
            if "waiting_since" not in task_columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN waiting_since INTEGER")
                conn.execute(
                    """
                    UPDATE tasks
                    SET waiting_since = CAST(strftime('%s', 'now') AS INTEGER)
                    WHERE waiting_since IS NULL
                      AND status = ?
                      AND result LIKE ?
                    """,
                    (TaskStatus.PENDING.value, "等待环境池工位:%"),
                )
            
            # 索引优化 (用于 Controller 查询)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_job_status ON tasks(job_id, status)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_job_status_waiting_since ON tasks(job_id, status, waiting_since)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state)")

    # =========================================================================
    # Job CRUD
    # =========================================================================

    async def save_job(self, job: Job) -> None:
        def _do():
            with get_connection(STATE_DB) as conn:
                conn.execute(
                    """
                    INSERT INTO jobs (id, name, type, run_profile_json, trigger_config, concurrency_target, params, state, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        name = excluded.name,
                        type = excluded.type,
                        run_profile_json = excluded.run_profile_json,
                        trigger_config = excluded.trigger_config,
                        concurrency_target = excluded.concurrency_target,
                        params = excluded.params,
                        state = excluded.state,
                        updated_at = excluded.updated_at
                    """,
                    (
                        job.id, item_or_empty(job.name), job.type.value,
                        json.dumps(job.run_profile.model_dump(mode="json"), ensure_ascii=False) if job.run_profile else "",
                        json.dumps(job.trigger.to_dict()), job.concurrency_target,
                        json.dumps(job.params), job.state.value,
                        job.created_at, job.updated_at
                    )
                )
        await self._run_async(_do)

    async def get_job(self, job_id: str) -> Job | None:
        def _do():
            with get_connection(STATE_DB) as conn:
                row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
                return self._row_to_job(conn, row) if row else None
        return await self._run_async(_do)

    async def list_jobs(self) -> List[Job]:
        def _do():
            with get_connection(STATE_DB) as conn:
                # 默认按创建时间倒序
                cursor = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC")
                return [self._row_to_job(conn, row) for row in cursor.fetchall()]
        return await self._run_async(_do)
    
    async def list_active_jobs(self) -> List[Job]:
        """获取所有激活状态的 Job (供 Controller 使用)。"""
        def _do():
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute("SELECT * FROM jobs WHERE state = ?", (JobState.ACTIVE.value,))
                return [self._row_to_job(conn, row) for row in cursor.fetchall()]
        return await self._run_async(_do)

    async def delete_job(self, job_id: str) -> None:
        def _do():
            with get_connection(STATE_DB) as conn:
                # tasks.job_id -> jobs.id 存在外键约束，先删 task 再删 job
                conn.execute("DELETE FROM tasks WHERE job_id = ?", (job_id,))
                conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
        await self._run_async(_do)

    # =========================================================================
    # Task CRUD
    # =========================================================================

    async def save_task(self, task: Task) -> None:
        def _do():
            waiting_since = task.waiting_since if task.status == TaskStatus.PENDING else None
            with get_connection(STATE_DB) as conn:
                conn.execute(
                    """
                    INSERT INTO tasks (
                        id,
                        job_id,
                        status,
                        env_id,
                        lease_id,
                        result,
                        error,
                        created_at,
                        waiting_since,
                        started_at,
                        finished_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        status = excluded.status,
                        env_id = excluded.env_id,
                        lease_id = excluded.lease_id,
                        result = excluded.result,
                        error = excluded.error,
                        waiting_since = excluded.waiting_since,
                        started_at = excluded.started_at,
                        finished_at = excluded.finished_at
                    """,
                    (
                        task.id, task.job_id, task.status.value, task.env_id, task.lease_id,
                        task.message, task.error,
                        task.created_at, waiting_since, task.started_at, task.finished_at
                    )
                )
        await self._run_async(_do)

    async def get_task(self, task_id: str) -> Task | None:
        def _do():
            with get_connection(STATE_DB) as conn:
                row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
                return self._row_to_task(row) if row else None
        return await self._run_async(_do)
        
    async def list_tasks_by_job(self, job_id: str, limit: int = 100) -> List[Task]:
        def _do():
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute(
                    "SELECT * FROM tasks WHERE job_id = ? ORDER BY created_at DESC LIMIT ?", 
                    (job_id, limit)
                )
                return [self._row_to_task(row) for row in cursor.fetchall()]
        return await self._run_async(_do)

    async def count_active_tasks(self, job_id: str) -> int:
        """统计某 Job 的活跃任务数。"""
        def _do():
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE job_id = ? AND status IN (?, ?)",
                    (
                        job_id,
                        TaskStatus.PENDING.value,
                        TaskStatus.RUNNING.value,
                    )
                )
                return cursor.fetchone()[0]
        return await self._run_async(_do)
    
    async def get_oldest_active_tasks(self, job_id: str, limit: int) -> List[Task]:
        """获取最老的活跃任务 (用于缩容)。"""
        def _do():
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute(
                    "SELECT * FROM tasks WHERE job_id = ? AND status IN (?, ?) ORDER BY created_at ASC LIMIT ?",
                    (
                        job_id,
                        TaskStatus.PENDING.value,
                        TaskStatus.RUNNING.value,
                        limit,
                    )
                )
                return [self._row_to_task(row) for row in cursor.fetchall()]
        return await self._run_async(_do)

    async def count_tasks_by_statuses(self, job_id: str, statuses: List[TaskStatus]) -> int:
        """统计某 Job 在指定状态集合下的任务数量。"""
        if not statuses:
            return 0

        def _do():
            placeholders = ",".join("?" for _ in statuses)
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute(
                    f"SELECT COUNT(*) FROM tasks WHERE job_id = ? AND status IN ({placeholders})",
                    [job_id, *[status.value for status in statuses]],
                )
                return cursor.fetchone()[0]

        return await self._run_async(_do)

    async def get_oldest_tasks_by_status(self, job_id: str, statuses: List[TaskStatus], limit: int) -> List[Task]:
        """获取指定状态集合下按创建时间升序的任务列表。"""
        if not statuses or limit <= 0:
            return []

        def _do():
            placeholders = ",".join("?" for _ in statuses)
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute(
                    f"SELECT * FROM tasks WHERE job_id = ? AND status IN ({placeholders}) ORDER BY created_at ASC LIMIT ?",
                    [job_id, *[status.value for status in statuses], limit],
                )
                return [self._row_to_task(row) for row in cursor.fetchall()]

        return await self._run_async(_do)

    async def get_oldest_tasks_by_status_before(
        self,
        job_id: str,
        statuses: List[TaskStatus],
        created_before: int,
        limit: int | None = None,
    ) -> List[Task]:
        """获取指定状态集合下在给定时间前创建的最老任务列表。"""
        if not statuses:
            return []
        if limit is not None and limit <= 0:
            return []

        def _do():
            placeholders = ",".join("?" for _ in statuses)
            sql = (
                f"SELECT * FROM tasks WHERE job_id = ? AND status IN ({placeholders}) "
                "AND created_at <= ? ORDER BY created_at ASC"
            )
            params: list[Any] = [job_id, *[status.value for status in statuses], created_before]
            if limit is not None:
                sql += " LIMIT ?"
                params.append(limit)
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute(sql, params)
                return [self._row_to_task(row) for row in cursor.fetchall()]

        return await self._run_async(_do)

    async def get_oldest_waiting_tasks(
        self,
        job_id: str,
        statuses: List[TaskStatus],
        limit: int,
    ) -> List[Task]:
        """获取等待队列中按 waiting_since 升序排列的任务列表。"""
        if not statuses or limit <= 0:
            return []

        def _do():
            placeholders = ",".join("?" for _ in statuses)
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute(
                    f"""
                    SELECT * FROM tasks
                    WHERE job_id = ?
                      AND status IN ({placeholders})
                      AND waiting_since IS NOT NULL
                    ORDER BY waiting_since ASC, created_at ASC
                    LIMIT ?
                    """,
                    [job_id, *[status.value for status in statuses], limit],
                )
                return [self._row_to_task(row) for row in cursor.fetchall()]

        return await self._run_async(_do)

    async def get_oldest_waiting_tasks_before(
        self,
        job_id: str,
        statuses: List[TaskStatus],
        waiting_since_before: int,
        limit: int | None = None,
    ) -> List[Task]:
        """获取等待队列中在给定 waiting_since 前进入排队的任务列表。"""
        if not statuses:
            return []
        if limit is not None and limit <= 0:
            return []

        def _do():
            placeholders = ",".join("?" for _ in statuses)
            sql = f"""
                SELECT * FROM tasks
                WHERE job_id = ?
                  AND status IN ({placeholders})
                  AND waiting_since IS NOT NULL
                  AND waiting_since <= ?
                ORDER BY waiting_since ASC, created_at ASC
            """
            params: list[Any] = [job_id, *[status.value for status in statuses], waiting_since_before]
            if limit is not None:
                sql += " LIMIT ?"
                params.append(limit)
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute(sql, params)
                return [self._row_to_task(row) for row in cursor.fetchall()]

        return await self._run_async(_do)

    async def get_running_tasks(self) -> List[Task]:
        """获取所有处于未终态的任务（重启恢复用）。"""
        def _do():
            with get_connection(STATE_DB) as conn:
                cursor = conn.execute(
                    "SELECT * FROM tasks WHERE status IN (?, ?)",
                    (
                        TaskStatus.PENDING.value,
                        TaskStatus.RUNNING.value,
                    ),
                )
                return [self._row_to_task(row) for row in cursor.fetchall()]
        return await self._run_async(_do)

    async def cancel_pending_tasks_without_resources(
        self,
        job_id: str,
        *,
        cancel_message: str,
        result_message: str,
        exclude_task_ids: List[str] | None = None,
    ) -> List[Task]:
        """取消尚未拿到环境与租约的 pending 任务。"""
        exclude_task_ids = [task_id for task_id in (exclude_task_ids or []) if task_id]

        def _do():
            with get_connection(STATE_DB) as conn:
                where_sql = """
                    job_id = ?
                    AND status = ?
                    AND env_id IS NULL
                    AND lease_id IS NULL
                """
                select_params: list[Any] = [job_id, TaskStatus.PENDING.value]
                if exclude_task_ids:
                    placeholders = ",".join("?" for _ in exclude_task_ids)
                    where_sql += f" AND id NOT IN ({placeholders})"
                    select_params.extend(exclude_task_ids)

                rows = conn.execute(
                    f"SELECT * FROM tasks WHERE {where_sql}",
                    select_params,
                ).fetchall()
                if not rows:
                    return []

                task_ids = [str(row["id"]) for row in rows]
                now = int(time.time())
                placeholders = ",".join("?" for _ in task_ids)
                conn.execute(
                    f"""
                    UPDATE tasks
                    SET status = ?,
                        result = ?,
                        error = ?,
                        waiting_since = NULL,
                        started_at = NULL,
                        finished_at = ?
                    WHERE id IN ({placeholders})
                    """,
                    [
                        TaskStatus.CANCELLED.value,
                        result_message,
                        cancel_message,
                        now,
                        *task_ids,
                    ],
                )

                tasks: list[Task] = []
                for row in rows:
                    task = self._row_to_task(row)
                    task.status = TaskStatus.CANCELLED
                    task.message = result_message
                    task.error = cancel_message
                    task.waiting_since = None
                    task.started_at = None
                    task.finished_at = now
                    tasks.append(task)
                return tasks

        return await self._run_async(_do)
        
    async def mark_tasks_failed(self, task_ids: List[str], error_message: str) -> List[Task]:
        """批量将任务标记为 FAILED。"""
        if not task_ids:
            return []
        def _do():
            with get_connection(STATE_DB) as conn:
                placeholders = ",".join("?" for _ in task_ids)
                now = int(time.time())

                params = [TaskStatus.FAILED.value, "", error_message, now, *task_ids]
                conn.execute(
                    f"""
                    UPDATE tasks 
                    SET status = ?,
                        result = ?,
                        error = ?,
                        waiting_since = NULL,
                        finished_at = ?
                    WHERE id IN ({placeholders})
                    """,
                    params
                )
                cursor = conn.execute(
                    f"SELECT * FROM tasks WHERE id IN ({placeholders})",
                    task_ids,
                )
                return [self._row_to_task(row) for row in cursor.fetchall()]
        return await self._run_async(_do)

    # =========================================================================
    # Helpers
    # =========================================================================

    def _row_to_job(self, conn: Any, row: Any) -> Job:
        trigger_data = json.loads(row["trigger_config"]) if row["trigger_config"] else {}
        run_profile_data = (
            json.loads(row["run_profile_json"])
            if "run_profile_json" in row.keys() and row["run_profile_json"]
            else None
        )
        return Job(
            id=row["id"],
            name=row["name"],
            type=JobType(row["type"]),
            run_profile=RunProfile.model_validate(run_profile_data) if run_profile_data else None,
            trigger=TriggerConfig.from_dict(trigger_data),
            concurrency_target=row["concurrency_target"],
            params=json.loads(row["params"]) if row["params"] else {},
            state=JobState(row["state"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    def _row_to_task(self, row: Any) -> Task:
        return Task(
            id=row["id"],
            job_id=row["job_id"],
            status=TaskStatus(row["status"]),
            env_id=row["env_id"],
            lease_id=row["lease_id"],
            message=row["result"] or "",
            error=row["error"] or "",
            created_at=row["created_at"],
            waiting_since=row["waiting_since"] if "waiting_since" in row.keys() else None,
            started_at=row["started_at"],
            finished_at=row["finished_at"]
        )

# Global Singleton
_repository: TaskRepository | None = None

def get_task_repository() -> TaskRepository:
    global _repository
    current_db_path = str(get_db_path(STATE_DB))
    if _repository is None or getattr(_repository, "_db_path", "") != current_db_path:
        _repository = TaskRepository()
    return _repository

def item_or_empty(item: Any) -> Any:
    return item if item else ""

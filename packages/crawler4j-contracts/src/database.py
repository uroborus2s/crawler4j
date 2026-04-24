"""模块数据库 Fluent API 契约。

该模块只负责把模块侧链式调用编译为结构化查询计划，实际校验与执行由宿主完成。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DatabaseExecutor(Protocol):
    """宿主注入给 `ctx.db` 的执行器。"""

    def describe_source(self, source: str) -> dict[str, Any]:
        """描述模块数据源。"""
        ...

    def execute_plan(self, plan: dict[str, Any]) -> Any:
        """执行结构化查询计划。"""
        ...


class DatabaseClient:
    """模块侧唯一正式数据库访问入口。"""

    def __init__(self, executor: DatabaseExecutor | None = None):
        self._executor = executor

    def bind(self, executor: DatabaseExecutor | None) -> "DatabaseClient":
        return DatabaseClient(executor)

    def from_(self, source: str) -> "DatabaseQueryBuilder":
        normalized_source = _normalize_name(source, "source")
        descriptor = self._describe_source(normalized_source)
        return DatabaseQueryBuilder(self, normalized_source, descriptor=descriptor)

    def named(self, query_id: str) -> "NamedQueryBuilder":
        return NamedQueryBuilder(self, _normalize_name(query_id, "query_id"))

    def into(self, resource: str) -> "ResourceWriter":
        return ResourceWriter(self, _normalize_name(resource, "resource"))

    def audit(self, dataset: str) -> "AuditEventClient":
        return AuditEventClient(self, _normalize_name(dataset, "dataset"))

    def _describe_source(self, source: str) -> dict[str, Any]:
        if self._executor is None:
            raise RuntimeError("ctx.db is not available in this runtime context")
        return self._executor.describe_source(source)

    def _execute_plan(self, plan: dict[str, Any]) -> Any:
        if self._executor is None:
            raise RuntimeError("ctx.db is not available in this runtime context")
        return self._executor.execute_plan(plan)


class DatabaseQueryBuilder:
    """`ctx.db.from_(...)` 查询构造器。"""

    def __init__(self, client: DatabaseClient, source: str, *, descriptor: dict[str, Any]):
        self._client = client
        self._source = source
        self._descriptor = dict(descriptor or {})
        self._select: list[dict[str, Any]] = []
        self._where: list[dict[str, Any]] = []
        self._joins: list[dict[str, Any]] = []
        self._group_by: list[str] = []
        self._order_by: list[dict[str, str]] = []
        self._limit: int | None = None
        self._offset = 0

    def select(self, *fields: str) -> "DatabaseQueryBuilder":
        self._select = [
            {"kind": "column", "field": _normalize_name(field, "field")}
            for field in fields
        ]
        return self

    def where_eq(self, field: str, value: Any) -> "DatabaseQueryBuilder":
        return self._add_where(field, "eq", value=value)

    def where(self, field: str, op: str = "eq", value: Any = None) -> "DatabaseQueryBuilder":
        normalized_op = str(op or "eq").strip().lower()
        if normalized_op not in {"eq", "in", "gt", "gte", "lt", "lte", "between", "like", "is_null"}:
            raise ValueError(f"unsupported where op: {normalized_op}")
        if normalized_op == "is_null":
            return self._add_where(field, normalized_op)
        return self._add_where(field, normalized_op, value=value)

    def where_in(self, field: str, values: list[Any] | tuple[Any, ...]) -> "DatabaseQueryBuilder":
        return self._add_where(field, "in", value=list(values))

    def where_gt(self, field: str, value: Any) -> "DatabaseQueryBuilder":
        return self._add_where(field, "gt", value=value)

    def where_gte(self, field: str, value: Any) -> "DatabaseQueryBuilder":
        return self._add_where(field, "gte", value=value)

    def where_lt(self, field: str, value: Any) -> "DatabaseQueryBuilder":
        return self._add_where(field, "lt", value=value)

    def where_lte(self, field: str, value: Any) -> "DatabaseQueryBuilder":
        return self._add_where(field, "lte", value=value)

    def where_between(self, field: str, start: Any, end: Any) -> "DatabaseQueryBuilder":
        return self._add_where(field, "between", value=[start, end])

    def where_like(self, field: str, value: str) -> "DatabaseQueryBuilder":
        return self._add_where(field, "like", value=value)

    def where_is_null(self, field: str) -> "DatabaseQueryBuilder":
        return self._add_where(field, "is_null")

    def join(
        self,
        target: str,
        *,
        on: dict[str, str],
        how: str = "inner",
    ) -> "DatabaseQueryBuilder":
        join_type = str(how or "inner").strip().lower()
        if join_type not in {"inner", "left"}:
            raise ValueError(f"unsupported join type: {join_type}")
        if not isinstance(on, dict) or not on:
            raise ValueError("join on must be a non-empty mapping")
        self._joins.append(
            {
                "target": _normalize_name(target, "target"),
                "type": join_type,
                "on": [
                    {
                        "left": _normalize_name(left, "left"),
                        "right": _normalize_name(right, "right"),
                    }
                    for left, right in on.items()
                ],
            }
        )
        return self

    def group_by(self, *fields: str) -> "DatabaseQueryBuilder":
        self._group_by = [_normalize_name(field, "field") for field in fields]
        return self

    def count(
        self,
        field: str = "*",
        *,
        as_: str = "count",
        alias: str | None = None,
    ) -> "DatabaseQueryBuilder":
        self._select.append(
            {
                "kind": "aggregate",
                "func": "count",
                "field": field,
                "alias": _normalize_name(alias or as_, "alias"),
            }
        )
        return self

    def sum(self, field: str, *, as_: str | None = None, alias: str | None = None) -> "DatabaseQueryBuilder":
        return self._add_aggregate("sum", field, alias or as_)

    def avg(self, field: str, *, as_: str | None = None, alias: str | None = None) -> "DatabaseQueryBuilder":
        return self._add_aggregate("avg", field, alias or as_)

    def min(self, field: str, *, as_: str | None = None, alias: str | None = None) -> "DatabaseQueryBuilder":
        return self._add_aggregate("min", field, alias or as_)

    def max(self, field: str, *, as_: str | None = None, alias: str | None = None) -> "DatabaseQueryBuilder":
        return self._add_aggregate("max", field, alias or as_)

    def order_by(self, field: str, direction: str = "asc") -> "DatabaseQueryBuilder":
        normalized_direction = str(direction or "asc").strip().lower()
        if normalized_direction not in {"asc", "desc"}:
            raise ValueError(f"unsupported sort direction: {normalized_direction}")
        self._order_by.append({"field": _normalize_name(field, "field"), "direction": normalized_direction})
        return self

    def limit(self, value: int) -> "DatabaseQueryBuilder":
        normalized = int(value)
        if normalized < 1:
            raise ValueError("limit must be >= 1")
        self._limit = normalized
        return self

    def offset(self, value: int) -> "DatabaseQueryBuilder":
        normalized = int(value)
        if normalized < 0:
            raise ValueError("offset must be >= 0")
        self._offset = normalized
        return self

    def execute(self) -> Any:
        return self._client._execute_plan(
            {
                "kind": "select",
                "base": {"source": self._source},
                "joins": list(self._joins),
                "select": list(self._select),
                "where": list(self._where),
                "group_by": list(self._group_by),
                "order_by": list(self._order_by),
                "limit": self._limit,
                "offset": self._offset,
            }
        )

    def _add_where(self, field: str, op: str, *, value: Any = None) -> "DatabaseQueryBuilder":
        item = {"field": _normalize_name(field, "field"), "op": op}
        if op != "is_null":
            item["value"] = value
        self._where.append(item)
        return self

    def _add_aggregate(self, func: str, field: str, alias: str | None) -> "DatabaseQueryBuilder":
        normalized_field = _normalize_name(field, "field")
        normalized_alias = _normalize_name(alias or f"{func}_{normalized_field}", "alias")
        self._select.append(
            {
                "kind": "aggregate",
                "func": func,
                "field": normalized_field,
                "alias": normalized_alias,
            }
        )
        return self


class NamedQueryBuilder:
    def __init__(self, client: DatabaseClient, query_id: str):
        self._client = client
        self._query_id = query_id
        self._params: dict[str, Any] = {}

    def bind(self, **params: Any) -> "NamedQueryBuilder":
        self._params.update(params)
        return self

    def execute(self) -> Any:
        return self._client._execute_plan(
            {
                "kind": "named_query",
                "query_id": self._query_id,
                "params": dict(self._params),
            }
        )


class AuditEventClient:
    """`ctx.db.audit(...)` 审计事件入口。"""

    def __init__(self, client: DatabaseClient, dataset: str):
        self._client = client
        self._dataset = dataset

    def append(self, event: dict[str, Any] | None = None, **fields: Any) -> Any:
        payload = dict(event or {})
        payload.update(fields)
        return self._client._execute_plan(
            {
                "kind": "append_audit_event",
                "dataset": self._dataset,
                "event": payload,
            }
        )

    def query(
        self,
        *,
        entity_key: str | None = None,
        event_type: str | None = None,
        run_id: str | None = None,
        start_at: int | None = None,
        end_at: int | None = None,
        limit: int = 100,
        offset: int = 0,
        order: str = "desc",
    ) -> Any:
        return self._client._execute_plan(
            {
                "kind": "query_audit_events",
                "dataset": self._dataset,
                "entity_key": entity_key,
                "event_type": event_type,
                "run_id": run_id,
                "start_at": start_at,
                "end_at": end_at,
                "limit": int(limit),
                "offset": int(offset),
                "order": str(order or "desc").strip().lower(),
            }
        )


class ResourceWriter:
    def __init__(self, client: DatabaseClient, resource: str):
        self._client = client
        self._resource = resource

    def replace(self, records: list[dict[str, Any]]) -> Any:
        return self._client._execute_plan(
            {
                "kind": "replace_records",
                "resource": self._resource,
                "records": list(records),
            }
        )


def _normalize_name(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text

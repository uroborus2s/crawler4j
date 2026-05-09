"""模块数据库 Fluent API 契约。

该模块只负责把模块侧链式调用编译为结构化查询计划，实际校验与执行由宿主完成。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


_UNSET = object()
_FILTER_OP_ALIASES = {
    "=": "eq",
    "==": "eq",
    "eq": "eq",
    "in": "in",
    ">": "gt",
    "gt": "gt",
    ">=": "gte",
    "gte": "gte",
    "<": "lt",
    "lt": "lt",
    "<=": "lte",
    "lte": "lte",
    "between": "between",
    "like": "like",
    "is_null": "is_null",
}


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

    def describe(self, source: str) -> dict[str, Any]:
        """Return the host-owned descriptor for a declared data source."""
        normalized_source = _normalize_name(source, "source")
        return dict(self._describe_source(normalized_source))

    def into(self, resource: str) -> "ResourceWriter":
        return ResourceWriter(self, _normalize_name(resource, "resource"))

    def audit(self, dataset: str) -> "AuditEventClient":
        return AuditEventClient(self, _normalize_name(dataset, "dataset"))

    def batch(self) -> "DatabaseBatchWriter":
        return DatabaseBatchWriter(self)

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

    def select(self, *fields: Any) -> "DatabaseQueryBuilder":
        normalized_fields = _normalize_select_fields(fields)
        self._select = [{"kind": "column", "field": _normalize_name(field, "field")} for field in normalized_fields]
        return self

    def where(self, condition: Any, op: str = "eq", value: Any = _UNSET) -> "DatabaseQueryBuilder":
        if value is _UNSET and op == "eq" and not isinstance(condition, str):
            self._where.extend(_normalize_where(condition))
            return self
        normalized_value = None if value is _UNSET else value
        self._where.extend(_normalize_where([condition, op, normalized_value]))
        return self

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

    def add(self, records: list[dict[str, Any]]) -> Any:
        return self._client._execute_plan(
            {
                "kind": "add_records",
                "resource": self._resource,
                "records": list(records),
            }
        )

    def replace(self, records: list[dict[str, Any]]) -> Any:
        return self._client._execute_plan(
            {
                "kind": "replace_records",
                "resource": self._resource,
                "records": list(records),
            }
        )

    def upsert(self, records: list[dict[str, Any]]) -> Any:
        return self._client._execute_plan(
            {
                "kind": "upsert_records",
                "resource": self._resource,
                "records": list(records),
            }
        )

    def update_where(self, fields: dict[str, Any], *, where: Any) -> Any:
        return self._client._execute_plan(
            {
                "kind": "update_records",
                "resource": self._resource,
                "fields": dict(fields),
                "where": _normalize_where(where),
            }
        )

    def delete_where(self, *, where: Any) -> Any:
        return self._client._execute_plan(
            {
                "kind": "delete_records",
                "resource": self._resource,
                "where": _normalize_where(where),
            }
        )


class DatabaseBatchWriter:
    """Host-owned atomic write batch builder."""

    def __init__(self, client: DatabaseClient):
        self._client = client
        self._operations: list[dict[str, Any]] = []

    def add(self, resource: str, records: list[dict[str, Any]]) -> "DatabaseBatchWriter":
        self._operations.append(
            {
                "kind": "add_records",
                "resource": _normalize_name(resource, "resource"),
                "records": list(records),
            }
        )
        return self

    def replace(self, resource: str, records: list[dict[str, Any]]) -> "DatabaseBatchWriter":
        self._operations.append(
            {
                "kind": "replace_records",
                "resource": _normalize_name(resource, "resource"),
                "records": list(records),
            }
        )
        return self

    def upsert(self, resource: str, records: list[dict[str, Any]]) -> "DatabaseBatchWriter":
        self._operations.append(
            {
                "kind": "upsert_records",
                "resource": _normalize_name(resource, "resource"),
                "records": list(records),
            }
        )
        return self

    def update_where(
        self,
        resource: str,
        fields: dict[str, Any],
        *,
        where: Any,
    ) -> "DatabaseBatchWriter":
        self._operations.append(
            {
                "kind": "update_records",
                "resource": _normalize_name(resource, "resource"),
                "fields": dict(fields),
                "where": _normalize_where(where),
            }
        )
        return self

    def delete_where(self, resource: str, *, where: Any) -> "DatabaseBatchWriter":
        self._operations.append(
            {
                "kind": "delete_records",
                "resource": _normalize_name(resource, "resource"),
                "where": _normalize_where(where),
            }
        )
        return self

    def audit(self, dataset: str, event: dict[str, Any] | None = None, **fields: Any) -> "DatabaseBatchWriter":
        payload = dict(event or {})
        payload.update(fields)
        self._operations.append(
            {
                "kind": "append_audit_event",
                "dataset": _normalize_name(dataset, "dataset"),
                "event": payload,
            }
        )
        return self

    def execute(self) -> Any:
        return self._client._execute_plan(
            {
                "kind": "batch",
                "operations": [dict(item) for item in self._operations],
            }
        )


def _normalize_name(value: str, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def _normalize_select_fields(raw_fields: tuple[Any, ...]) -> list[Any]:
    if len(raw_fields) == 1 and isinstance(raw_fields[0], (list, tuple)):
        return list(raw_fields[0])
    return list(raw_fields)


def _normalize_filter_op(op: Any) -> str:
    normalized = str(op or "eq").strip().lower()
    if normalized not in _FILTER_OP_ALIASES:
        raise ValueError(f"unsupported where op: {normalized}")
    return _FILTER_OP_ALIASES[normalized]


def _normalize_where(where: Any) -> list[dict[str, Any]]:
    if isinstance(where, dict):
        if "field" in where:
            return [_normalize_condition(where)]
        if "operator" in where or "conditions" in where:
            return [_normalize_condition(where)]
        if not where:
            raise ValueError("where must be non-empty")
        return [
            {"field": _normalize_name(field, "field"), "op": "eq", "value": value} for field, value in where.items()
        ]
    normalized = _normalize_condition(where)
    if normalized.get("kind") == "group" and normalized.get("operator") == "and":
        return list(normalized["conditions"])
    return [normalized]


def _normalize_condition(condition: Any) -> dict[str, Any]:
    if isinstance(condition, dict):
        if "operator" in condition or "conditions" in condition:
            operator = str(condition.get("operator") or "and").strip().lower()
            if operator not in {"and", "or"}:
                raise ValueError(f"unsupported where group operator: {operator}")
            conditions = [_normalize_condition(item) for item in condition.get("conditions") or []]
            if not conditions:
                raise ValueError("where group must contain conditions")
            return {"kind": "group", "operator": operator, "conditions": conditions}
        field = _normalize_name(condition.get("field"), "field")
        op = _normalize_filter_op(condition.get("op"))
        item = {"field": field, "op": op}
        if op != "is_null":
            item["value"] = condition.get("value")
        return item
    if not isinstance(condition, (list, tuple)):
        raise ValueError("where condition must be a list, tuple, dict, or mapping")
    items = list(condition)
    if not items:
        raise ValueError("where condition must be non-empty")
    first = items[0]
    if isinstance(first, str) and first.strip().lower() in {"and", "or"}:
        operator = first.strip().lower()
        conditions = [_normalize_condition(item) for item in items[1:]]
        if not conditions:
            raise ValueError("where group must contain conditions")
        return {"kind": "group", "operator": operator, "conditions": conditions}
    if len(items) >= 2 and isinstance(items[0], str):
        field = _normalize_name(items[0], "field")
        op = _normalize_filter_op(items[1])
        item = {"field": field, "op": op}
        if op == "between":
            if len(items) == 4:
                item["value"] = [items[2], items[3]]
            elif len(items) == 3:
                item["value"] = items[2]
            else:
                raise ValueError("between where condition requires bounds")
        elif op != "is_null":
            if len(items) < 3:
                raise ValueError(f"{op} where condition requires a value")
            item["value"] = items[2]
        return item
    if all(isinstance(item, (dict, list, tuple)) for item in items):
        return {
            "kind": "group",
            "operator": "and",
            "conditions": [_normalize_condition(item) for item in items],
        }
    raise ValueError("invalid where condition")

"""Pure environment candidate query DSL for core-native-v2 modules."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Any

NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_FILTER_OPS = {"eq", "in", "gt", "gte", "lt", "lte", "between", "like", "is_null"}


@dataclass(frozen=True)
class EnvCandidates:
    """Composable, read-only environment candidate query.

    The query only produces ordered candidate ``env_id`` values. Core still owns
    READY checks, leases, concurrency and final allocation.
    """

    source: str
    env_field: str = "env_id"
    op: str = "select"
    where: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    left: "EnvCandidates | None" = None
    right: "EnvCandidates | None" = None
    order_by_items: tuple[dict[str, str], ...] = field(default_factory=tuple)
    limit_value: int | None = None

    def __post_init__(self) -> None:
        source = _normalize_name(self.source, "source")
        env_field = _normalize_name(self.env_field, "env_field")
        op = str(self.op or "select").strip().lower()
        if op not in {"select", "intersect", "union", "minus"}:
            raise ValueError(f"unsupported env candidate operation: {op}")
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "env_field", env_field)
        object.__setattr__(self, "op", op)

    @classmethod
    def from_table(cls, source: str, *, env_field: str = "env_id") -> "EnvCandidates":
        return cls(source=source, env_field=env_field)

    def filter(self, *queries: "EnvCandidates", **conditions: Any) -> "EnvCandidates":
        current = self
        for query in queries:
            current = current.intersect(query)
        if not conditions:
            return current
        if current.op == "select":
            return replace(current, where=(*current.where, *_conditions_from_kwargs(conditions)))
        return current.intersect(
            EnvCandidates.from_table(current.source, env_field=current.env_field).filter(**conditions)
        )

    def exclude(self, *queries: "EnvCandidates", **conditions: Any) -> "EnvCandidates":
        current = self
        for query in queries:
            current = current.minus(query)
        if conditions:
            current = current.minus(
                EnvCandidates.from_table(current.source, env_field=current.env_field).filter(**conditions)
            )
        return current

    def intersect(self, other: "EnvCandidates") -> "EnvCandidates":
        return self._combine("intersect", other)

    def union(self, other: "EnvCandidates") -> "EnvCandidates":
        return self._combine("union", other)

    def minus(self, other: "EnvCandidates") -> "EnvCandidates":
        return self._combine("minus", other)

    def order_by(self, *fields: str) -> "EnvCandidates":
        items: list[dict[str, str]] = []
        for raw_field in fields:
            field_name = str(raw_field or "").strip()
            direction = "asc"
            if field_name.startswith("-"):
                field_name = field_name[1:]
                direction = "desc"
            items.append({"field": _normalize_name(field_name, "field"), "direction": direction})
        return replace(self, order_by_items=tuple(items))

    def order(self, *fields: str) -> "EnvCandidates":
        return self.order_by(*fields)

    def limit(self, value: int) -> "EnvCandidates":
        normalized = int(value)
        if normalized < 1:
            raise ValueError("limit must be >= 1")
        return replace(self, limit_value=normalized)

    def list(self, ctx: Any) -> list[int]:
        ids = self._eval_ids(ctx)
        if self.op != "select" and self.order_by_items:
            ids = self._order_ids(ctx, ids)
        if self.op != "select" and self.limit_value is not None:
            ids = ids[: self.limit_value]
        return ids

    def to_plan(self) -> dict[str, Any]:
        plan: dict[str, Any] = {
            "kind": "env_candidates",
            "op": self.op,
            "source": self.source,
            "env_field": self.env_field,
        }
        if self.op == "select":
            plan["where"] = [dict(item) for item in self.where]
        else:
            plan["left"] = self.left.to_plan() if self.left is not None else None
            plan["right"] = self.right.to_plan() if self.right is not None else None
        plan["order_by"] = [dict(item) for item in self.order_by_items]
        plan["limit"] = self.limit_value
        return plan

    def _combine(self, op: str, other: "EnvCandidates") -> "EnvCandidates":
        if not isinstance(other, EnvCandidates):
            raise TypeError("env candidate composition requires EnvCandidates")
        return EnvCandidates(
            source=self.source,
            env_field=self.env_field,
            op=op,
            left=self,
            right=other,
        )

    def _eval_ids(self, ctx: Any) -> list[int]:
        if self.op == "select":
            query = ctx.db.from_(self.source).select(self.env_field)
            for item in self.where:
                query = _apply_condition(query, item)
            for item in self.order_by_items:
                query = query.order_by(item["field"], item["direction"])
            if self.limit_value is not None:
                query = query.limit(self.limit_value)
            return _ids_from_rows(query.execute(), self.env_field)

        left_ids = self.left._eval_ids(ctx) if self.left is not None else []
        right_ids = self.right._eval_ids(ctx) if self.right is not None else []
        right_set = set(right_ids)
        if self.op == "intersect":
            return [env_id for env_id in left_ids if env_id in right_set]
        if self.op == "minus":
            return [env_id for env_id in left_ids if env_id not in right_set]
        if self.op == "union":
            seen = set(left_ids)
            merged = list(left_ids)
            for env_id in right_ids:
                if env_id in seen:
                    continue
                seen.add(env_id)
                merged.append(env_id)
            return merged
        raise ValueError(f"unsupported env candidate operation: {self.op}")

    def _order_ids(self, ctx: Any, env_ids: list[int]) -> list[int]:
        if not env_ids:
            return []
        query = ctx.db.from_(self.source).select(self.env_field).where([self.env_field, "in", env_ids])
        for item in self.order_by_items:
            query = query.order_by(item["field"], item["direction"])
        return _ids_from_rows(query.execute(), self.env_field)


def _conditions_from_kwargs(conditions: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    items: list[dict[str, Any]] = []
    for raw_name, value in conditions.items():
        field_name, op = _split_condition_name(str(raw_name or ""))
        item = {"field": field_name, "op": op}
        if op != "is_null":
            item["value"] = value
        items.append(item)
    return tuple(items)


def _split_condition_name(raw_name: str) -> tuple[str, str]:
    name = raw_name.strip()
    if "__" not in name:
        return _normalize_name(name, "field"), "eq"
    field_name, op = name.rsplit("__", 1)
    op = op.strip().lower()
    if op not in _FILTER_OPS:
        raise ValueError(f"unsupported env candidate filter op: {op}")
    return _normalize_name(field_name, "field"), op


def _apply_condition(query: Any, item: dict[str, Any]) -> Any:
    field_name = item["field"]
    op = item["op"]
    if op == "between":
        value = list(item.get("value") or [])
        if len(value) != 2:
            raise ValueError(f"{field_name}__between requires two values")
        return query.where([field_name, op, value])
    if op == "is_null":
        return query.where([field_name, op])
    if op in _FILTER_OPS:
        return query.where([field_name, op, item.get("value")])
    raise ValueError(f"unsupported env candidate filter op: {op}")


def _ids_from_rows(rows: Any, env_field: str) -> list[int]:
    ids: list[int] = []
    for row in rows or []:
        if not isinstance(row, dict) or env_field not in row:
            continue
        ids.append(int(row[env_field]))
    return ids


def _normalize_name(value: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not NAME_RE.match(normalized):
        raise ValueError(f"{field_name} must be snake_case: {normalized or '<empty>'}")
    return normalized

"""Hosted UI 表单状态与短生命周期句柄。"""

from __future__ import annotations

import secrets
import time
import weakref
from copy import deepcopy
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

FORM_HANDLE_REJECTED = "FORM_HANDLE_REJECTED"
FORM_SCOPE_UNAVAILABLE = "FORM_SCOPE_UNAVAILABLE"
FORM_EVENT_STALE = "FORM_EVENT_STALE"
FORM_INITIAL_VALUES_INVALID = "FORM_INITIAL_VALUES_INVALID"


def _reset_error(code: str) -> RuntimeError:
    return RuntimeError(f"ui.form.reset rejected: {code}")


@dataclass(frozen=True)
class HostedFormOwnerScope:
    """限制表单句柄只能由创建它的模块、页面和 UI 会话使用。"""

    module_name: str
    page_id: str
    session_id: str


@dataclass(frozen=True)
class HostedFormChange:
    field: str
    value: Any
    previous_value: Any
    values: dict[str, Any]
    revision: int


class HostedFormController:
    """与具体 Qt 控件解耦的临时表单状态。"""

    def __init__(
        self,
        *,
        mode: str,
        field_names: Sequence[str],
        initial_values: Mapping[str, Any],
        apply_values: Callable[[Mapping[str, Any]], None],
    ) -> None:
        self.mode = str(mode)
        self._field_names = tuple(str(name) for name in field_names)
        if len(set(self._field_names)) != len(self._field_names):
            raise ValueError("field_names must be unique")
        self._field_name_set = frozenset(self._field_names)
        self._apply_values = apply_values
        self._revision = 0
        self._validation_errors: dict[str, str] = {}
        normalized = self._normalize_values(initial_values)
        self._values = normalized
        self._initial_values = dict(normalized)

    @property
    def values(self) -> dict[str, Any]:
        return deepcopy(self._values)

    @property
    def initial_values(self) -> dict[str, Any]:
        return deepcopy(self._initial_values)

    @property
    def validation_errors(self) -> dict[str, str]:
        return dict(self._validation_errors)

    @property
    def dirty(self) -> bool:
        return any(
            type(self._values[name]) is not type(self._initial_values[name])
            or self._values[name] != self._initial_values[name]
            for name in self._field_names
        )

    @property
    def revision(self) -> int:
        return self._revision

    def change(self, field: str, value: Any) -> HostedFormChange:
        if field not in self._field_name_set:
            raise _reset_error(FORM_INITIAL_VALUES_INVALID)
        previous_value = self._values[field]
        self._values[field] = deepcopy(value)
        self._revision += 1
        return HostedFormChange(
            field=field,
            value=deepcopy(value),
            previous_value=deepcopy(previous_value),
            values=deepcopy(self._values),
            revision=self._revision,
        )

    def set_validation_error(self, field: str, message: str) -> None:
        if field not in self._field_name_set:
            raise _reset_error(FORM_INITIAL_VALUES_INVALID)
        self._validation_errors[field] = str(message)

    def reset(self, initial_values: Mapping[str, Any]) -> None:
        normalized = self._normalize_values(initial_values)
        self._apply_values(deepcopy(normalized))
        self._values = normalized
        self._initial_values = dict(normalized)
        self._validation_errors.clear()
        self._revision += 1

    def _normalize_values(self, values: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(values, Mapping):
            raise _reset_error(FORM_INITIAL_VALUES_INVALID)
        if set(values) - self._field_name_set:
            raise _reset_error(FORM_INITIAL_VALUES_INVALID)
        return {name: deepcopy(values[name]) if name in values else None for name in self._field_names}


@dataclass
class _HostedFormEntry:
    owner: HostedFormOwnerScope
    controller_ref: weakref.ReferenceType[HostedFormController]
    created_at: float
    is_open: Callable[[], bool]


class HostedFormRegistry:
    """保存不能由模块构造、且到期或关闭即失效的表单句柄。"""

    def __init__(self, *, ttl_seconds: float = 300.0, clock: Callable[[], float] = time.monotonic) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl_seconds = float(ttl_seconds)
        self._clock = clock
        self._entries: dict[str, _HostedFormEntry] = {}

    def open_form(
        self,
        owner: HostedFormOwnerScope,
        controller: HostedFormController,
        *,
        is_open: Callable[[], bool] | None = None,
    ) -> str:
        form_id = secrets.token_urlsafe(32)
        while form_id in self._entries:
            form_id = secrets.token_urlsafe(32)
        self._entries[form_id] = _HostedFormEntry(
            owner=owner,
            controller_ref=weakref.ref(controller),
            created_at=self._clock(),
            is_open=is_open or (lambda: True),
        )
        return form_id

    def close_form(self, form_id: str) -> None:
        self._entries.pop(str(form_id), None)

    def close_all(self) -> None:
        self._entries.clear()

    def bind_tools(
        self,
        owner: HostedFormOwnerScope,
        *,
        form_id: str,
        revision: int,
    ) -> HostedFormBoundTools:
        return HostedFormBoundTools(
            registry=self,
            owner=owner,
            form_id=str(form_id),
            revision=int(revision),
        )

    def _reset(
        self,
        *,
        owner: HostedFormOwnerScope,
        allowed_form_id: str,
        revision: int,
        form_id: str,
        initial_values: Mapping[str, Any],
    ) -> dict[str, bool]:
        requested_form_id = str(form_id)
        if requested_form_id != allowed_form_id:
            raise _reset_error(FORM_HANDLE_REJECTED)
        entry = self._entries.get(requested_form_id)
        if entry is None or entry.owner != owner:
            raise _reset_error(FORM_HANDLE_REJECTED)
        controller = entry.controller_ref()
        if (
            controller is None
            or not entry.is_open()
            or self._clock() - entry.created_at >= self._ttl_seconds
        ):
            self._entries.pop(requested_form_id, None)
            raise _reset_error(FORM_HANDLE_REJECTED)
        if controller.revision != revision:
            raise _reset_error(FORM_EVENT_STALE)
        controller.reset(initial_values)
        return {"ok": True}


@dataclass(frozen=True)
class HostedFormBoundTools:
    _registry: HostedFormRegistry
    _owner: HostedFormOwnerScope
    _form_id: str
    _revision: int

    def __init__(
        self,
        *,
        registry: HostedFormRegistry,
        owner: HostedFormOwnerScope,
        form_id: str,
        revision: int,
    ) -> None:
        object.__setattr__(self, "_registry", registry)
        object.__setattr__(self, "_owner", owner)
        object.__setattr__(self, "_form_id", form_id)
        object.__setattr__(self, "_revision", revision)

    def reset(self, *, form_id: str, initial_values: Mapping[str, Any]) -> dict[str, bool]:
        return self._registry._reset(
            owner=self._owner,
            allowed_form_id=self._form_id,
            revision=self._revision,
            form_id=form_id,
            initial_values=initial_values,
        )


class HostedFormUnavailableTools:
    """非 Form 事件使用的稳定拒绝实现。"""

    def reset(self, *, form_id: str, initial_values: Mapping[str, Any]) -> dict[str, bool]:
        del form_id, initial_values
        raise _reset_error(FORM_SCOPE_UNAVAILABLE)


__all__ = [
    "FORM_EVENT_STALE",
    "FORM_HANDLE_REJECTED",
    "FORM_INITIAL_VALUES_INVALID",
    "FORM_SCOPE_UNAVAILABLE",
    "HostedFormBoundTools",
    "HostedFormChange",
    "HostedFormController",
    "HostedFormOwnerScope",
    "HostedFormRegistry",
    "HostedFormUnavailableTools",
]

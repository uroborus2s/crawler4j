"""Minimal core-native-v2 object graph assembly."""

from __future__ import annotations

import asyncio
import datetime as dt
import inspect
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from crawler4j_contracts import ParameterSpec, TaskContext, TaskOutcome

from src.core.foundation.logging import logger
from src.core.mms.runtime_descriptor import ModuleRuntimeDescriptorV2, V2RuntimeEntry


class ObjectContainerV2:
    """Per task/env object graph for a v2 workflow run."""

    def __init__(
        self,
        descriptor: ModuleRuntimeDescriptorV2,
        workflow_name: str,
        *,
        object_bindings: Mapping[str, str] | None = None,
        object_params: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self.descriptor = descriptor
        self.workflow_name = str(workflow_name or "").strip()
        self.object_bindings = _normalize_object_bindings(object_bindings)
        self.object_params = _normalize_object_params(object_params)
        self._validate_object_binding_keys()
        self._validate_object_param_owners()
        self.instances: dict[str, Any] = {}
        self._workflow_instance: Any | None = None
        self._closed = False

    def build_workflow(self) -> Any:
        if self._workflow_instance is not None:
            return self._workflow_instance
        if not self.workflow_name:
            raise RuntimeError("workflow 名称不能为空")
        entry = self.descriptor.workflows.get(self.workflow_name)
        if entry is None:
            raise RuntimeError(f"workflow 不存在: {self.workflow_name}")

        kwargs = self._build_inject_kwargs(entry, parent_path="")
        try:
            self._workflow_instance = entry.target(**kwargs)
        except Exception as exc:
            raise RuntimeError(f"workflow {self.workflow_name} 构造失败: {exc.__class__.__name__}: {exc}") from exc
        return self._workflow_instance

    def get_component(self, component_name: str) -> Any:
        normalized_name = str(component_name or "").strip()
        if not normalized_name:
            raise RuntimeError("component 名称不能为空")
        return self._build_component(normalized_name, inject_path=normalized_name)

    def _validate_object_binding_keys(self) -> None:
        valid_keys = set(self.descriptor.interfaces)

        def visit(entry: V2RuntimeEntry, *, parent_path: str, seen_components: set[str]) -> None:
            for inject in entry.meta.inject:
                inject_path = f"{parent_path}.{inject.name}" if parent_path else inject.name
                if inject.type == "interface":
                    valid_keys.add(inject_path)
                    for component_name in self.descriptor.implementations.get(inject.target, ()):
                        if component_name in seen_components:
                            continue
                        component_entry = self.descriptor.components.get(component_name)
                        if component_entry is not None:
                            visit(
                                component_entry,
                                parent_path=inject_path,
                                seen_components={*seen_components, component_name},
                            )
                    continue
                if inject.type != "object":
                    continue
                component_name = inject.target
                if component_name in seen_components:
                    continue
                component_entry = self.descriptor.components.get(component_name)
                if component_entry is not None:
                    visit(component_entry, parent_path=inject_path, seen_components={*seen_components, component_name})

        for entry in self.descriptor.workflows.values():
            visit(entry, parent_path="", seen_components=set())
        for component_name, entry in self.descriptor.components.items():
            visit(entry, parent_path=component_name, seen_components={component_name})

        unknown_keys = sorted(set(self.object_bindings) - valid_keys)
        if unknown_keys:
            raise RuntimeError(f"object_bindings 包含未知注入路径: {', '.join(unknown_keys)}")

    def _build_component(self, component_name: str, *, inject_path: str) -> Any:
        if component_name in self.instances:
            return self.instances[component_name]

        entry = self.descriptor.components.get(component_name)
        if entry is None:
            raise RuntimeError(f"component 不存在: {component_name}")

        kwargs = self._build_inject_kwargs(entry, parent_path=inject_path)
        kwargs.update(self._component_constructor_params(component_name, entry))
        try:
            instance = entry.target(**kwargs)
        except Exception as exc:
            raise RuntimeError(f"component {component_name} 构造失败: {exc.__class__.__name__}: {exc}") from exc
        self.instances[component_name] = instance
        return instance

    async def cleanup(
        self,
        context: TaskContext,
        outcome: TaskOutcome,
        *,
        timeout_seconds: float | None = None,
    ) -> None:
        """Run workflow/component cleanup methods owned by this task/env graph."""
        if self._closed:
            return
        self._closed = True

        finalizers: list[tuple[str, Any]] = []
        if self._workflow_instance is not None:
            finalizers.append((f"workflow {self.workflow_name}", self._workflow_instance))
        finalizers.extend(
            (f"component {component_name}", instance)
            for component_name, instance in reversed(list(self.instances.items()))
        )

        for label, instance in finalizers:
            await self._cleanup_instance(label, instance, context, outcome, timeout_seconds=timeout_seconds)

    async def _cleanup_instance(
        self,
        label: str,
        instance: Any,
        context: TaskContext,
        outcome: TaskOutcome,
        *,
        timeout_seconds: float | None,
    ) -> None:
        cleanup = getattr(instance, "cleanup", None)
        if not callable(cleanup):
            return
        try:
            operation = _invoke_cleanup(cleanup, context, outcome)
            if timeout_seconds is not None and timeout_seconds > 0:
                await asyncio.wait_for(operation, timeout=float(timeout_seconds))
            else:
                await operation
        except asyncio.TimeoutError:
            logger.error(
                f"[MMS] Timed out cleaning v2 object: {label} "
                f"method=cleanup timeout={timeout_seconds:.1f}s"
            )
        except Exception as exc:
            logger.error(
                f"[MMS] Failed to clean v2 object: {label} "
                f"method=cleanup error={exc.__class__.__name__}: {exc}"
            )

    def _build_inject_kwargs(self, entry: V2RuntimeEntry, *, parent_path: str) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        for inject in entry.meta.inject:
            inject_path = f"{parent_path}.{inject.name}" if parent_path else inject.name
            if inject.type == "object":
                component_name = inject.target
            elif inject.type == "interface":
                component_name = self._resolve_interface_component(inject.target, inject_path)
            else:  # pragma: no cover - InjectSpec validation rejects this earlier.
                raise RuntimeError(f"{entry.meta.name} 包含不支持的注入类型: {inject.type}")
            kwargs[inject.name] = self._build_component(component_name, inject_path=inject_path)
        return kwargs

    def _resolve_interface_component(self, interface_name: str, inject_path: str) -> str:
        if interface_name not in self.descriptor.interfaces:
            raise RuntimeError(f"interface 不存在: {interface_name}")

        selected_component = self.object_bindings.get(inject_path) or self.object_bindings.get(interface_name)
        if not selected_component:
            implementations = self.descriptor.implementations.get(interface_name, ())
            if len(implementations) == 1:
                selected_component = implementations[0]
            else:
                raise RuntimeError(f"interface 注入缺少实现选择: {inject_path} -> interface {interface_name}")

        component_entry = self.descriptor.components.get(selected_component)
        if component_entry is None:
            raise RuntimeError(f"interface {interface_name} 选择的 component 不存在: {selected_component}")
        if component_entry.meta.implements != interface_name:
            raise RuntimeError(
                f"component {selected_component} 不实现 interface {interface_name}: "
                f"{component_entry.meta.implements or '<empty>'}"
            )
        return selected_component

    def _component_constructor_params(self, component_name: str, entry: V2RuntimeEntry) -> dict[str, Any]:
        raw_params = self.object_params.get(component_name, {})
        declared_params = {parameter.name: parameter for parameter in entry.meta.parameters}
        unknown_params = sorted(set(raw_params) - set(declared_params))
        if unknown_params:
            raise RuntimeError(f"component {component_name} 包含未声明对象参数: {', '.join(unknown_params)}")

        params: dict[str, Any] = {}
        for parameter in entry.meta.parameters:
            if parameter.name in raw_params:
                value = raw_params[parameter.name]
                params[parameter.name] = _validate_parameter_value(component_name, parameter, value)
                continue
            if parameter.required and parameter.default is None:
                raise RuntimeError(f"component {component_name} 缺少对象参数: {parameter.name}")
            if parameter.default is not None:
                params[parameter.name] = _validate_parameter_value(component_name, parameter, parameter.default)
            else:
                params[parameter.name] = parameter.default
        return params

    def _validate_object_param_owners(self) -> None:
        unknown_components = sorted(set(self.object_params) - set(self.descriptor.components))
        if unknown_components:
            raise RuntimeError(f"object_params 引用了未声明 component: {', '.join(unknown_components)}")


def _normalize_object_bindings(object_bindings: Mapping[str, str] | None) -> dict[str, str]:
    if object_bindings is None:
        return {}
    if not isinstance(object_bindings, Mapping):
        raise RuntimeError("object_bindings 必须是映射对象")

    normalized: dict[str, str] = {}
    for raw_key, raw_value in object_bindings.items():
        key = str(raw_key or "").strip()
        value = str(raw_value or "").strip()
        if key and value:
            normalized[key] = value
    return normalized


def _normalize_object_params(
    object_params: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    if object_params is None:
        return {}
    if not isinstance(object_params, Mapping):
        raise RuntimeError("object_params 必须是映射对象")

    normalized: dict[str, dict[str, Any]] = {}
    for raw_component_name, raw_params in object_params.items():
        component_name = str(raw_component_name or "").strip()
        if not component_name:
            continue
        if not isinstance(raw_params, Mapping):
            raise RuntimeError(f"object_params[{component_name}] 必须是映射对象")
        normalized[component_name] = dict(raw_params)
    return normalized


async def _invoke_cleanup(cleanup: Any, context: TaskContext, outcome: TaskOutcome) -> None:
    result = cleanup(context, outcome)
    if inspect.isawaitable(result):
        await result


def _validate_parameter_value(component_name: str, parameter: ParameterSpec, value: Any) -> Any:
    owner = f"component {component_name} 参数 {parameter.name}"
    return _validate_value(owner, parameter, value)


def _validate_value(owner: str, parameter: ParameterSpec, value: Any) -> Any:
    if value is None:
        if parameter.required:
            raise RuntimeError(f"{owner} 不能为空")
        return None

    parameter_type = parameter.type
    if parameter_type in {"string", "text", "secret"}:
        if not isinstance(value, str):
            raise RuntimeError(f"{owner} 必须是字符串")
        return value
    if parameter_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise RuntimeError(f"{owner} 必须是整数")
        _validate_numeric_bounds(owner, parameter, value)
        return value
    if parameter_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise RuntimeError(f"{owner} 必须是数字")
        _validate_numeric_bounds(owner, parameter, value)
        return value
    if parameter_type == "boolean":
        if not isinstance(value, bool):
            raise RuntimeError(f"{owner} 必须是布尔值")
        return value
    if parameter_type == "enum":
        allowed_values = [option.value for option in parameter.options]
        if value not in allowed_values:
            raise RuntimeError(f"{owner} 不在允许范围: {value!r}")
        return value
    if parameter_type == "array":
        return _validate_array(owner, parameter, value)
    if parameter_type == "object":
        return _validate_object(owner, parameter, value)
    if parameter_type == "json":
        if not _is_json_like(value):
            raise RuntimeError(f"{owner} 必须是 JSON-like 值")
        return value
    if parameter_type == "date":
        return _coerce_date(owner, value)
    if parameter_type == "datetime":
        return _coerce_datetime(owner, value)
    if parameter_type == "time":
        return _coerce_time(owner, value)
    if parameter_type == "url":
        if not isinstance(value, str) or not _is_url(value):
            raise RuntimeError(f"{owner} 必须是 URL")
        return value
    if parameter_type == "path":
        if not isinstance(value, (str, Path)):
            raise RuntimeError(f"{owner} 必须是路径")
        return Path(value)
    raise RuntimeError(f"{owner} 类型不受支持: {parameter_type}")


def _validate_array(owner: str, parameter: ParameterSpec, value: Any) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        raise RuntimeError(f"{owner} 必须是数组")
    if not parameter.item_schema:
        return list(value)
    item_parameter = _schema_parameter(parameter.item_schema)
    return [_validate_value(f"{owner}[{index}]", item_parameter, item) for index, item in enumerate(value)]


def _validate_object(owner: str, parameter: ParameterSpec, value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"{owner} 必须是对象")
    if not all(isinstance(key, str) for key in value):
        raise RuntimeError(f"{owner} 必须是对象")

    normalized = dict(value)
    fields = parameter.schema.get("fields")
    if isinstance(fields, list):
        for field in fields:
            if not isinstance(field, Mapping):
                continue
            field_name = str(field.get("name") or field.get("key") or "").strip()
            if not field_name:
                continue
            field_parameter = _schema_parameter(field)
            if field_name not in normalized:
                if field_parameter.required:
                    _validate_value(f"{owner}.{field_name}", field_parameter, None)
                continue
            normalized[field_name] = _validate_value(f"{owner}.{field_name}", field_parameter, normalized[field_name])

    additional_type = str(parameter.schema.get("additional_type") or "").strip()
    if additional_type:
        additional_parameter = ParameterSpec(name="value", type=additional_type)
        for key, item in list(normalized.items()):
            normalized[key] = _validate_value(f"{owner}.{key}", additional_parameter, item)
    return normalized


def _schema_parameter(schema: Mapping[str, Any]) -> ParameterSpec:
    return ParameterSpec(
        name=str(schema.get("name") or schema.get("key") or "value"),
        type=str(schema.get("type") or "string"),
        required=bool(schema.get("required")),
        options=tuple(_as_tuple(schema.get("options"))),
        min=schema.get("min"),
        max=schema.get("max"),
        step=schema.get("step"),
        schema=dict(schema.get("schema") or {}),
        item_schema=dict(schema.get("item_schema") or {}),
    )


def _validate_numeric_bounds(owner: str, parameter: ParameterSpec, value: int | float) -> None:
    if parameter.min is not None and value < parameter.min:
        raise RuntimeError(f"{owner} 不能小于 {parameter.min}")
    if parameter.max is not None and value > parameter.max:
        raise RuntimeError(f"{owner} 不能大于 {parameter.max}")


def _coerce_date(owner: str, value: Any) -> dt.date:
    if isinstance(value, dt.date) and not isinstance(value, dt.datetime):
        return value
    if isinstance(value, str):
        try:
            return dt.date.fromisoformat(value)
        except ValueError as exc:
            raise RuntimeError(f"{owner} 必须是 ISO date") from exc
    raise RuntimeError(f"{owner} 必须是 ISO date")


def _coerce_datetime(owner: str, value: Any) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, str):
        try:
            return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RuntimeError(f"{owner} 必须是 ISO datetime") from exc
    raise RuntimeError(f"{owner} 必须是 ISO datetime")


def _coerce_time(owner: str, value: Any) -> dt.time:
    if isinstance(value, dt.time):
        return value
    if isinstance(value, str):
        try:
            return dt.time.fromisoformat(value)
        except ValueError as exc:
            raise RuntimeError(f"{owner} 必须是 ISO time") from exc
    raise RuntimeError(f"{owner} 必须是 ISO time")


def _is_url(value: str) -> bool:
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def _is_json_like(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool)):
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if isinstance(value, list):
        return all(_is_json_like(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_like(item) for key, item in value.items())
    return False


def _as_tuple(value: Any) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return tuple(value)


__all__ = ["ObjectContainerV2"]

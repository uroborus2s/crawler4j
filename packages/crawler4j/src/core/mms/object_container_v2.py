"""Minimal core-native-v2 object graph assembly."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from crawler4j_contracts import ParameterSpec

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
        self._validate_object_param_owners()
        self.instances: dict[str, Any] = {}
        self._workflow_instance: Any | None = None

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
                _validate_parameter_value(component_name, parameter, value)
                params[parameter.name] = value
                continue
            if parameter.required and parameter.default is None:
                raise RuntimeError(f"component {component_name} 缺少对象参数: {parameter.name}")
            if parameter.default is not None:
                _validate_parameter_value(component_name, parameter, parameter.default)
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


def _validate_parameter_value(component_name: str, parameter: ParameterSpec, value: Any) -> None:
    owner = f"component {component_name} 参数 {parameter.name}"
    if value is None:
        if parameter.required:
            raise RuntimeError(f"{owner} 不能为空")
        return

    parameter_type = parameter.type
    if parameter_type in {"string", "text"}:
        if not isinstance(value, str):
            raise RuntimeError(f"{owner} 必须是字符串")
        return
    if parameter_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise RuntimeError(f"{owner} 必须是整数")
        _validate_numeric_bounds(owner, parameter, value)
        return
    if parameter_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise RuntimeError(f"{owner} 必须是数字")
        _validate_numeric_bounds(owner, parameter, value)
        return
    if parameter_type == "boolean":
        if not isinstance(value, bool):
            raise RuntimeError(f"{owner} 必须是布尔值")
        return
    if parameter_type == "enum":
        allowed_values = [option.value for option in parameter.options]
        if value not in allowed_values:
            raise RuntimeError(f"{owner} 不在允许范围: {value!r}")
        return
    raise RuntimeError(f"{owner} 类型不受支持: {parameter_type}")


def _validate_numeric_bounds(owner: str, parameter: ParameterSpec, value: int | float) -> None:
    if parameter.min is not None and value < parameter.min:
        raise RuntimeError(f"{owner} 不能小于 {parameter.min}")
    if parameter.max is not None and value > parameter.max:
        raise RuntimeError(f"{owner} 不能大于 {parameter.max}")


__all__ = ["ObjectContainerV2"]

"""Core-native-v2 declaration decorators and metadata contracts."""

from __future__ import annotations

import ast
import inspect
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Annotated, Any, TypeVar, get_args, get_origin, get_type_hints


CRAWLER4J_META_ATTR = "__crawler4j_meta__"
HOST_RESERVED_DATA_FIELDS = frozenset({"created_at", "updated_at", "create_at", "update_at"})
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
TargetT = TypeVar("TargetT")
_MISSING = object()


@dataclass(frozen=True)
class ParameterOptionSpec:
    """Option item for enum parameters."""

    label: str
    value: Any


@dataclass(frozen=True)
class ParameterSpec:
    """Declarative component or action parameter metadata."""

    name: str
    type: str = "string"
    label: str = ""
    description: str = ""
    required: bool = False
    default: Any = None
    options: tuple[ParameterOptionSpec, ...] = field(default_factory=tuple)
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    placeholder: str = ""

    def __post_init__(self) -> None:
        name = str(self.name or "").strip()
        parameter_type = str(self.type or "string").strip().lower()
        options = tuple(_normalize_parameter_option(item) for item in _as_tuple(self.options))
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "type", parameter_type)
        object.__setattr__(self, "label", str(self.label or "").strip())
        object.__setattr__(self, "description", str(self.description or "").strip())
        object.__setattr__(self, "options", options)
        object.__setattr__(self, "placeholder", str(self.placeholder or "").strip())
        if parameter_type == "enum" and not options:
            raise ValueError(f"enum parameter must declare options: {name}")


@dataclass(frozen=True)
class ObjectParamAnnotation:
    """Class or ``__init__`` annotation marker for component object parameters."""

    name: str = ""
    type: str = ""
    label: str = ""
    description: str = ""
    required: bool | None = None
    default: Any = _MISSING
    options: tuple[ParameterOptionSpec | Mapping[str, Any] | Any, ...] = field(default_factory=tuple)
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    placeholder: str = ""


@dataclass(frozen=True)
class ObjectInjectAnnotation:
    """Class or ``__init__`` annotation marker for object graph injection."""

    target: str
    type: str = "interface"
    name: str = ""

    def __post_init__(self) -> None:
        inject_type = str(self.type or "interface").strip().lower()
        target = str(self.target or "").strip()
        name = str(self.name or "").strip()
        object.__setattr__(self, "type", inject_type)
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "name", name)
        if inject_type not in {"interface", "object"}:
            raise ValueError(f"object injection type must be interface or object: {inject_type or '<empty>'}")
        if not _is_valid_name(target):
            raise ValueError(f"object injection target must be snake_case: {target or '<empty>'}")
        if name and not _is_valid_name(name):
            raise ValueError(f"object injection name must be snake_case: {name}")


@dataclass(frozen=True)
class InjectSpec:
    """Object graph injection requirement."""

    name: str
    type: str
    target: str

    def __post_init__(self) -> None:
        name = str(self.name or "").strip()
        inject_type = str(self.type or "").strip().lower()
        target = str(self.target or "").strip()
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "type", inject_type)
        object.__setattr__(self, "target", target)
        if not _is_valid_name(name):
            raise ValueError(f"inject name must be snake_case: {name or '<empty>'}")
        if inject_type not in {"interface", "object"}:
            raise ValueError(f"inject type must be interface or object: {inject_type or '<empty>'}")
        if not _is_valid_name(target):
            raise ValueError(f"inject target must be snake_case: {target or '<empty>'}")


@dataclass(frozen=True)
class DataTableIndexSpec:
    """Index declaration for a v2 data table."""

    name: str = ""
    fields: tuple[str, ...] = field(default_factory=tuple)
    unique: bool = False

    def __post_init__(self) -> None:
        fields = tuple(str(item or "").strip() for item in _as_tuple(self.fields))
        object.__setattr__(self, "name", str(self.name or "").strip())
        object.__setattr__(self, "fields", fields)
        if not fields:
            raise ValueError("data table index fields cannot be empty")
        for field_name in fields:
            if not _is_valid_name(field_name):
                raise ValueError(f"data table index field must be snake_case: {field_name or '<empty>'}")


@dataclass(frozen=True)
class Crawler4jMeta:
    """Metadata attached to core-native-v2 decorated declarations."""

    kind: str
    name: str
    label: str = ""
    description: str = ""
    implements: str = ""
    inject: tuple[InjectSpec, ...] = field(default_factory=tuple)
    parameters: tuple[ParameterSpec, ...] = field(default_factory=tuple)
    schema: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    indexes: tuple[DataTableIndexSpec, ...] = field(default_factory=tuple)
    source: str = ""
    sql: str = ""
    output_schema: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        kind = str(self.kind or "").strip()
        name = str(self.name or "").strip()
        if kind not in {"interface", "component", "workflow", "page_action", "data_table", "data_query"}:
            raise ValueError(f"unsupported decorator kind: {kind or '<empty>'}")
        if not _is_valid_name(name):
            raise ValueError(f"{kind} name must be snake_case: {name or '<empty>'}")
        inject = tuple(_normalize_inject(item) for item in _as_tuple(self.inject))
        parameters = tuple(_normalize_parameter(item) for item in _as_tuple(self.parameters))
        schema = tuple(_normalize_schema_item(item, field_name="schema") for item in _as_tuple(self.schema))
        indexes = tuple(_normalize_index(item) for item in _as_tuple(self.indexes))
        output_schema = tuple(
            _normalize_schema_item(item, field_name="output_schema") for item in _as_tuple(self.output_schema)
        )
        implements = str(self.implements or "").strip()
        source = str(self.source or "").strip()
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "label", str(self.label or "").strip())
        object.__setattr__(self, "description", str(self.description or "").strip())
        object.__setattr__(self, "implements", implements)
        object.__setattr__(self, "inject", inject)
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "schema", schema)
        object.__setattr__(self, "indexes", indexes)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "sql", str(self.sql or "").strip())
        object.__setattr__(self, "output_schema", output_schema)
        if kind == "component" and not _is_valid_name(implements):
            raise ValueError("component implements must reference an interface")
        if kind == "data_table" and not schema:
            raise ValueError("data_table schema cannot be empty")
        if kind == "data_query" and not source:
            raise ValueError("data_query source cannot be empty")


def interface(
    *,
    name: str,
    label: str = "",
    description: str = "",
) -> Callable[[TargetT], TargetT]:
    """Declare an injectable interface."""
    return _decorate(Crawler4jMeta(kind="interface", name=name, label=label, description=description))


def component(
    *,
    name: str,
    implements: str,
    label: str = "",
    description: str = "",
    inject: Iterable[InjectSpec | Mapping[str, Any]] | None = None,
    parameters: Iterable[ParameterSpec | Mapping[str, Any]] | None = None,
) -> Callable[[TargetT], TargetT]:
    """Declare an object graph component implementation."""
    return _decorate(
        Crawler4jMeta(
            kind="component",
            name=name,
            label=label,
            description=description,
            implements=implements,
            inject=tuple(_as_tuple(inject)),
            parameters=tuple(_as_tuple(parameters)),
        )
    )


def object_param(
    *,
    name: str = "",
    type: str = "",
    label: str = "",
    description: str = "",
    required: bool | None = None,
    default: Any = _MISSING,
    options: Iterable[ParameterOptionSpec | Mapping[str, Any] | Any] | None = None,
    min: int | float | None = None,
    max: int | float | None = None,
    step: int | float | None = None,
    placeholder: str = "",
) -> ObjectParamAnnotation:
    """Declare a component object parameter on a class attribute or ``__init__`` argument."""
    return ObjectParamAnnotation(
        name=name,
        type=type,
        label=label,
        description=description,
        required=required,
        default=default,
        options=tuple(_as_tuple(options)),
        min=min,
        max=max,
        step=step,
        placeholder=placeholder,
    )


def object_inject(*, target: str, type: str = "interface", name: str = "") -> ObjectInjectAnnotation:
    """Declare object graph injection on a class attribute or ``__init__`` argument."""
    return ObjectInjectAnnotation(name=name, type=type, target=target)


def workflow(
    *,
    name: str,
    label: str = "",
    description: str = "",
    inject: Iterable[InjectSpec | Mapping[str, Any]] | None = None,
    parameters: Iterable[ParameterSpec | Mapping[str, Any]] | None = None,
) -> Callable[[TargetT], TargetT]:
    """Declare a workflow object assembled by Core."""
    if parameters:
        raise ValueError("workflow decorators do not accept parameters in core-native-v2")
    return _decorate(
        Crawler4jMeta(
            kind="workflow",
            name=name,
            label=label,
            description=description,
            inject=tuple(_as_tuple(inject)),
        )
    )


def page_action(
    *,
    name: str,
    label: str = "",
    description: str = "",
    inject: Iterable[InjectSpec | Mapping[str, Any]] | None = None,
    parameters: Iterable[ParameterSpec | Mapping[str, Any]] | None = None,
) -> Callable[[TargetT], TargetT]:
    """Declare a hosted-page action function."""
    return _decorate(
        Crawler4jMeta(
            kind="page_action",
            name=name,
            label=label,
            description=description,
            inject=tuple(_as_tuple(inject)),
            parameters=tuple(_as_tuple(parameters)),
        )
    )


def data_table(
    *,
    name: str,
    label: str = "",
    description: str = "",
    schema: Iterable[Mapping[str, Any]],
    indexes: Iterable[DataTableIndexSpec | Mapping[str, Any]] | None = None,
) -> Callable[[TargetT], TargetT]:
    """Declare a table-shaped data contract."""
    return _decorate(
        Crawler4jMeta(
            kind="data_table",
            name=name,
            label=label,
            description=description,
            schema=tuple(_as_tuple(schema)),
            indexes=tuple(_as_tuple(indexes)),
        )
    )


def data_query(
    *,
    name: str,
    source: str,
    sql: str,
    label: str = "",
    description: str = "",
    parameters: Iterable[ParameterSpec | Mapping[str, Any]] | None = None,
    output_schema: Iterable[Mapping[str, Any]] | None = None,
) -> Callable[[TargetT], TargetT]:
    """Declare a named query over a v2 data table."""
    return _decorate(
        Crawler4jMeta(
            kind="data_query",
            name=name,
            label=label,
            description=description,
            source=source,
            sql=sql,
            parameters=tuple(_as_tuple(parameters)),
            output_schema=tuple(_as_tuple(output_schema)),
        )
    )


def _decorate(meta: Crawler4jMeta) -> Callable[[TargetT], TargetT]:
    def apply(target: TargetT) -> TargetT:
        setattr(target, CRAWLER4J_META_ATTR, _merge_annotation_metadata(meta, target))
        return target

    return apply


def _merge_annotation_metadata(meta: Crawler4jMeta, target: TargetT) -> Crawler4jMeta:
    if not isinstance(target, type):
        return meta

    annotation_inject, annotation_parameters = _class_annotation_metadata(target)
    if not annotation_inject and not annotation_parameters:
        return meta

    return Crawler4jMeta(
        kind=meta.kind,
        name=meta.name,
        label=meta.label,
        description=meta.description,
        implements=meta.implements,
        inject=_merge_named_specs(meta.inject, annotation_inject),
        parameters=_merge_named_specs(meta.parameters, annotation_parameters),
        schema=meta.schema,
        indexes=meta.indexes,
        source=meta.source,
        sql=meta.sql,
        output_schema=meta.output_schema,
    )


def _class_annotation_metadata(target: type[Any]) -> tuple[tuple[InjectSpec, ...], tuple[ParameterSpec, ...]]:
    inject: list[InjectSpec] = []
    parameters: list[ParameterSpec] = []

    class_hints = _safe_type_hints(target, localns=dict(vars(target)))
    class_values = vars(target)
    for name, annotation in class_hints.items():
        item_inject, item_parameter = _spec_from_annotation(
            name,
            annotation,
            fallback_default=class_values.get(name, _MISSING),
        )
        if item_inject is not None:
            inject.append(item_inject)
        if item_parameter is not None:
            parameters.append(item_parameter)

    init = getattr(target, "__init__", None)
    if init is not None:
        init_hints = _safe_type_hints(init, localns=dict(vars(target)))
        signature = inspect.signature(init)
        for name, parameter in signature.parameters.items():
            if name == "self" or parameter.kind in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }:
                continue
            annotation = init_hints.get(name)
            if annotation is None:
                continue
            fallback_default = parameter.default
            if fallback_default is inspect.Parameter.empty:
                fallback_default = _MISSING
            item_inject, item_parameter = _spec_from_annotation(
                name,
                annotation,
                fallback_default=fallback_default,
            )
            if item_inject is not None:
                inject.append(item_inject)
            if item_parameter is not None:
                parameters.append(item_parameter)

    return tuple(inject), tuple(parameters)


def _safe_type_hints(target: Any, *, localns: dict[str, Any]) -> dict[str, Any]:
    try:
        return get_type_hints(target, localns=localns, include_extras=True)
    except Exception:
        return inspect.get_annotations(target, eval_str=False)


def _spec_from_annotation(
    fallback_name: str,
    annotation: Any,
    *,
    fallback_default: Any,
) -> tuple[InjectSpec | None, ParameterSpec | None]:
    marker, type_hint = _annotation_marker(annotation)
    if isinstance(marker, ObjectInjectAnnotation):
        return (
            InjectSpec(
                name=marker.name or fallback_name,
                type=marker.type,
                target=marker.target,
            ),
            None,
        )
    if isinstance(marker, ObjectParamAnnotation):
        return None, _parameter_from_annotation(marker, fallback_name, type_hint, fallback_default)
    return None, None


def _annotation_marker(annotation: Any) -> tuple[Any, Any]:
    if isinstance(annotation, str):
        return _annotation_marker_from_string(annotation)
    if isinstance(annotation, (ObjectInjectAnnotation, ObjectParamAnnotation)):
        return annotation, Any

    if get_origin(annotation) is Annotated:
        args = get_args(annotation)
        if not args:
            return None, Any
        type_hint = args[0]
        for marker in args[1:]:
            if isinstance(marker, (ObjectInjectAnnotation, ObjectParamAnnotation)):
                return marker, type_hint
    return None, annotation


def _annotation_marker_from_string(annotation: str) -> tuple[Any, Any]:
    try:
        expression = ast.parse(annotation, mode="eval").body
    except SyntaxError:
        return None, Any
    return _annotation_marker_from_ast(expression)


def _annotation_marker_from_ast(node: ast.expr) -> tuple[Any, Any]:
    if isinstance(node, ast.Call):
        marker = _marker_from_ast_call(node)
        if marker is not None:
            return marker, Any
    if isinstance(node, ast.Subscript) and _ast_annotation_name(node.value) == "Annotated":
        elements = _ast_subscript_elements(node.slice)
        if not elements:
            return None, Any
        type_hint = _ast_annotation_name(elements[0])
        for item in elements[1:]:
            if not isinstance(item, ast.Call):
                continue
            marker = _marker_from_ast_call(item)
            if marker is not None:
                return marker, type_hint
    return None, Any


def _marker_from_ast_call(node: ast.Call) -> ObjectInjectAnnotation | ObjectParamAnnotation | None:
    marker_name = _ast_annotation_name(node.func)
    if marker_name not in {"object_param", "object_inject"}:
        return None
    if node.args:
        raise ValueError(f"{marker_name} annotation does not support positional arguments")
    kwargs: dict[str, Any] = {}
    for keyword in node.keywords:
        if keyword.arg is None:
            raise ValueError(f"{marker_name} annotation does not support **kwargs")
        kwargs[keyword.arg] = ast.literal_eval(keyword.value)
    if marker_name == "object_inject":
        return object_inject(**kwargs)
    return object_param(**kwargs)


def _ast_annotation_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _ast_subscript_elements(node: ast.expr) -> list[ast.expr]:
    if isinstance(node, ast.Tuple):
        return list(node.elts)
    return [node]


def _parameter_from_annotation(
    marker: ObjectParamAnnotation,
    fallback_name: str,
    type_hint: Any,
    fallback_default: Any,
) -> ParameterSpec:
    default_supplied = marker.default is not _MISSING or fallback_default is not _MISSING
    default = marker.default if marker.default is not _MISSING else fallback_default
    if default is _MISSING:
        default = None
    required = marker.required if marker.required is not None else not default_supplied
    return ParameterSpec(
        name=marker.name or fallback_name,
        type=marker.type or _infer_parameter_type(type_hint) or "string",
        label=marker.label,
        description=marker.description,
        required=bool(required),
        default=default,
        options=tuple(_as_tuple(marker.options)),
        min=marker.min,
        max=marker.max,
        step=marker.step,
        placeholder=marker.placeholder,
    )


def _infer_parameter_type(type_hint: Any) -> str:
    mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
    }
    return mapping.get(type_hint, "")


def _merge_named_specs(existing: Iterable[Any], annotations: Iterable[Any]) -> tuple[Any, ...]:
    merged = list(existing)
    seen_names = {str(getattr(item, "name", "") or "") for item in merged}
    for item in annotations:
        name = str(getattr(item, "name", "") or "")
        if name in seen_names:
            continue
        merged.append(item)
        seen_names.add(name)
    return tuple(merged)


def _as_tuple(value: Iterable[Any] | None) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return tuple(value)


def _normalize_parameter(value: ParameterSpec | Mapping[str, Any]) -> ParameterSpec:
    if isinstance(value, ParameterSpec):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("parameters must contain ParameterSpec or mapping items")
    return ParameterSpec(**dict(value))


def _normalize_parameter_option(value: ParameterOptionSpec | Mapping[str, Any] | Any) -> ParameterOptionSpec:
    if isinstance(value, ParameterOptionSpec):
        return value
    if isinstance(value, Mapping):
        if "value" not in value:
            raise ValueError("enum option value cannot be empty")
        return ParameterOptionSpec(
            label=str(value.get("label", value["value"]) or "").strip(),
            value=value["value"],
        )
    return ParameterOptionSpec(label=str(value), value=value)


def _normalize_inject(value: InjectSpec | Mapping[str, Any]) -> InjectSpec:
    if isinstance(value, InjectSpec):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("inject must contain InjectSpec or mapping items")
    return InjectSpec(**dict(value))


def _normalize_index(value: DataTableIndexSpec | Mapping[str, Any]) -> DataTableIndexSpec:
    if isinstance(value, DataTableIndexSpec):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("indexes must contain DataTableIndexSpec or mapping items")
    return DataTableIndexSpec(**dict(value))


def _normalize_schema_item(value: Mapping[str, Any], *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must contain mapping items")
    normalized = dict(value)
    schema_name = str(normalized.get("name", normalized.get("key", "")) or "").strip()
    if not _is_valid_name(schema_name):
        raise ValueError(f"{field_name} item name must be snake_case: {schema_name or '<empty>'}")
    return normalized


def _is_valid_name(name: str) -> bool:
    return bool(NAME_RE.match(str(name or "").strip()))

"""Core-native-v2 declaration decorators and metadata contracts."""

from __future__ import annotations

import ast
import datetime as dt
import inspect
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import UnionType
from typing import Annotated, Any, Literal, TypeVar, Union, get_args, get_origin, get_type_hints

from crawler4j_contracts.hosted_ui import PageSchema


CRAWLER4J_META_ATTR = "__crawler4j_meta__"
HOST_RESERVED_DATA_FIELDS = frozenset({"created_at", "updated_at", "create_at", "update_at"})
MANAGED_DATASET_RESERVED_DATA_FIELDS = HOST_RESERVED_DATA_FIELDS | frozenset(
    {"record_index", "record_key", "run_status", "record_status"}
)
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
DATA_TABLE_STORAGE_MODES = frozenset({"managed_dataset", "custom_table"})
DATA_TABLE_CLEANUP_POLICIES = frozenset({"delete_rows", "drop_table", "keep"})
DATA_VIEW_CLEANUP_POLICIES = frozenset({"drop_view", "keep"})
WORKFLOW_HOST_SCENARIOS = frozenset({"existing_env_import"})
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
    schema: dict[str, Any] = field(default_factory=dict)
    item_schema: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        name = str(self.name or "").strip()
        parameter_type = str(self.type or "string").strip().lower()
        options = tuple(_normalize_parameter_option(item) for item in _as_tuple(self.options))
        schema = _normalize_parameter_schema(self.schema, field_name="schema")
        item_schema = _normalize_parameter_schema(self.item_schema, field_name="item_schema")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "type", parameter_type)
        object.__setattr__(self, "label", str(self.label or "").strip())
        object.__setattr__(self, "description", str(self.description or "").strip())
        object.__setattr__(self, "options", options)
        object.__setattr__(self, "placeholder", str(self.placeholder or "").strip())
        object.__setattr__(self, "schema", schema)
        object.__setattr__(self, "item_schema", item_schema)
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
    schema: Mapping[str, Any] | None = None
    item_schema: Mapping[str, Any] | None = None


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
    storage_mode: str = ""
    record_key_field: str = ""
    cleanup_policy: str = ""
    env_binding_field: str = ""
    source: str = ""
    sources: tuple[str, ...] = field(default_factory=tuple)
    sql: str = ""
    icon: str = ""
    menu: bool = False
    order: int = 0
    page_schema: dict[str, Any] = field(default_factory=dict)
    host_scenarios: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        kind = str(self.kind or "").strip()
        name = str(self.name or "").strip()
        if kind not in {
            "interface",
            "component",
            "workflow",
            "page",
            "page_action",
            "ui_action",
            "data_table",
            "data_view",
            "env_candidates",
            "env_cleanup_candidates",
        }:
            raise ValueError(f"unsupported decorator kind: {kind or '<empty>'}")
        if not _is_valid_name(name):
            raise ValueError(f"{kind} name must be snake_case: {name or '<empty>'}")
        inject = tuple(_normalize_inject(item) for item in _as_tuple(self.inject))
        parameters = tuple(_normalize_parameter(item) for item in _as_tuple(self.parameters))
        page_schema = _normalize_page_schema_metadata(self.page_schema)
        if kind == "page" and not page_schema and isinstance(self.schema, Mapping):
            page_schema = _normalize_page_schema_metadata(self.schema)
            schema = ()
        else:
            schema = tuple(_normalize_schema_item(item, field_name="schema") for item in _as_tuple(self.schema))
        indexes = tuple(_normalize_index(item) for item in _as_tuple(self.indexes))
        storage_mode = str(self.storage_mode or "").strip().lower()
        record_key_field = str(self.record_key_field or "").strip()
        cleanup_policy = str(self.cleanup_policy or "").strip().lower()
        env_binding_field = str(self.env_binding_field or "").strip()
        if kind == "data_table":
            storage_mode = storage_mode or "custom_table"
            if storage_mode not in DATA_TABLE_STORAGE_MODES:
                raise ValueError(f"data_table storage_mode must be managed_dataset or custom_table: {storage_mode}")
            if record_key_field and not _is_valid_name(record_key_field):
                raise ValueError(f"data_table record_key_field must be snake_case: {record_key_field}")
            effective_record_key_field = record_key_field
            if not effective_record_key_field and schema:
                effective_record_key_field = str(schema[0].get("name") or schema[0].get("key") or "").strip()
            auto_increment_fields = [item for item in schema if bool(item.get("auto_increment"))]
            if auto_increment_fields:
                if storage_mode != "custom_table":
                    raise ValueError("data_table auto_increment is only supported for custom_table")
                if len(auto_increment_fields) > 1:
                    raise ValueError("data_table auto_increment can only be declared on the record_key_field")
                auto_increment_field = auto_increment_fields[0]
                auto_increment_name = str(
                    auto_increment_field.get("name") or auto_increment_field.get("key") or ""
                ).strip()
                if auto_increment_name != effective_record_key_field:
                    raise ValueError("data_table auto_increment can only be declared on the record_key_field")
                auto_increment_type = str(auto_increment_field.get("type") or "").strip().lower()
                if auto_increment_type not in {"integer", "int"}:
                    raise ValueError("data_table auto_increment record_key_field must be integer")
            if env_binding_field:
                if not _is_valid_name(env_binding_field):
                    raise ValueError(f"data_table env_binding_field must be snake_case: {env_binding_field}")
                schema_field = next(
                    (
                        item
                        for item in schema
                        if str(item.get("name") or item.get("key") or "").strip() == env_binding_field
                    ),
                    None,
                )
                if schema_field is None:
                    raise ValueError(f"data_table env_binding_field must exist in schema: {env_binding_field}")
                field_type = str(schema_field.get("type") or "").strip().lower()
                if field_type not in {"integer", "int"}:
                    raise ValueError(f"data_table env_binding_field must be integer: {env_binding_field}")
            cleanup_policy = cleanup_policy or ("delete_rows" if storage_mode == "managed_dataset" else "drop_table")
            if cleanup_policy not in DATA_TABLE_CLEANUP_POLICIES:
                raise ValueError(f"data_table cleanup_policy must be delete_rows, drop_table or keep: {cleanup_policy}")
        elif kind == "data_view":
            if any(bool(item.get("auto_increment")) for item in schema):
                raise ValueError("data_view schema does not support auto_increment")
            cleanup_policy = cleanup_policy or "drop_view"
            if cleanup_policy not in DATA_VIEW_CLEANUP_POLICIES:
                raise ValueError(f"data_view cleanup_policy must be drop_view or keep: {cleanup_policy}")
        else:
            storage_mode = ""
            record_key_field = ""
            cleanup_policy = ""
            env_binding_field = ""
        implements = str(self.implements or "").strip()
        source = str(self.source or "").strip()
        sources = tuple(str(item or "").strip() for item in _as_tuple(self.sources))
        for source_name in sources:
            if not _is_valid_name(source_name):
                raise ValueError(f"{kind} source must be snake_case: {source_name or '<empty>'}")
        host_scenarios = tuple(
            dict.fromkeys(str(item or "").strip() for item in _as_tuple(self.host_scenarios) if str(item or "").strip())
        )
        if host_scenarios and kind != "workflow":
            raise ValueError("host_scenarios is only supported by workflow decorators")
        for scenario in host_scenarios:
            if scenario not in WORKFLOW_HOST_SCENARIOS:
                raise ValueError(f"workflow host_scenarios contains unsupported scenario: {scenario}")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "label", str(self.label or "").strip())
        object.__setattr__(self, "description", str(self.description or "").strip())
        object.__setattr__(self, "implements", implements)
        object.__setattr__(self, "inject", inject)
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "schema", schema)
        object.__setattr__(self, "indexes", indexes)
        object.__setattr__(self, "storage_mode", storage_mode)
        object.__setattr__(self, "record_key_field", record_key_field)
        object.__setattr__(self, "cleanup_policy", cleanup_policy)
        object.__setattr__(self, "env_binding_field", env_binding_field)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "sources", sources)
        object.__setattr__(self, "sql", str(self.sql or "").strip())
        object.__setattr__(self, "icon", str(self.icon or "").strip())
        object.__setattr__(self, "menu", bool(self.menu))
        object.__setattr__(self, "order", int(self.order or 0))
        object.__setattr__(self, "page_schema", page_schema)
        object.__setattr__(self, "host_scenarios", host_scenarios)
        if kind == "component" and not _is_valid_name(implements):
            raise ValueError("component implements must reference an interface")
        if kind == "page" and not page_schema:
            raise ValueError("page schema cannot be empty")
        if kind == "data_table" and not schema:
            raise ValueError("data_table schema cannot be empty")
        if kind == "data_view":
            if not sources:
                raise ValueError("data_view sources cannot be empty")
            if not schema:
                raise ValueError("data_view schema cannot be empty")
            if not str(self.sql or "").strip():
                raise ValueError("data_view sql cannot be empty")


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
    schema: Mapping[str, Any] | None = None,
    item_schema: Mapping[str, Any] | None = None,
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
        schema=schema,
        item_schema=item_schema,
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
    host_scenarios: Iterable[str] | None = None,
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
            host_scenarios=tuple(_as_tuple(host_scenarios)),
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
    """Declare an automated browser page action function."""
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


def ui_action(
    *,
    name: str,
    label: str = "",
    description: str = "",
    inject: Iterable[InjectSpec | Mapping[str, Any]] | None = None,
    parameters: Iterable[ParameterSpec | Mapping[str, Any]] | None = None,
) -> Callable[[TargetT], TargetT]:
    """Declare a hosted UI command function."""
    return _decorate(
        Crawler4jMeta(
            kind="ui_action",
            name=name,
            label=label,
            description=description,
            inject=tuple(_as_tuple(inject)),
            parameters=tuple(_as_tuple(parameters)),
        )
    )


def env_candidates(
    *,
    name: str,
    label: str = "",
    description: str = "",
) -> Callable[[TargetT], TargetT]:
    """Declare a pure environment candidate provider."""
    return _decorate(Crawler4jMeta(kind="env_candidates", name=name, label=label, description=description))


def env_cleanup_candidates(
    *,
    name: str,
    label: str = "",
    description: str = "",
) -> Callable[[TargetT], TargetT]:
    """Declare a pure environment cleanup candidate provider."""
    return _decorate(Crawler4jMeta(kind="env_cleanup_candidates", name=name, label=label, description=description))


def page(
    *,
    name: str,
    label: str = "",
    description: str = "",
    icon: str = "📄",
    menu: bool = True,
    order: int = 0,
    schema: PageSchema | Mapping[str, Any],
) -> Callable[[TargetT], TargetT]:
    """Declare a hosted UI page with the decorated function as its load handler."""
    return _decorate(
        Crawler4jMeta(
            kind="page",
            name=name,
            label=label,
            description=description,
            icon=icon,
            menu=menu,
            order=order,
            page_schema=dict(schema),
        )
    )


def data_table(
    *,
    name: str,
    schema: Iterable[Mapping[str, Any]],
    label: str = "",
    description: str = "",
    storage_mode: Literal["managed_dataset", "custom_table"] = "custom_table",
    record_key_field: str = "",
    cleanup_policy: Literal["delete_rows", "drop_table", "keep"] | str = "",
    env_binding_field: str = "",
    indexes: Iterable[DataTableIndexSpec | Mapping[str, Any]] | None = None,
) -> Callable[[TargetT], TargetT]:
    """Declare a table-shaped data contract."""
    return _decorate(
        Crawler4jMeta(
            kind="data_table",
            name=name,
            label=label,
            description=description,
            storage_mode=storage_mode,
            record_key_field=record_key_field,
            cleanup_policy=cleanup_policy,
            env_binding_field=env_binding_field,
            schema=tuple(_as_tuple(schema)),
            indexes=tuple(_as_tuple(indexes)),
        )
    )


def data_view(
    *,
    name: str,
    sources: Iterable[str] | str,
    sql: str,
    schema: Iterable[Mapping[str, Any]],
    label: str = "",
    description: str = "",
    cleanup_policy: Literal["drop_view", "keep"] | str = "drop_view",
) -> Callable[[TargetT], TargetT]:
    """Declare a read-only SQL view over custom_table resources."""
    normalized_sources = (sources,) if isinstance(sources, str) else tuple(_as_tuple(sources))
    return _decorate(
        Crawler4jMeta(
            kind="data_view",
            name=name,
            label=label,
            description=description,
            sources=tuple(str(item or "").strip() for item in normalized_sources),
            sql=sql,
            schema=tuple(_as_tuple(schema)),
            cleanup_policy=cleanup_policy,
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
        storage_mode=meta.storage_mode,
        record_key_field=meta.record_key_field,
        cleanup_policy=meta.cleanup_policy,
        env_binding_field=meta.env_binding_field,
        source=meta.source,
        sources=meta.sources,
        sql=meta.sql,
        icon=meta.icon,
        menu=meta.menu,
        order=meta.order,
        page_schema=meta.page_schema,
        host_scenarios=meta.host_scenarios,
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
    inferred = _parameter_shape_from_type(type_hint)
    default_supplied = marker.default is not _MISSING or fallback_default is not _MISSING
    default = marker.default if marker.default is not _MISSING else fallback_default
    if default is _MISSING:
        default = None
    required = marker.required if marker.required is not None else not default_supplied and not inferred["optional"]
    options = tuple(_as_tuple(marker.options)) or tuple(_as_tuple(inferred["options"]))
    return ParameterSpec(
        name=marker.name or fallback_name,
        type=marker.type or inferred["type"] or "string",
        label=marker.label,
        description=marker.description,
        required=bool(required),
        default=default,
        options=options,
        min=marker.min,
        max=marker.max,
        step=marker.step,
        placeholder=marker.placeholder,
        schema=dict(marker.schema or inferred["schema"] or {}),
        item_schema=dict(marker.item_schema or inferred["item_schema"] or {}),
    )


def _parameter_shape_from_type(type_hint: Any) -> dict[str, Any]:
    inferred: dict[str, Any] = {
        "type": _infer_parameter_type(type_hint),
        "schema": {},
        "item_schema": {},
        "options": (),
        "optional": False,
    }
    if isinstance(type_hint, str):
        return _parameter_shape_from_string(type_hint, inferred)

    origin = get_origin(type_hint)
    args = get_args(type_hint)
    if origin in {Union, UnionType}:
        concrete_args = tuple(item for item in args if item is not type(None))
        if len(concrete_args) != len(args):
            inferred["optional"] = True
        if len(concrete_args) == 1:
            nested = _parameter_shape_from_type(concrete_args[0])
            nested["optional"] = bool(inferred["optional"] or nested["optional"])
            return nested

    if origin is Literal:
        options = tuple(ParameterOptionSpec(label=str(item), value=item) for item in args)
        inferred.update({"type": "enum", "options": options})
        return inferred

    if origin in {list, tuple, set, frozenset}:
        item_type = _homogeneous_collection_item(args)
        if item_type is not None:
            inferred["item_schema"] = _schema_from_type(item_type)
        inferred["type"] = "array"
        return inferred

    if origin in {dict, Mapping}:
        if len(args) >= 2:
            value_schema = _schema_from_type(args[1])
            if value_schema.get("type"):
                inferred["schema"] = {"additional_type": value_schema["type"]}
        inferred["type"] = "object"
        return inferred

    return inferred


def _parameter_shape_from_string(type_hint: str, inferred: dict[str, Any]) -> dict[str, Any]:
    text = type_hint.strip()
    lower_text = text.lower()
    if lower_text.endswith(" | none") or lower_text.startswith("optional["):
        inferred["optional"] = True
    if lower_text.startswith(("list[", "tuple[", "set[")):
        inferred["type"] = "array"
        inner = text[text.find("[") + 1 : -1].strip()
        item_schema = _schema_from_type(inner)
        if item_schema.get("type"):
            inferred["item_schema"] = item_schema
    elif lower_text.startswith(("dict[", "mapping[")):
        inferred["type"] = "object"
        inner = text[text.find("[") + 1 : -1].strip()
        parts = [item.strip() for item in inner.split(",", 1)]
        if len(parts) == 2:
            value_schema = _schema_from_type(parts[1])
            if value_schema.get("type"):
                inferred["schema"] = {"additional_type": value_schema["type"]}
    return inferred


def _schema_from_type(type_hint: Any) -> dict[str, Any]:
    shape = _parameter_shape_from_type(type_hint)
    schema: dict[str, Any] = {"type": shape["type"] or "string"}
    if shape["schema"]:
        schema["schema"] = shape["schema"]
    if shape["item_schema"]:
        schema["item_schema"] = shape["item_schema"]
    return schema


def _homogeneous_collection_item(args: tuple[Any, ...]) -> Any | None:
    if not args:
        return None
    if len(args) == 2 and args[1] is Ellipsis:
        return args[0]
    if len(args) == 1:
        return args[0]
    return None


def _infer_parameter_type(type_hint: Any) -> str:
    mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        tuple: "array",
        dict: "object",
        Mapping: "object",
        dt.date: "date",
        dt.datetime: "datetime",
        dt.time: "time",
        Path: "path",
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "list": "array",
        "List": "array",
        "tuple": "array",
        "Tuple": "array",
        "dict": "object",
        "Dict": "object",
        "Mapping": "object",
        "date": "date",
        "datetime": "datetime",
        "time": "time",
        "Path": "path",
        "pathlib.Path": "path",
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


def _normalize_parameter_schema(value: Mapping[str, Any] | None, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError(f"parameter {field_name} must be a mapping")
    return dict(value)


def _normalize_page_schema_metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("page schema must be a mapping")
    return dict(value)


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

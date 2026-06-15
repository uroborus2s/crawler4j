"""Reusable core-native-v2 decorator scanner and diagnostics."""

from __future__ import annotations

import ast
import datetime as dt
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from crawler4j_contracts import (
    HOST_RESERVED_DATA_FIELDS,
    MANAGED_DATASET_RESERVED_DATA_FIELDS,
    Crawler4jMeta,
    InjectSpec,
    ParameterSpec,
)
from crawler4j_contracts.hosted_ui import normalize_page_schema

CORE_NATIVE_V2_RUNTIME_API = "core-native-v2"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
V2_SCAN_DIRECTORIES = ("interfaces", "objects", "workflows", "tasks", "data", "pages", "candidates", "cleanups")
IGNORED_PATH_PARTS = {
    ".git",
    ".idea",
    ".venv",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".crawler4j",
    "build",
    "dist",
    "tests",
}
LEGACY_RUNTIME_DIRECTORIES = ("hooks", "env_selectors")
LEGACY_SPEC_NAMES = {"TaskSpec", "WorkflowSpec", "EnvSelectorSpec", "PageSpec"}
LEGACY_DECLARATION_NAMES = {"TASK", "WORKFLOW", "SELECTOR", "PAGE"}
HOST_FLOW_CONTROL_NAMES = {"EnvAction", "TaskSignal", "TaskSignalAction"}
REMOVED_OBJECT_LIFECYCLE_METHODS = {"aclose", "close"}
MANAGED_DATASET_DERIVED_FIELD_SUFFIXES = ("_label", "_display", "_masked")
DECORATOR_KINDS = {
    "interface": "interface",
    "component": "component",
    "workflow": "workflow",
    "page": "page",
    "page_action": "page_action",
    "ui_action": "ui_action",
    "data_table": "data_table",
    "data_view": "data_view",
    "env_candidates": "env_candidates",
    "env_cleanup_candidates": "env_cleanup_candidates",
}
_MISSING = object()


@dataclass(frozen=True)
class V2Diagnostic:
    """Stable diagnostic emitted by the v2 scanner."""

    code: str
    message: str
    location: str = ""
    severity: str = "error"

    def render(self) -> str:
        """Render a stable one-line CLI message."""
        if self.location:
            return f"{self.code} {self.location}: {self.message}"
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class V2Declaration:
    """Decorator metadata discovered in module source."""

    kind: str
    name: str
    symbol: str
    source_path: str
    meta: Crawler4jMeta
    target_kind: str
    annotations: tuple[str, ...] = ()
    methods: tuple[str, ...] = ()
    method_signatures: tuple["V2MethodSignature", ...] = ()
    target: Any = None


@dataclass(frozen=True)
class V2MethodSignature:
    """Static method signature shape used by scanner diagnostics."""

    name: str
    positional_args: tuple[str, ...]
    has_varargs: bool = False


@dataclass(frozen=True)
class V2FunctionSignature:
    """Top-level runtime function signature discovered in a module."""

    name: str
    source_path: str
    is_async: bool
    positional_args: tuple[str, ...]
    positional_default_count: int = 0
    kwonly_args: tuple[str, ...] = ()
    required_kwonly_args: tuple[str, ...] = ()
    has_varargs: bool = False
    has_varkw: bool = False
    parameter_annotations: dict[str, str] | None = None


@dataclass(frozen=True)
class V2ScanResult:
    """Result returned by the core-native-v2 scanner."""

    module_root: Path
    runtime_api: str
    declarations: tuple[V2Declaration, ...]
    diagnostics: tuple[V2Diagnostic, ...]

    def error_messages(self) -> list[str]:
        """Return CLI-compatible error messages."""
        return [diagnostic.render() for diagnostic in self.diagnostics if diagnostic.severity == "error"]


def scan_v2_module(module_root: Path, manifest: dict[str, Any] | None = None) -> V2ScanResult:
    """Scan a core-native-v2 module for decorator declarations and diagnostics."""
    root = module_root.resolve()
    resolved_manifest = dict(manifest or {})
    runtime_api = str(resolved_manifest.get("runtime_api", "") or "").strip()
    diagnostics = _collect_manifest_diagnostics(resolved_manifest)
    diagnostics.extend(_collect_static_diagnostics(root))
    declarations: list[V2Declaration] = []

    module_name = _resolve_module_import_name(root, resolved_manifest)
    parsed_modules, parse_diagnostics = _parse_python_modules(root)
    diagnostics.extend(parse_diagnostics)
    module_functions = _collect_module_function_signatures(parsed_modules)
    collected_declarations, declaration_diagnostics = _collect_declarations(module_name, parsed_modules)
    declarations.extend(collected_declarations)
    diagnostics.extend(declaration_diagnostics)
    diagnostics.extend(_validate_declarations(declarations, module_functions))

    return V2ScanResult(
        module_root=root,
        runtime_api=runtime_api,
        declarations=tuple(declarations),
        diagnostics=tuple(diagnostics),
    )


def _collect_manifest_diagnostics(manifest: dict[str, Any]) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    runtime_api = str(manifest.get("runtime_api", "") or "").strip()
    if runtime_api != CORE_NATIVE_V2_RUNTIME_API:
        diagnostics.append(
            V2Diagnostic(
                code="V2_RUNTIME_API_INVALID",
                location="module.yaml.runtime_api",
                message=f"expected {CORE_NATIVE_V2_RUNTIME_API}",
            )
        )

    if "default_workflow" in manifest:
        diagnostics.append(
            V2Diagnostic(
                code="V2_MANIFEST_LEGACY_DEFAULT_WORKFLOW",
                location="module.yaml.default_workflow",
                message="default workflow is declared with @workflow decorators in core-native-v2",
            )
        )

    workflows = manifest.get("workflows")
    if isinstance(workflows, list):
        diagnostics.append(
            V2Diagnostic(
                code="V2_MANIFEST_LEGACY_WORKFLOWS",
                location="module.yaml.workflows",
                message="workflows must be declared with core-native-v2 decorators",
            )
        )
        for index, workflow in enumerate(workflows):
            if not isinstance(workflow, dict) or "parameters" not in workflow:
                continue
            workflow_name = str(workflow.get("name", "") or index).strip()
            diagnostics.append(
                V2Diagnostic(
                    code="V2_MANIFEST_LEGACY_WORKFLOW_PARAMETERS",
                    location=f"module.yaml.workflows[{workflow_name}].parameters",
                    message="workflow parameters must be declared by component decorators, not module.yaml",
                )
            )
    elif workflows is not None:
        diagnostics.append(
            V2Diagnostic(
                code="V2_MANIFEST_INVALID_WORKFLOWS",
                location="module.yaml.workflows",
                message="workflows must be a list when present",
            )
        )

    for key, code in (
        ("data", "V2_MANIFEST_LEGACY_DATA"),
        ("objects", "V2_MANIFEST_LEGACY_OBJECTS"),
        ("interfaces", "V2_MANIFEST_LEGACY_INTERFACES"),
        ("tasks", "V2_MANIFEST_LEGACY_TASKS"),
        ("ui_extension", "V2_MANIFEST_LEGACY_UI_EXTENSION"),
        ("resource_pools", "V2_MANIFEST_LEGACY_RESOURCE_POOLS"),
    ):
        if key in manifest:
            diagnostics.append(
                V2Diagnostic(
                    code=code,
                    location=f"module.yaml.{key}",
                    message=f"{key} must be declared with core-native-v2 decorators",
                )
            )

    return diagnostics


def _collect_static_diagnostics(module_root: Path) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    seen_sdk_imports: set[str] = set()
    seen_legacy_imports: set[str] = set()
    seen_host_flow_imports: set[str] = set()
    for directory_name in LEGACY_RUNTIME_DIRECTORIES:
        if (module_root / directory_name).exists():
            diagnostics.append(
                V2Diagnostic(
                    code="V2_LEGACY_RUNTIME_DIRECTORY",
                    location=directory_name,
                    message=f"core-native-v2 does not support legacy {directory_name}/ runtime entries",
                )
            )

    for path in _iter_runtime_python_files(module_root):
        relative = path.relative_to(module_root)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            diagnostics.append(
                V2Diagnostic(
                    code="V2_SYNTAX_ERROR",
                    location=relative.as_posix(),
                    message=str(exc),
                )
            )
            continue
        for node in ast.walk(tree):
            sdk_import = False
            legacy_specs: set[str] = set()
            if isinstance(node, ast.Import):
                sdk_import = any(
                    alias.name == "crawler4j_sdk" or alias.name.startswith("crawler4j_sdk.") for alias in node.names
                )
                for alias in node.names:
                    if alias.name == "crawler4j_contracts.signal":
                        _append_host_flow_control_import_diagnostic(
                            diagnostics,
                            seen_host_flow_imports,
                            relative.as_posix(),
                            "crawler4j_contracts.signal",
                        )
            elif isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                sdk_import = module == "crawler4j_sdk" or module.startswith("crawler4j_sdk.")
                if module == "crawler4j_contracts.specs":
                    legacy_specs.update(alias.name for alias in node.names if alias.name in LEGACY_SPEC_NAMES)
                elif module == "crawler4j_contracts":
                    legacy_specs.update(alias.name for alias in node.names if alias.name in LEGACY_SPEC_NAMES)
                if module in {"crawler4j_contracts", "crawler4j_contracts.signal"}:
                    imported_names = {alias.name for alias in node.names}
                    blocked_names = (
                        HOST_FLOW_CONTROL_NAMES
                        if "*" in imported_names
                        else HOST_FLOW_CONTROL_NAMES.intersection(imported_names)
                    )
                    for blocked_name in sorted(blocked_names):
                        _append_host_flow_control_import_diagnostic(
                            diagnostics,
                            seen_host_flow_imports,
                            relative.as_posix(),
                            blocked_name,
                        )
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in LEGACY_DECLARATION_NAMES:
                        diagnostics.append(
                            V2Diagnostic(
                                code="V2_LEGACY_RUNTIME_DECLARATION",
                                location=f"{relative.as_posix()}:{node.lineno}",
                                message=f"{target.id} declarations are removed in core-native-v2",
                            )
                        )
            if not sdk_import:
                location = relative.as_posix()
            else:
                location = relative.as_posix()
                if location not in seen_sdk_imports:
                    seen_sdk_imports.add(location)
                    diagnostics.append(
                        V2Diagnostic(
                            code="V2_RUNTIME_SDK_IMPORT",
                            location=location,
                            message="runtime module code must not import crawler4j_sdk",
                        )
                    )
            for spec_name in sorted(legacy_specs):
                key = f"{location}:{spec_name}"
                if key in seen_legacy_imports:
                    continue
                seen_legacy_imports.add(key)
                diagnostics.append(
                    V2Diagnostic(
                        code="V2_LEGACY_CONTRACT_IMPORT",
                        location=location,
                        message=f"{spec_name} is removed from core-native-v2 runtime contracts",
                    )
                )
    return diagnostics


def _append_host_flow_control_import_diagnostic(
    diagnostics: list[V2Diagnostic],
    seen: set[str],
    location: str,
    symbol: str,
) -> None:
    key = f"{location}:{symbol}"
    if key in seen:
        return
    seen.add(key)
    diagnostics.append(
        V2Diagnostic(
            code="V2_HOST_FLOW_CONTROL_IMPORT",
            location=location,
            message=f"{symbol} is host-owned and cannot be imported by module runtime code",
        )
    )


def _resolve_module_import_name(module_root: Path, manifest: dict[str, Any]) -> str:
    module_name = str(manifest.get("name", "") or "").strip()
    return module_name or module_root.name


def _parse_python_modules(
    module_root: Path,
) -> tuple[list[tuple[Path, ast.Module]], list[V2Diagnostic]]:
    diagnostics: list[V2Diagnostic] = []
    modules: list[tuple[Path, ast.Module]] = []

    for path in _iter_python_files(module_root):
        relative = path.relative_to(module_root)
        try:
            module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            diagnostics.append(
                V2Diagnostic(
                    code="V2_SYNTAX_ERROR",
                    location=relative.as_posix(),
                    message=str(exc),
                )
            )
            continue
        modules.append((relative, module))

    return modules, diagnostics


def _iter_python_files(module_root: Path) -> list[Path]:
    paths = []
    root_init = module_root / "__init__.py"
    if root_init.exists():
        paths.append(root_init)
    for directory_name in V2_SCAN_DIRECTORIES:
        directory = module_root / directory_name
        if not directory.exists():
            continue
        for path in directory.rglob("*.py"):
            relative = path.relative_to(module_root)
            if path.name == "__init__.py" or path.name.startswith("_"):
                continue
            if any(part in IGNORED_PATH_PARTS for part in relative.parts):
                continue
            paths.append(path)
    return sorted(paths, key=lambda item: (item.relative_to(module_root).parts != ("__init__.py",), item.as_posix()))


def _iter_runtime_python_files(module_root: Path) -> list[Path]:
    paths = []
    for path in module_root.rglob("*.py"):
        relative = path.relative_to(module_root)
        if any(part in IGNORED_PATH_PARTS for part in relative.parts):
            continue
        paths.append(path)
    return sorted(paths)


def _import_name_for_path(package_name: str, relative: Path) -> str:
    if relative.name == "__init__.py":
        parts = relative.parent.parts
    else:
        parts = relative.with_suffix("").parts
    if not parts:
        return package_name
    return ".".join((package_name, *parts))


def _collect_declarations(
    package_name: str,
    parsed_modules: list[tuple[Path, ast.Module]],
) -> tuple[list[V2Declaration], list[V2Diagnostic]]:
    declarations: list[V2Declaration] = []
    diagnostics: list[V2Diagnostic] = []
    for relative, module in parsed_modules:
        if relative.parts == ("__init__.py",):
            continue
        module_name = _import_name_for_path(package_name, relative)
        for node in module.body:
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            try:
                meta = _metadata_from_decorators(node.decorator_list)
            except (TypeError, ValueError) as exc:
                diagnostics.append(
                    V2Diagnostic(
                        code="V2_DECORATOR_INVALID",
                        location=f"{relative.as_posix()}:{node.lineno}",
                        message=str(exc),
                    )
                )
                continue
            if meta is None:
                continue
            if isinstance(node, ast.ClassDef):
                try:
                    meta = _merge_annotation_metadata(meta, node)
                except (TypeError, ValueError) as exc:
                    diagnostics.append(
                        V2Diagnostic(
                            code="V2_DECORATOR_INVALID",
                            location=f"{relative.as_posix()}:{node.lineno}",
                            message=str(exc),
                        )
                    )
                    continue
            declarations.append(
                V2Declaration(
                    kind=meta.kind,
                    name=meta.name,
                    symbol=_symbol_label(package_name, module_name, node.name),
                    source_path=relative.as_posix(),
                    meta=meta,
                    target_kind=_target_kind(node),
                    annotations=_class_annotations(node) if isinstance(node, ast.ClassDef) else (),
                    methods=_class_methods(node) if isinstance(node, ast.ClassDef) else (),
                    method_signatures=_class_method_signatures(node) if isinstance(node, ast.ClassDef) else (),
                )
            )
    return declarations, diagnostics


def _collect_module_function_signatures(
    parsed_modules: list[tuple[Path, ast.Module]],
) -> dict[str, dict[str, V2FunctionSignature]]:
    functions_by_path: dict[str, dict[str, V2FunctionSignature]] = {}
    for relative, module in parsed_modules:
        module_functions: dict[str, V2FunctionSignature] = {}
        for node in module.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            positional_args = (*node.args.posonlyargs, *node.args.args)
            all_args = (*positional_args, *node.args.kwonlyargs)
            required_kwonly_args = tuple(
                arg.arg
                for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True)
                if default is None
            )
            module_functions[node.name] = V2FunctionSignature(
                name=node.name,
                source_path=relative.as_posix(),
                is_async=isinstance(node, ast.AsyncFunctionDef),
                positional_args=tuple(arg.arg for arg in positional_args),
                positional_default_count=len(node.args.defaults),
                kwonly_args=tuple(arg.arg for arg in node.args.kwonlyargs),
                required_kwonly_args=required_kwonly_args,
                has_varargs=node.args.vararg is not None,
                has_varkw=node.args.kwarg is not None,
                parameter_annotations={
                    arg.arg: _annotation_to_source(arg.annotation) for arg in all_args if arg.annotation is not None
                },
            )
        functions_by_path[relative.as_posix()] = module_functions
    return functions_by_path


def _metadata_from_decorators(decorators: list[ast.expr]) -> Crawler4jMeta | None:
    for decorator in decorators:
        if not isinstance(decorator, ast.Call):
            continue
        decorator_name = _decorator_name(decorator.func)
        kind = DECORATOR_KINDS.get(decorator_name)
        if kind is None:
            continue
        kwargs: dict[str, Any] = {}
        for keyword in decorator.keywords:
            if keyword.arg is None:
                raise ValueError(f"{decorator_name} decorator does not support **kwargs")
            kwargs[keyword.arg] = ast.literal_eval(keyword.value)
        if decorator.args:
            raise ValueError(f"{decorator_name} decorator does not support positional arguments")
        return Crawler4jMeta(kind=kind, **kwargs)
    return None


def _decorator_name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _target_kind(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    if isinstance(node, ast.ClassDef):
        return "class"
    if isinstance(node, ast.AsyncFunctionDef):
        return "async_function"
    return "function"


def _class_annotations(node: ast.ClassDef) -> tuple[str, ...]:
    names: list[str] = []
    for item in node.body:
        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
            names.append(item.target.id)
    return tuple(sorted(names))


def _class_methods(node: ast.ClassDef) -> tuple[str, ...]:
    names: list[str] = []
    for item in node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.append(item.name)
    return tuple(sorted(names))


def _class_method_signatures(node: ast.ClassDef) -> tuple[V2MethodSignature, ...]:
    signatures: list[V2MethodSignature] = []
    for item in node.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        positional_args = (*item.args.posonlyargs, *item.args.args)
        signatures.append(
            V2MethodSignature(
                name=item.name,
                positional_args=tuple(arg.arg for arg in positional_args),
                has_varargs=item.args.vararg is not None,
            )
        )
    return tuple(sorted(signatures, key=lambda item: item.name))


def _merge_annotation_metadata(meta: Crawler4jMeta, node: ast.ClassDef) -> Crawler4jMeta:
    inject, parameters = _annotation_metadata_from_class(node)
    if not inject and not parameters:
        return meta
    return Crawler4jMeta(
        kind=meta.kind,
        name=meta.name,
        label=meta.label,
        description=meta.description,
        implements=meta.implements,
        inject=_merge_named_specs(meta.inject, inject),
        parameters=_merge_named_specs(meta.parameters, parameters),
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


def _annotation_metadata_from_class(node: ast.ClassDef) -> tuple[tuple[InjectSpec, ...], tuple[ParameterSpec, ...]]:
    inject: list[InjectSpec] = []
    parameters: list[ParameterSpec] = []

    for item in node.body:
        if not isinstance(item, ast.AnnAssign) or not isinstance(item.target, ast.Name):
            continue
        item_inject, item_parameter = _spec_from_annotation(
            item.target.id,
            item.annotation,
            fallback_default=_literal_or_missing(item.value),
        )
        if item_inject is not None:
            inject.append(item_inject)
        if item_parameter is not None:
            parameters.append(item_parameter)

    init_node = _find_init_node(node)
    if init_node is not None:
        defaults = _function_default_map(init_node)
        for arg in [*init_node.args.posonlyargs, *init_node.args.args, *init_node.args.kwonlyargs]:
            if arg.arg == "self" or arg.annotation is None:
                continue
            item_inject, item_parameter = _spec_from_annotation(
                arg.arg,
                arg.annotation,
                fallback_default=defaults.get(arg.arg, _MISSING),
            )
            if item_inject is not None:
                inject.append(item_inject)
            if item_parameter is not None:
                parameters.append(item_parameter)

    return tuple(inject), tuple(parameters)


def _find_init_node(node: ast.ClassDef) -> ast.FunctionDef | None:
    for item in node.body:
        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
            return item
    return None


def _function_default_map(node: ast.FunctionDef) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    positional = [*node.args.posonlyargs, *node.args.args]
    if node.args.defaults:
        default_args = positional[-len(node.args.defaults) :]
        for arg, default in zip(default_args, node.args.defaults, strict=True):
            defaults[arg.arg] = _literal_or_missing(default)
    for arg, default in zip(node.args.kwonlyargs, node.args.kw_defaults, strict=True):
        defaults[arg.arg] = _literal_or_missing(default)
    return defaults


def _spec_from_annotation(
    fallback_name: str,
    annotation: ast.expr,
    *,
    fallback_default: Any,
) -> tuple[InjectSpec | None, ParameterSpec | None]:
    marker, type_expr = _annotation_marker(annotation)
    if marker is None:
        return None, None
    marker_name, marker_kwargs = marker
    if marker_name == "object_inject":
        return (
            InjectSpec(
                name=str(marker_kwargs.get("name") or fallback_name),
                type=str(marker_kwargs.get("type") or "interface"),
                target=str(marker_kwargs.get("target") or ""),
            ),
            None,
        )
    if marker_name == "object_param":
        return None, _parameter_from_annotation(
            marker_kwargs,
            fallback_name=fallback_name,
            type_expr=type_expr,
            fallback_default=fallback_default,
        )
    return None, None


def _annotation_marker(annotation: ast.expr) -> tuple[tuple[str, dict[str, Any]] | None, ast.expr | None]:
    if isinstance(annotation, ast.Call):
        marker = _marker_call(annotation)
        if marker is not None:
            return marker, None

    if isinstance(annotation, ast.Subscript) and _annotation_name(annotation.value) == "Annotated":
        elements = _subscript_elements(annotation.slice)
        if not elements:
            return None, None
        for item in elements[1:]:
            if isinstance(item, ast.Call):
                marker = _marker_call(item)
                if marker is not None:
                    return marker, elements[0]
    return None, None


def _marker_call(node: ast.Call) -> tuple[str, dict[str, Any]] | None:
    marker_name = _annotation_name(node.func)
    if marker_name not in {"object_param", "object_inject"}:
        return None
    if node.args:
        raise ValueError(f"{marker_name} annotation does not support positional arguments")
    kwargs: dict[str, Any] = {}
    for keyword in node.keywords:
        if keyword.arg is None:
            raise ValueError(f"{marker_name} annotation does not support **kwargs")
        kwargs[keyword.arg] = ast.literal_eval(keyword.value)
    return marker_name, kwargs


def _annotation_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def _annotation_to_source(node: ast.expr) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return _annotation_name(node)


def _subscript_elements(node: ast.expr) -> list[ast.expr]:
    if isinstance(node, ast.Tuple):
        return list(node.elts)
    return [node]


def _parameter_from_annotation(
    kwargs: dict[str, Any],
    *,
    fallback_name: str,
    type_expr: ast.expr | None,
    fallback_default: Any,
) -> ParameterSpec:
    inferred = _parameter_shape_from_annotation(type_expr)
    default_marker = kwargs.get("default", _MISSING)
    default_supplied = default_marker is not _MISSING or fallback_default is not _MISSING
    default = default_marker if default_marker is not _MISSING else fallback_default
    if default is _MISSING:
        default = None
    required_value = kwargs.get("required", _MISSING)
    required = (
        bool(required_value) if required_value is not _MISSING else not default_supplied and not inferred["optional"]
    )
    options = tuple(_as_tuple(kwargs.get("options"))) or tuple(_as_tuple(inferred["options"]))
    return ParameterSpec(
        name=str(kwargs.get("name") or fallback_name),
        type=str(kwargs.get("type") or inferred["type"] or "string"),
        label=str(kwargs.get("label") or ""),
        description=str(kwargs.get("description") or ""),
        required=required,
        default=default,
        options=options,
        min=kwargs.get("min"),
        max=kwargs.get("max"),
        step=kwargs.get("step"),
        placeholder=str(kwargs.get("placeholder") or ""),
        schema=dict(kwargs.get("schema") or inferred["schema"] or {}),
        item_schema=dict(kwargs.get("item_schema") or inferred["item_schema"] or {}),
    )


def _parameter_shape_from_annotation(node: ast.expr | None) -> dict[str, Any]:
    inferred: dict[str, Any] = {
        "type": _infer_parameter_type(node),
        "schema": {},
        "item_schema": {},
        "options": (),
        "optional": False,
    }
    if node is None:
        return inferred

    union_items = _union_items(node)
    if union_items is not None:
        concrete_items = tuple(item for item in union_items if not _is_none_annotation(item))
        if len(concrete_items) != len(union_items):
            inferred["optional"] = True
        if len(concrete_items) == 1:
            nested = _parameter_shape_from_annotation(concrete_items[0])
            nested["optional"] = bool(inferred["optional"] or nested["optional"])
            return nested

    if isinstance(node, ast.Subscript):
        type_name = _annotation_name(node.value)
        elements = _subscript_elements(node.slice)
        if type_name == "Literal":
            values = tuple(ast.literal_eval(item) for item in elements)
            inferred.update(
                {
                    "type": "enum",
                    "options": tuple({"label": str(value), "value": value} for value in values),
                }
            )
            return inferred
        if type_name in {"list", "List", "Sequence", "tuple", "Tuple", "set", "Set"}:
            item_expr = _homogeneous_collection_item(elements)
            if item_expr is not None:
                inferred["item_schema"] = _schema_from_annotation(item_expr)
            inferred["type"] = "array"
            return inferred
        if type_name in {"dict", "Dict", "Mapping"}:
            if len(elements) >= 2:
                value_schema = _schema_from_annotation(elements[1])
                if value_schema.get("type"):
                    inferred["schema"] = {"additional_type": value_schema["type"]}
            inferred["type"] = "object"
            return inferred

    return inferred


def _infer_parameter_type(node: ast.expr | None) -> str:
    if node is None:
        return ""
    type_name = _annotation_name(node)
    return {
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
    }.get(type_name, "")


def _schema_from_annotation(node: ast.expr | None) -> dict[str, Any]:
    shape = _parameter_shape_from_annotation(node)
    schema: dict[str, Any] = {"type": shape["type"] or "string"}
    if shape["schema"]:
        schema["schema"] = shape["schema"]
    if shape["item_schema"]:
        schema["item_schema"] = shape["item_schema"]
    return schema


def _homogeneous_collection_item(elements: list[ast.expr]) -> ast.expr | None:
    if not elements:
        return None
    if len(elements) == 2 and isinstance(elements[1], ast.Constant) and elements[1].value is Ellipsis:
        return elements[0]
    if len(elements) == 1:
        return elements[0]
    return None


def _union_items(node: ast.expr) -> tuple[ast.expr, ...] | None:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        left = _union_items(node.left) or (node.left,)
        right = _union_items(node.right) or (node.right,)
        return (*left, *right)
    if isinstance(node, ast.Subscript) and _annotation_name(node.value) in {"Optional", "Union"}:
        return tuple(_subscript_elements(node.slice))
    return None


def _is_none_annotation(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is None or _annotation_name(node) == "None"


def _literal_or_missing(node: ast.expr | None) -> Any:
    if node is None:
        return _MISSING
    try:
        return ast.literal_eval(node)
    except (TypeError, ValueError):
        return _MISSING


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


def _symbol_label(package_name: str, module_name: str, attr_name: str) -> str:
    if module_name == package_name:
        module_label = "__init__"
    elif module_name.startswith(f"{package_name}."):
        module_label = module_name[len(package_name) + 1 :]
    else:
        module_label = module_name
    return f"{module_label}.{attr_name}"


def _validate_declarations(
    declarations: list[V2Declaration],
    module_functions: dict[str, dict[str, V2FunctionSignature]],
) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    diagnostics.extend(_validate_required_workflow(declarations))
    diagnostics.extend(_validate_duplicate_names(declarations))
    diagnostics.extend(_validate_interface_implementations(declarations))
    diagnostics.extend(_validate_injection_targets(declarations))
    diagnostics.extend(_validate_pages(declarations, module_functions))
    diagnostics.extend(_validate_page_actions(declarations))
    diagnostics.extend(_validate_ui_actions(declarations))
    diagnostics.extend(_validate_env_id_candidate_functions(declarations))
    diagnostics.extend(_validate_object_lifecycle_methods(declarations))
    diagnostics.extend(_validate_object_lifecycle_method_signatures(declarations))
    diagnostics.extend(_validate_parameters(declarations))
    diagnostics.extend(_validate_data_contracts(declarations))
    diagnostics.extend(_validate_dependency_cycles(declarations))
    return diagnostics


def _validate_object_lifecycle_methods(declarations: list[V2Declaration]) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    for declaration in declarations:
        if declaration.kind not in {"workflow", "component"} or declaration.target_kind != "class":
            continue
        for method_name in sorted(REMOVED_OBJECT_LIFECYCLE_METHODS.intersection(declaration.methods)):
            diagnostics.append(
                V2Diagnostic(
                    code="V2_OBJECT_LIFECYCLE_METHOD_UNSUPPORTED",
                    location=f"{declaration.symbol}.{method_name}",
                    message="object lifecycle only supports cleanup(ctx, outcome); aclose/close are not called",
                )
            )
    return diagnostics


def _validate_object_lifecycle_method_signatures(declarations: list[V2Declaration]) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    expected = {
        "setup": ("self", "ctx", "workflow"),
        "cleanup": ("self", "ctx", "outcome"),
    }
    for declaration in declarations:
        if declaration.kind not in {"workflow", "component"} or declaration.target_kind != "class":
            continue
        for signature in declaration.method_signatures:
            expected_args = expected.get(signature.name)
            if expected_args is None:
                continue
            if signature.has_varargs or len(signature.positional_args) != len(expected_args):
                diagnostics.append(
                    V2Diagnostic(
                        code="V2_OBJECT_LIFECYCLE_METHOD_SIGNATURE_INVALID",
                        location=f"{declaration.symbol}.{signature.name}",
                        message=(f"{signature.name} lifecycle method must accept ({', '.join(expected_args)})"),
                    )
                )
    return diagnostics


def _validate_required_workflow(declarations: list[V2Declaration]) -> list[V2Diagnostic]:
    if any(item.kind == "workflow" for item in declarations):
        return []
    return [
        V2Diagnostic(
            code="V2_WORKFLOW_MISSING",
            location="workflows/",
            message="core-native-v2 modules must declare at least one @workflow",
        )
    ]


def _validate_duplicate_names(declarations: list[V2Declaration]) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    by_key: dict[tuple[str, str], list[V2Declaration]] = defaultdict(list)
    for declaration in declarations:
        by_key[(declaration.kind, declaration.name)].append(declaration)

    for (kind, name), items in sorted(by_key.items()):
        if len(items) < 2:
            continue
        symbols = ", ".join(item.symbol for item in items)
        diagnostics.append(
            V2Diagnostic(
                code="V2_DUPLICATE_NAME",
                location=f"{kind}.{name}",
                message=f"duplicate {kind} name: {symbols}",
            )
        )
    return diagnostics


def _validate_interface_implementations(declarations: list[V2Declaration]) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    interfaces = {item.name for item in declarations if item.kind == "interface"}
    implemented = {item.meta.implements for item in declarations if item.kind == "component" and item.meta.implements}
    for interface_name in sorted(interfaces - implemented):
        diagnostics.append(
            V2Diagnostic(
                code="V2_INTERFACE_IMPLEMENTATION_MISSING",
                location=f"interface.{interface_name}",
                message=f"interface has no component implementation: {interface_name}",
            )
        )
    return diagnostics


def _validate_injection_targets(declarations: list[V2Declaration]) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    interfaces = {item.name for item in declarations if item.kind == "interface"}
    components = {item.name for item in declarations if item.kind == "component"}

    for declaration in declarations:
        if declaration.kind == "component" and declaration.meta.implements not in interfaces:
            diagnostics.append(
                V2Diagnostic(
                    code="V2_IMPLEMENT_TARGET_MISSING",
                    location=f"{declaration.symbol}.implements",
                    message=f"interface target is not declared: {declaration.meta.implements}",
                )
            )

        for inject in declaration.meta.inject:
            targets = interfaces if inject.type == "interface" else components
            if inject.target in targets:
                continue
            diagnostics.append(
                V2Diagnostic(
                    code="V2_INJECT_TARGET_MISSING",
                    location=f"{declaration.symbol}.inject[{inject.name}]",
                    message=f"{inject.type} target is not declared: {inject.target}",
                )
            )
    return diagnostics


def _validate_page_actions(declarations: list[V2Declaration]) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    for declaration in declarations:
        if declaration.kind != "page_action":
            continue
        if declaration.target_kind in {"function", "async_function"}:
            continue
        diagnostics.append(
            V2Diagnostic(
                code="V2_PAGE_ACTION_INVALID_TARGET",
                location=declaration.symbol,
                message="page action must decorate a function or async function",
            )
        )
    return diagnostics


def _validate_ui_actions(declarations: list[V2Declaration]) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    for declaration in declarations:
        if declaration.kind != "ui_action":
            continue
        if declaration.target_kind in {"function", "async_function"}:
            continue
        diagnostics.append(
            V2Diagnostic(
                code="V2_UI_ACTION_INVALID_TARGET",
                location=declaration.symbol,
                message="ui action must decorate a function or async function",
            )
        )
    return diagnostics


def _validate_env_id_candidate_functions(declarations: list[V2Declaration]) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    for declaration in declarations:
        if declaration.kind not in {"env_candidates", "env_cleanup_candidates"}:
            continue
        if declaration.target_kind == "function":
            continue
        label = "env cleanup candidates" if declaration.kind == "env_cleanup_candidates" else "env candidates"
        code = (
            "V2_ENV_CLEANUP_CANDIDATES_INVALID_TARGET"
            if declaration.kind == "env_cleanup_candidates"
            else "V2_ENV_CANDIDATES_INVALID_TARGET"
        )
        diagnostics.append(
            V2Diagnostic(
                code=code,
                location=declaration.symbol,
                message=f"{label} must decorate a pure sync function",
            )
        )
    return diagnostics


def _validate_pages(
    declarations: list[V2Declaration],
    module_functions: dict[str, dict[str, V2FunctionSignature]],
) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    ui_action_signatures = _collect_ui_action_function_signatures(declarations, module_functions)
    for declaration in declarations:
        if declaration.kind != "page":
            continue
        if declaration.target_kind not in {"function", "async_function"}:
            diagnostics.append(
                V2Diagnostic(
                    code="V2_PAGE_INVALID_TARGET",
                    location=declaration.symbol,
                    message="page must decorate a function or async function",
                )
            )
            continue

        raw_schema = dict(declaration.meta.page_schema)
        load_handler = str(raw_schema.get("load_handler") or "").strip()
        function_name = declaration.symbol.rsplit(".", 1)[-1]
        if load_handler and load_handler != function_name:
            diagnostics.append(
                V2Diagnostic(
                    code="V2_PAGE_LOAD_HANDLER_MISMATCH",
                    location=f"{declaration.symbol}.schema.load_handler",
                    message="@page load_handler must match the decorated function",
                )
            )
            continue
        raw_schema["load_handler"] = function_name
        query_handler_schema = raw_schema
        try:
            query_handler_schema = normalize_page_schema(declaration.name, raw_schema)
        except ValueError as exc:
            diagnostics.append(
                V2Diagnostic(
                    code="V2_PAGE_SCHEMA_INVALID",
                    location=f"{declaration.symbol}.schema",
                    message=str(exc),
                )
            )
        diagnostics.extend(_validate_page_query_handlers(declaration, query_handler_schema, module_functions))
        diagnostics.extend(_validate_page_crud_handlers(declaration, query_handler_schema, ui_action_signatures))
    return diagnostics


def _validate_page_query_handlers(
    declaration: V2Declaration,
    page_schema: dict[str, Any],
    module_functions: dict[str, dict[str, V2FunctionSignature]],
) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    handlers = module_functions.get(declaration.source_path, {})
    for table_schema, table_path in _iter_page_data_tables(page_schema.get("children"), "schema.children"):
        data_source = table_schema.get("data_source")
        if not isinstance(data_source, dict):
            continue
        if str(data_source.get("type") or "").strip().lower() != "query_handler":
            continue

        location = f"{declaration.symbol}.{table_path}.data_source.handler"
        handler_name = str(data_source.get("handler") or "").strip()
        if not handler_name:
            diagnostics.append(
                V2Diagnostic(
                    code="V2_PAGE_QUERY_HANDLER_MISSING",
                    location=location,
                    message="DataTable query_handler must declare data_source.handler",
                )
            )
            continue

        handler = handlers.get(handler_name)
        if handler is None:
            diagnostics.append(
                V2Diagnostic(
                    code="V2_PAGE_QUERY_HANDLER_MISSING",
                    location=location,
                    message=(
                        "DataTable query_handler must reference a sync function "
                        f"in the same page module: {handler_name}"
                    ),
                )
            )
            continue

        if handler.is_async:
            diagnostics.append(
                V2Diagnostic(
                    code="V2_PAGE_QUERY_HANDLER_ASYNC",
                    location=location,
                    message=f"DataTable query_handler must be a sync function: {handler_name}",
                )
            )
            continue

        if not _function_accepts_runtime_positional_call(handler, 2):
            diagnostics.append(
                V2Diagnostic(
                    code="V2_PAGE_QUERY_HANDLER_SIGNATURE_INVALID",
                    location=location,
                    message=f"DataTable query_handler signature must accept (context, query): {handler_name}",
                )
            )
    return diagnostics


def _collect_ui_action_function_signatures(
    declarations: list[V2Declaration],
    module_functions: dict[str, dict[str, V2FunctionSignature]],
) -> dict[str, V2FunctionSignature]:
    signatures: dict[str, V2FunctionSignature] = {}
    for declaration in declarations:
        if declaration.kind != "ui_action":
            continue
        function_name = declaration.symbol.rsplit(".", 1)[-1]
        signature = module_functions.get(declaration.source_path, {}).get(function_name)
        if signature is not None:
            signatures[declaration.name] = signature
    return signatures


def _validate_page_crud_handlers(
    declaration: V2Declaration,
    page_schema: dict[str, Any],
    ui_action_signatures: dict[str, V2FunctionSignature],
) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    for table_schema, table_path in _iter_page_data_tables(page_schema.get("children"), "schema.children"):
        crud = table_schema.get("crud")
        if not isinstance(crud, dict):
            continue
        primary_key = str(crud.get("primary_key") or "").strip()
        handler_specs = (
            ("create_handler", ("payload",), ("payload",)),
            ("update_handler", (primary_key, "payload"), (primary_key, "payload")),
            ("delete_handler", (primary_key,), (primary_key,)),
        )
        for handler_key, expected_params, type_checked_params in handler_specs:
            handler_name = str(crud.get(handler_key) or "").strip()
            if not handler_name:
                continue
            location = f"{declaration.symbol}.{table_path}.crud.{handler_key}"
            handler = ui_action_signatures.get(handler_name)
            if handler is None:
                diagnostics.append(
                    V2Diagnostic(
                        code="V2_PAGE_CRUD_HANDLER_MISSING",
                        location=location,
                        message=f"DataTable {handler_key} must reference a @ui_action function: {handler_name}",
                    )
                )
                continue
            if not _function_accepts_exact_crud_keyword_call(handler, expected_params):
                diagnostics.append(
                    V2Diagnostic(
                        code="V2_PAGE_CRUD_HANDLER_SIGNATURE_INVALID",
                        location=location,
                        message=(
                            f"DataTable {handler_key} signature must accept "
                            f"(context, {', '.join(expected_params)}): {handler_name}"
                        ),
                    )
                )
                continue
            diagnostics.extend(
                _crud_handler_type_diagnostics(
                    handler,
                    handler_key=handler_key,
                    parameter_names=type_checked_params,
                    location=location,
                )
            )
    return diagnostics


def _function_accepts_exact_crud_keyword_call(
    signature: V2FunctionSignature,
    expected_params_after_context: tuple[str, ...],
) -> bool:
    expected_count = 1 + len(expected_params_after_context)
    return (
        not signature.has_varargs
        and not signature.has_varkw
        and not signature.kwonly_args
        and signature.positional_default_count == 0
        and len(signature.positional_args) == expected_count
        and tuple(signature.positional_args[1:]) == expected_params_after_context
    )


def _crud_handler_type_diagnostics(
    signature: V2FunctionSignature,
    *,
    handler_key: str,
    parameter_names: tuple[str, ...],
    location: str,
) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    annotations = signature.parameter_annotations or {}
    for parameter_name in parameter_names:
        annotation = str(annotations.get(parameter_name) or "").strip()
        if parameter_name == "payload":
            if _is_loose_crud_payload_annotation(annotation):
                diagnostics.append(
                    V2Diagnostic(
                        code="V2_PAGE_CRUD_HANDLER_TYPE_INVALID",
                        location=f"{location}.{parameter_name}",
                        message=(
                            f"DataTable {handler_key} payload must use a concrete "
                            "TypedDict/dataclass-style payload type, not dict/Mapping/Any: "
                            f"{signature.name}.{parameter_name}"
                        ),
                    )
                )
            continue

        if _is_loose_crud_scalar_annotation(annotation):
            diagnostics.append(
                V2Diagnostic(
                    code="V2_PAGE_CRUD_HANDLER_TYPE_INVALID",
                    location=f"{location}.{parameter_name}",
                    message=(
                        f"DataTable {handler_key} {parameter_name} must declare a concrete scalar type: "
                        f"{signature.name}.{parameter_name}"
                    ),
                )
            )
    return diagnostics


def _is_loose_crud_payload_annotation(annotation: str) -> bool:
    root = _annotation_root(annotation)
    return not annotation or _annotation_mentions_any(annotation) or root in {"Any", "object", "dict", "Dict", "Mapping", "MutableMapping"}


def _is_loose_crud_scalar_annotation(annotation: str) -> bool:
    root = _annotation_root(annotation)
    return not annotation or _annotation_mentions_any(annotation) or root in {
        "Any",
        "object",
        "dict",
        "Dict",
        "Mapping",
        "MutableMapping",
        "list",
        "List",
        "Sequence",
        "MutableSequence",
        "tuple",
        "Tuple",
        "set",
        "Set",
    }


def _annotation_root(annotation: str) -> str:
    compact = annotation.replace("typing.", "").replace("collections.abc.", "").replace(" ", "")
    if not compact:
        return ""
    return compact.split("[", 1)[0].rsplit(".", 1)[-1]


def _annotation_mentions_any(annotation: str) -> bool:
    compact = annotation.replace("typing.", "").replace(" ", "")
    return any(part == "Any" for part in re.split(r"[^A-Za-z0-9_]+", compact))


def _iter_page_data_tables(children: Any, path: str) -> list[tuple[dict[str, Any], str]]:
    if not isinstance(children, list):
        return []

    tables: list[tuple[dict[str, Any], str]] = []
    for index, child in enumerate(children):
        child_path = f"{path}[{index}]"
        if not isinstance(child, dict):
            continue
        if str(child.get("type") or "") == "DataTable":
            tables.append((child, child_path))
        nested = child.get("children")
        if isinstance(nested, list):
            tables.extend(_iter_page_data_tables(nested, f"{child_path}.children"))
    return tables


def _function_accepts_runtime_positional_call(signature: V2FunctionSignature, positional_count: int) -> bool:
    required_count = len(signature.positional_args) - signature.positional_default_count
    if positional_count < required_count:
        return False
    if not signature.has_varargs and positional_count > len(signature.positional_args):
        return False
    return not signature.required_kwonly_args


def _validate_parameters(declarations: list[V2Declaration]) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    for declaration in declarations:
        if declaration.kind == "workflow" and declaration.meta.parameters:
            diagnostics.append(
                V2Diagnostic(
                    code="V2_WORKFLOW_PARAMETERS_UNSUPPORTED",
                    location=f"{declaration.symbol}.parameters",
                    message="workflow parameters are removed; declare component parameters instead",
                )
            )
        seen_names: set[str] = set()
        for parameter in declaration.meta.parameters:
            location = f"{declaration.symbol}.parameters[{parameter.name}]"
            if not _is_valid_name(parameter.name):
                diagnostics.append(
                    V2Diagnostic(
                        code="V2_INVALID_PARAMETER",
                        location=location,
                        message="parameter name must be snake_case",
                    )
                )
            elif parameter.name in seen_names:
                diagnostics.append(
                    V2Diagnostic(
                        code="V2_INVALID_PARAMETER",
                        location=location,
                        message="duplicate parameter name",
                    )
                )
            else:
                seen_names.add(parameter.name)

            if parameter.min is not None and not _is_number(parameter.min):
                diagnostics.append(
                    V2Diagnostic(
                        code="V2_INVALID_PARAMETER",
                        location=f"{location}.min",
                        message="min must be numeric",
                    )
                )
            if parameter.max is not None and not _is_number(parameter.max):
                diagnostics.append(
                    V2Diagnostic(
                        code="V2_INVALID_PARAMETER",
                        location=f"{location}.max",
                        message="max must be numeric",
                    )
                )
            if _is_number(parameter.min) and _is_number(parameter.max) and parameter.min > parameter.max:
                diagnostics.append(
                    V2Diagnostic(
                        code="V2_INVALID_PARAMETER",
                        location=location,
                        message="min must be less than or equal to max",
                    )
                )
            if parameter.step is not None and (not _is_number(parameter.step) or parameter.step <= 0):
                diagnostics.append(
                    V2Diagnostic(
                        code="V2_INVALID_PARAMETER",
                        location=f"{location}.step",
                        message="step must be a positive number",
                    )
                )

            if parameter.default is not None:
                diagnostics.extend(_validate_parameter_default(parameter, location))

            option_values: set[str] = set()
            for option in parameter.options:
                value_key = json.dumps(option.value, ensure_ascii=False, sort_keys=True)
                if value_key in option_values:
                    diagnostics.append(
                        V2Diagnostic(
                            code="V2_INVALID_PARAMETER",
                            location=f"{location}.options[{value_key}]",
                            message="duplicate enum option value",
                        )
                    )
                option_values.add(value_key)
    return diagnostics


def _validate_parameter_default(parameter: Any, location: str) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    try:
        _validate_default_value(parameter, parameter.default)
    except ValueError as exc:
        diagnostics.append(
            V2Diagnostic(
                code="V2_INVALID_PARAMETER_DEFAULT",
                location=f"{location}.default",
                message=str(exc),
            )
        )
        return diagnostics
    return diagnostics


def _validate_default_value(parameter: ParameterSpec, value: Any) -> None:
    parameter_type = parameter.type
    if parameter_type in {"string", "text", "secret"}:
        valid = isinstance(value, str)
    elif parameter_type == "integer":
        valid = isinstance(value, int) and not isinstance(value, bool)
    elif parameter_type == "number":
        valid = _is_number(value)
    elif parameter_type == "boolean":
        valid = isinstance(value, bool)
    elif parameter_type == "enum":
        valid = value in [option.value for option in parameter.options]
    elif parameter_type == "array":
        valid = isinstance(value, (list, tuple))
    elif parameter_type == "object":
        valid = isinstance(value, dict)
    elif parameter_type == "json":
        valid = _is_json_like(value)
    elif parameter_type == "date":
        valid = isinstance(value, dt.date) and not isinstance(value, dt.datetime) or _is_iso_date(value)
    elif parameter_type == "datetime":
        valid = isinstance(value, dt.datetime) or _is_iso_datetime(value)
    elif parameter_type == "time":
        valid = isinstance(value, dt.time) or _is_iso_time(value)
    elif parameter_type == "url":
        valid = isinstance(value, str) and _is_url(value)
    elif parameter_type == "path":
        valid = isinstance(value, (str, Path))
    else:
        valid = False
    if not valid:
        raise ValueError(f"default value does not match parameter type: {parameter_type}")

    if parameter_type in {"integer", "number"}:
        if parameter.min is not None and value < parameter.min:
            raise ValueError("default value is lower than min")
        if parameter.max is not None and value > parameter.max:
            raise ValueError("default value is greater than max")
    if parameter_type == "array" and parameter.item_schema:
        for item in value:
            _validate_default_value(_schema_parameter(parameter.item_schema), item)
    if parameter_type == "object":
        _validate_object_default(parameter, value)


def _validate_object_default(parameter: ParameterSpec, value: dict[Any, Any]) -> None:
    if not all(isinstance(key, str) for key in value):
        raise ValueError("default value does not match parameter type: object")
    fields = parameter.schema.get("fields")
    if isinstance(fields, list):
        for field in fields:
            if not isinstance(field, dict):
                continue
            field_name = str(field.get("name") or field.get("key") or "").strip()
            if not field_name:
                continue
            if field_name not in value:
                if bool(field.get("required")):
                    raise ValueError(f"default object field is required: {field_name}")
                continue
            _validate_default_value(_schema_parameter(field), value[field_name])
    additional_type = str(parameter.schema.get("additional_type") or "").strip()
    if additional_type:
        additional_parameter = ParameterSpec(name="value", type=additional_type)
        for item in value.values():
            _validate_default_value(additional_parameter, item)


def _schema_parameter(schema: dict[str, Any]) -> ParameterSpec:
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


def _is_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _is_iso_datetime(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _is_iso_time(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        dt.time.fromisoformat(value)
    except ValueError:
        return False
    return True


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


def _validate_data_contracts(declarations: list[V2Declaration]) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    data_tables = {item.name: item for item in declarations if item.kind == "data_table"}
    for declaration in declarations:
        if declaration.kind == "data_table":
            reserved_fields = _reserved_data_fields_for_table(declaration)
            diagnostics.extend(
                _reserved_schema_field_diagnostics(
                    declaration,
                    declaration.meta.schema,
                    "schema",
                    reserved_fields=reserved_fields,
                )
            )
            diagnostics.extend(_reserved_annotation_field_diagnostics(declaration, reserved_fields=reserved_fields))
            if declaration.meta.storage_mode == "managed_dataset":
                diagnostics.extend(_derived_managed_dataset_field_diagnostics(declaration))
            for index in declaration.meta.indexes:
                for field in index.fields:
                    if field in reserved_fields:
                        diagnostics.append(
                            V2Diagnostic(
                                code="V2_RESERVED_DATA_FIELD",
                                location=f"{declaration.symbol}.indexes[{field}]",
                                message=f"host-reserved data field is not allowed: {field}",
                            )
                        )
        elif declaration.kind == "data_view":
            for source_name in declaration.meta.sources:
                source_table = data_tables.get(source_name)
                if source_table is None:
                    diagnostics.append(
                        V2Diagnostic(
                            code="V2_VIEW_SOURCE_MISSING",
                            location=f"{declaration.symbol}.sources[{source_name}]",
                            message=f"data view source table is not declared: {source_name}",
                        )
                    )
                elif source_table.meta.storage_mode != "custom_table":
                    diagnostics.append(
                        V2Diagnostic(
                            code="V2_VIEW_SOURCE_NOT_RELATION",
                            location=f"{declaration.symbol}.sources[{source_name}]",
                            message=f"data view source must be custom_table: {source_name}",
                        )
                    )
            diagnostics.extend(
                _reserved_schema_field_diagnostics(
                    declaration,
                    declaration.meta.schema,
                    "schema",
                    reserved_fields=HOST_RESERVED_DATA_FIELDS,
                )
            )
    return diagnostics


def _reserved_data_fields_for_table(declaration: V2Declaration) -> frozenset[str]:
    if declaration.meta.storage_mode == "managed_dataset":
        return MANAGED_DATASET_RESERVED_DATA_FIELDS
    return HOST_RESERVED_DATA_FIELDS


def _derived_managed_dataset_field_diagnostics(declaration: V2Declaration) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    for item in declaration.meta.schema:
        field_name = _schema_field_name(item)
        if _looks_like_derived_data_field(field_name):
            diagnostics.append(
                V2Diagnostic(
                    code="V2_DERIVED_DATA_FIELD",
                    location=f"{declaration.symbol}.schema[{field_name}]",
                    message=(
                        "managed_dataset schema should declare persisted business fields only; "
                        f"move derived UI field out of @data_table.schema: {field_name}"
                    ),
                    severity="warning",
                )
            )
    for field_name in declaration.annotations:
        if _looks_like_derived_data_field(field_name):
            diagnostics.append(
                V2Diagnostic(
                    code="V2_DERIVED_DATA_FIELD",
                    location=f"{declaration.symbol}.annotations[{field_name}]",
                    message=(
                        "managed_dataset schema should declare persisted business fields only; "
                        f"move derived UI field out of data annotations: {field_name}"
                    ),
                    severity="warning",
                )
            )
    return diagnostics


def _looks_like_derived_data_field(field_name: str) -> bool:
    return bool(field_name) and field_name.endswith(MANAGED_DATASET_DERIVED_FIELD_SUFFIXES)


def _reserved_annotation_field_diagnostics(
    declaration: V2Declaration,
    *,
    reserved_fields: frozenset[str],
) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    for field_name in declaration.annotations:
        if not field_name or field_name not in reserved_fields:
            continue
        diagnostics.append(
            V2Diagnostic(
                code="V2_RESERVED_DATA_FIELD",
                location=f"{declaration.symbol}.annotations[{field_name}]",
                message=f"host-reserved data field is not allowed: {field_name}",
            )
        )
    return diagnostics


def _reserved_schema_field_diagnostics(
    declaration: V2Declaration,
    schema: tuple[dict[str, Any], ...],
    field_group: str,
    *,
    reserved_fields: frozenset[str],
) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    for item in schema:
        field_name = _schema_field_name(item)
        if not field_name or field_name not in reserved_fields:
            continue
        diagnostics.append(
            V2Diagnostic(
                code="V2_RESERVED_DATA_FIELD",
                location=f"{declaration.symbol}.{field_group}[{field_name}]",
                message=f"host-reserved data field is not allowed: {field_name}",
            )
        )
    return diagnostics


def _schema_field_name(item: dict[str, Any]) -> str:
    name = str(item.get("name", "") or "").strip()
    if name:
        return name
    return str(item.get("key", "") or "").strip()


def _validate_dependency_cycles(declarations: list[V2Declaration]) -> list[V2Diagnostic]:
    component_graph: dict[str, list[str]] = defaultdict(list)
    components = {item.name for item in declarations if item.kind == "component"}
    implementations: dict[str, list[str]] = defaultdict(list)
    for declaration in declarations:
        if declaration.kind == "component" and declaration.meta.implements:
            implementations[declaration.meta.implements].append(declaration.name)

    for declaration in declarations:
        if declaration.kind != "component":
            continue
        for inject in declaration.meta.inject:
            if inject.type == "object" and inject.target in components:
                component_graph[declaration.name].append(inject.target)
            elif inject.type == "interface":
                component_graph[declaration.name].extend(implementations.get(inject.target, ()))

    cycles = _find_cycles(component_graph)
    return [
        V2Diagnostic(
            code="V2_DEPENDENCY_CYCLE",
            location="object_graph",
            message="object injection cycle detected: " + " -> ".join(cycle),
        )
        for cycle in cycles
    ]


def _find_cycles(graph: dict[str, list[str]]) -> list[tuple[str, ...]]:
    cycles: set[tuple[str, ...]] = set()
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> None:
        if node in visiting:
            cycle_start = stack.index(node)
            cycle = stack[cycle_start:] + [node]
            cycles.add(_canonical_cycle(cycle))
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for target in sorted(graph.get(node, [])):
            visit(target)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return sorted(cycles)


def _canonical_cycle(cycle: list[str]) -> tuple[str, ...]:
    if len(cycle) <= 1:
        return tuple(cycle)
    nodes = cycle[:-1]
    rotations = [nodes[index:] + nodes[:index] for index in range(len(nodes))]
    canonical = min(rotations)
    return tuple([*canonical, canonical[0]])


def _is_valid_name(name: str) -> bool:
    return bool(NAME_RE.match(str(name or "").strip()))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)

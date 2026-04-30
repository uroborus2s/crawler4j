"""Reusable core-native-v2 decorator scanner and diagnostics."""

from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from crawler4j_contracts import (
    HOST_RESERVED_DATA_FIELDS,
    Crawler4jMeta,
    InjectSpec,
    ParameterSpec,
)

CORE_NATIVE_V2_RUNTIME_API = "core-native-v2"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
V2_SCAN_DIRECTORIES = ("interfaces", "objects", "workflows", "tasks", "data")
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
LEGACY_SPEC_NAMES = {"TaskSpec", "WorkflowSpec", "EnvSelectorSpec"}
LEGACY_DECLARATION_NAMES = {"TASK", "WORKFLOW", "SELECTOR"}
DECORATOR_KINDS = {
    "interface": "interface",
    "component": "component",
    "workflow": "workflow",
    "page_action": "page_action",
    "data_table": "data_table",
    "data_query": "data_query",
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
    target: Any = None


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
    collected_declarations, declaration_diagnostics = _collect_declarations(module_name, parsed_modules)
    declarations.extend(collected_declarations)
    diagnostics.extend(declaration_diagnostics)
    diagnostics.extend(_validate_declarations(declarations))

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
            elif isinstance(node, ast.ImportFrom):
                module = str(node.module or "")
                sdk_import = module == "crawler4j_sdk" or module.startswith("crawler4j_sdk.")
                if module == "crawler4j_contracts.specs":
                    legacy_specs.update(alias.name for alias in node.names if alias.name in LEGACY_SPEC_NAMES)
                elif module == "crawler4j_contracts":
                    legacy_specs.update(alias.name for alias in node.names if alias.name in LEGACY_SPEC_NAMES)
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
                )
            )
    return declarations, diagnostics


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
        source=meta.source,
        sql=meta.sql,
        output_schema=meta.output_schema,
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
    default_marker = kwargs.get("default", _MISSING)
    default_supplied = default_marker is not _MISSING or fallback_default is not _MISSING
    default = default_marker if default_marker is not _MISSING else fallback_default
    if default is _MISSING:
        default = None
    required_value = kwargs.get("required", _MISSING)
    required = bool(required_value) if required_value is not _MISSING else not default_supplied
    return ParameterSpec(
        name=str(kwargs.get("name") or fallback_name),
        type=str(kwargs.get("type") or _infer_parameter_type(type_expr) or "string"),
        label=str(kwargs.get("label") or ""),
        description=str(kwargs.get("description") or ""),
        required=required,
        default=default,
        options=tuple(_as_tuple(kwargs.get("options"))),
        min=kwargs.get("min"),
        max=kwargs.get("max"),
        step=kwargs.get("step"),
        placeholder=str(kwargs.get("placeholder") or ""),
    )


def _infer_parameter_type(node: ast.expr | None) -> str:
    if node is None:
        return ""
    type_name = _annotation_name(node)
    return {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
    }.get(type_name, "")


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


def _validate_declarations(declarations: list[V2Declaration]) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    diagnostics.extend(_validate_required_workflow(declarations))
    diagnostics.extend(_validate_duplicate_names(declarations))
    diagnostics.extend(_validate_interface_implementations(declarations))
    diagnostics.extend(_validate_injection_targets(declarations))
    diagnostics.extend(_validate_page_actions(declarations))
    diagnostics.extend(_validate_parameters(declarations))
    diagnostics.extend(_validate_data_contracts(declarations))
    diagnostics.extend(_validate_dependency_cycles(declarations))
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
    value = parameter.default
    parameter_type = parameter.type
    if parameter_type in {"string", "text"}:
        valid = isinstance(value, str)
    elif parameter_type == "integer":
        valid = isinstance(value, int) and not isinstance(value, bool)
    elif parameter_type == "number":
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif parameter_type == "boolean":
        valid = isinstance(value, bool)
    elif parameter_type == "enum":
        valid = value in [option.value for option in parameter.options]
    else:
        valid = False
    if not valid:
        diagnostics.append(
            V2Diagnostic(
                code="V2_INVALID_PARAMETER_DEFAULT",
                location=f"{location}.default",
                message=f"default value does not match parameter type: {parameter_type}",
            )
        )
        return diagnostics
    if parameter_type in {"integer", "number"}:
        if parameter.min is not None and value < parameter.min:
            diagnostics.append(
                V2Diagnostic(
                    code="V2_INVALID_PARAMETER_DEFAULT",
                    location=f"{location}.default",
                    message="default value is lower than min",
                )
            )
        if parameter.max is not None and value > parameter.max:
            diagnostics.append(
                V2Diagnostic(
                    code="V2_INVALID_PARAMETER_DEFAULT",
                    location=f"{location}.default",
                    message="default value is greater than max",
                )
            )
    return diagnostics


def _validate_data_contracts(declarations: list[V2Declaration]) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    data_tables = {item.name for item in declarations if item.kind == "data_table"}
    for declaration in declarations:
        if declaration.kind == "data_table":
            diagnostics.extend(_reserved_schema_field_diagnostics(declaration, declaration.meta.schema, "schema"))
            diagnostics.extend(_reserved_annotation_field_diagnostics(declaration))
            for index in declaration.meta.indexes:
                for field in index.fields:
                    if field in HOST_RESERVED_DATA_FIELDS:
                        diagnostics.append(
                            V2Diagnostic(
                                code="V2_RESERVED_DATA_FIELD",
                                location=f"{declaration.symbol}.indexes[{field}]",
                                message=f"host-reserved data field is not allowed: {field}",
                            )
                        )
        elif declaration.kind == "data_query":
            if declaration.meta.source and declaration.meta.source not in data_tables:
                diagnostics.append(
                    V2Diagnostic(
                        code="V2_QUERY_SOURCE_MISSING",
                        location=f"{declaration.symbol}.source",
                        message=f"data query source table is not declared: {declaration.meta.source}",
                    )
                )
            diagnostics.extend(
                _reserved_schema_field_diagnostics(declaration, declaration.meta.output_schema, "output_schema")
            )
    return diagnostics


def _reserved_annotation_field_diagnostics(declaration: V2Declaration) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    for field_name in declaration.annotations:
        if not field_name or field_name not in HOST_RESERVED_DATA_FIELDS:
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
) -> list[V2Diagnostic]:
    diagnostics: list[V2Diagnostic] = []
    for item in schema:
        field_name = _schema_field_name(item)
        if not field_name or field_name not in HOST_RESERVED_DATA_FIELDS:
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

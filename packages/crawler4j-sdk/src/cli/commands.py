"""CLI commands for crawler4j SDK module projects."""

from __future__ import annotations

import argparse
import ast
import asyncio
import importlib
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import yaml
from crawler4j_contracts import TaskContext, ToolSpec

from crawler4j_sdk._version import get_compatible_dependency_spec
from crawler4j_sdk.cli.templates import (
    DATA_TABLE_HELPER_TEMPLATE,
    ENV_SELECTOR_TEMPLATE,
    MODEL_GITIGNORE_TEMPLATE,
    MODEL_MANIFEST_TEMPLATE,
    MODEL_MODULE_INIT,
    MODEL_PROJECT_PYPROJECT,
    MODEL_PROJECT_README,
    MODEL_RUNTIME_TEMPLATE,
    MODEL_TEST_TASK_TEMPLATE,
    PAGE_HELPER_TEMPLATE,
    SCRIPT_TEMPLATE,
    WORKFLOW_TEMPLATE,
)
from crawler4j_sdk.hosted_ui import normalize_page_schema, normalize_table_schema


DEFAULT_PYTHON_VERSION = "3.12"
DEFAULT_MODULE_VERSION = "0.1.0"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
SEMVER_RE = re.compile(
    r"^v?"
    r"(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
CORE_PAGE_ENTRY_RE = re.compile(r"^core:page:(?P<id>[a-z][a-z0-9_]*)$")
CORE_DATA_TABLE_ENTRY_RE = re.compile(r"^core:data_table:(?P<id>[a-z][a-z0-9_]*)$")
GITHUB_TOKEN_ENV_VARS = ("CRAWLER4J_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")
LEGACY_UI_EXTENSION_KEYS = ("type", "entry", "detail_menu", "trusted")
LOCK_KEY_BUSINESS_OCCUPANCY_COLUMN_KEYS = {
    "occupied",
    "occupied_label",
    "is_occupied",
    "lock_status",
    "lock_status_label",
}
LOCK_KEY_BUSINESS_OCCUPANCY_COLUMN_LABELS = {"占用中", "占用状态"}


class CLIError(RuntimeError):
    """Raised when a CLI action cannot be completed safely."""


def to_class_name(name: str) -> str:
    """Convert a snake_case identifier to PascalCase."""
    return "".join(part.capitalize() for part in name.replace("-", "_").split("_"))


def to_display_name(name: str) -> str:
    """Convert an identifier to a readable title."""
    return name.replace("_", " ").replace("-", " ").title()


def is_valid_name(name: str) -> bool:
    """Validate importable module-style identifiers."""
    return bool(NAME_RE.match(str(name or "").strip()))


def is_valid_semver(version: str) -> bool:
    """Validate semantic version strings accepted by module manifests."""
    try:
        _parse_semver(version)
    except CLIError:
        return False
    return True


def is_valid_repo(repo: str) -> bool:
    """Validate GitHub owner/repo notation."""
    return bool(REPO_RE.match(str(repo or "").strip()))


def _insert_declare_ui_call(runtime_text: str, call_line: str) -> str:
    lines = runtime_text.splitlines(keepends=True)
    tree = ast.parse(runtime_text)
    declare_ui = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "declare_ui"
        ),
        None,
    )
    if declare_ui is None:
        raise CLIError("module_runtime.py 缺少 declare_ui，无法自动注册 hosted UI helper")

    function_start = declare_ui.lineno - 1
    function_end = declare_ui.end_lineno or declare_ui.lineno
    body_lines = lines[function_start:function_end]
    if any(line.rstrip("\n") == call_line for line in body_lines):
        return runtime_text

    sentinel = "    # SDK-DATA-TABLES"
    for offset, line in enumerate(body_lines):
        if line.rstrip("\n") == sentinel:
            lines.insert(function_start + offset, f"{call_line}\n")
            return "".join(lines)

    insert_at = function_end
    if declare_ui.body:
        last_stmt = declare_ui.body[-1]
        if isinstance(last_stmt, (ast.Return, ast.Pass)):
            insert_at = last_stmt.lineno - 1
    lines.insert(insert_at, f"{call_line}\n")
    return "".join(lines)


def _upsert_function_block(runtime_text: str, function_names: list[str], block: str) -> str:
    lines = runtime_text.splitlines(keepends=True)
    tree = ast.parse(runtime_text)
    names = set(function_names)
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    if not functions:
        return f"{runtime_text}{block}"

    start = min(node.lineno for node in functions) - 1
    end = max((node.end_lineno or node.lineno) for node in functions)
    lines[start:end] = [block]
    return "".join(lines)


def _resolve_github_token(explicit_token: str | None = None) -> str | None:
    token = str(explicit_token or "").strip()
    if token:
        return token
    for env_name in GITHUB_TOKEN_ENV_VARS:
        value = str(os.getenv(env_name, "") or "").strip()
        if value:
            return value
    return None


def _github_headers(*, accept: str, github_token: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": accept,
        "User-Agent": "crawler4j-sdk-cli",
    }
    token = _resolve_github_token(github_token)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _read_http_error_message(exc: urllib.error.HTTPError) -> str:
    try:
        payload = exc.read().decode("utf-8").strip()
    except Exception:
        payload = ""
    if payload:
        try:
            body = json.loads(payload)
        except Exception:
            return payload
        if isinstance(body, dict):
            message = str(body.get("message", "") or "").strip()
            if message:
                return message
        return payload
    return str(exc.reason or exc)


def _print_error(message: str) -> None:
    print(f"❌ {message}")


def _print_success(message: str) -> None:
    print(f"✅ {message}")


def _write_text(path: Path, content: str, *, force: bool = False) -> None:
    if path.exists() and not force:
        raise CLIError(f"文件已存在，拒绝覆盖: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _ensure_package_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    init_file = path / "__init__.py"
    if not init_file.exists():
        init_file.write_text("", encoding="utf-8")


def _ensure_package_export(init_file: Path, module_name: str, symbol_name: str) -> None:
    export_line = f"from .{module_name} import {symbol_name}\n"
    content = init_file.read_text(encoding="utf-8") if init_file.exists() else ""
    if export_line in content:
        return
    if content and not content.endswith("\n"):
        content += "\n"
    content += export_line
    init_file.write_text(content, encoding="utf-8")


def find_module_root(start: Path | None = None) -> Path | None:
    """Locate the nearest parent directory containing module.yaml."""
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "module.yaml").is_file():
            return candidate
    return None


def require_module_root(start: Path | None = None) -> Path:
    """Require the current working directory to be inside a module project."""
    module_root = find_module_root(start)
    if module_root:
        return module_root
    raise CLIError("当前目录不在模块项目中，找不到 module.yaml")


def load_manifest(module_root: Path) -> dict[str, Any]:
    """Load module.yaml as a mutable dictionary."""
    manifest_path = module_root / "module.yaml"
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise CLIError("module.yaml 顶层必须是 YAML 映射对象")
    return data


def save_manifest(module_root: Path, manifest: dict[str, Any]) -> None:
    """Persist a manifest dictionary back to module.yaml."""
    manifest_path = module_root / "module.yaml"
    manifest_path.write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _load_project_version(pyproject_path: Path) -> str:
    try:
        with pyproject_path.open("rb") as fh:
            payload = tomllib.load(fh)
    except FileNotFoundError as exc:
        raise CLIError(f"缺少文件: {pyproject_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise CLIError(f"pyproject.toml 解析失败: {pyproject_path}") from exc

    project = payload.get("project")
    if not isinstance(project, dict):
        raise CLIError("pyproject.toml 缺少 [project] 配置")

    version = str(project.get("version", "") or "").strip()
    if not version:
        raise CLIError("pyproject.toml [project].version 不能为空")
    return version


def _set_project_version(pyproject_path: Path, version: str) -> None:
    text = pyproject_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    in_project = False
    replaced = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if in_project and stripped.startswith("version"):
            indent = line[: len(line) - len(line.lstrip())]
            lines[index] = f'{indent}version = "{version}"'
            replaced = True
            break

    if not replaced:
        raise CLIError("pyproject.toml [project] 缺少 version 声明")

    rendered = "\n".join(lines)
    if text.endswith("\n"):
        rendered += "\n"
    pyproject_path.write_text(rendered, encoding="utf-8")


def _list_python_modules(package_dir: Path) -> list[str]:
    if not package_dir.exists():
        return []
    return sorted(
        path.stem
        for path in package_dir.glob("*.py")
        if path.name != "__init__.py" and not path.name.startswith("_")
    )


def _read_default_workflow(runtime_path: Path) -> str:
    if not runtime_path.exists():
        return ""
    match = re.search(
        r'(?m)^\s*DEFAULT_WORKFLOW\s*=\s*["\'](?P<name>[a-z][a-z0-9_]*)["\']\s*$',
        runtime_path.read_text(encoding="utf-8"),
    )
    return match.group("name") if match else ""


def _set_default_workflow(runtime_path: Path, workflow_name: str) -> None:
    text = runtime_path.read_text(encoding="utf-8")
    replacement = f'DEFAULT_WORKFLOW = "{workflow_name}"'
    pattern = re.compile(
        r'(?m)^(?:#\s*)?DEFAULT_WORKFLOW\s*=\s*["\'][A-Za-z0-9_]+["\']\s*$'
    )
    if pattern.search(text):
        text = pattern.sub(replacement, text, count=1)
    else:
        text += f"\n\n{replacement}\n"
    runtime_path.write_text(text, encoding="utf-8")


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise CLIError(f"YAML 文件必须是映射对象: {path}")
    return payload


def _normalize_ui_pages(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    ui_extension = manifest.setdefault("ui_extension", {})
    if not isinstance(ui_extension, dict):
        raise CLIError("module.yaml.ui_extension 必须是映射对象")
    pages = ui_extension.setdefault("pages", [])
    if not isinstance(pages, list):
        raise CLIError("module.yaml.ui_extension.pages 必须是数组")
    return pages


def _classify_ui_entry(page_id: str, entry: str) -> str | None:
    page_match = CORE_PAGE_ENTRY_RE.match(entry)
    if page_match and page_match.group("id") == page_id:
        return "page"
    table_match = CORE_DATA_TABLE_ENTRY_RE.match(entry)
    if table_match and table_match.group("id") == page_id:
        return "data_table"
    return None


def _manifest_ui_extension(manifest: dict[str, Any]) -> dict[str, Any] | None:
    ui_extension = manifest.get("ui_extension")
    if ui_extension is None:
        return None
    if not isinstance(ui_extension, dict):
        raise CLIError("module.yaml.ui_extension 必须是映射对象")
    return ui_extension


def _manifest_ui_pages(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    ui_extension = _manifest_ui_extension(manifest)
    if ui_extension is None:
        return []
    pages = ui_extension.get("pages")
    if pages is None:
        return []
    if not isinstance(pages, list):
        raise CLIError("module.yaml.ui_extension.pages 必须是数组")
    return [item for item in pages if isinstance(item, dict)]


def _manifest_ui_entries_by_kind(manifest: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for item in _manifest_ui_pages(manifest):
        page_id = str(item.get("id", "") or "").strip()
        entry = str(item.get("entry", "") or "").strip()
        if _classify_ui_entry(page_id, entry) == kind:
            entries.append(item)
    return entries


def _normalize_config_defaults(manifest: dict[str, Any]) -> dict[str, Any]:
    config_defaults = manifest.setdefault("config_defaults", {})
    if config_defaults is None:
        config_defaults = {}
        manifest["config_defaults"] = config_defaults
    if not isinstance(config_defaults, dict):
        raise CLIError("config_defaults 必须是 YAML 映射对象")
    module_defaults = config_defaults.setdefault("module", {})
    workflow_defaults = config_defaults.setdefault("workflows", {})
    if not isinstance(module_defaults, dict):
        raise CLIError("config_defaults.module 必须是 YAML 映射对象")
    if not isinstance(workflow_defaults, dict):
        raise CLIError("config_defaults.workflows 必须是 YAML 映射对象")
    return config_defaults


def _manifest_workflows(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    workflows = manifest.setdefault("workflows", [])
    if not isinstance(workflows, list):
        raise CLIError("module.yaml.workflows 必须是数组")
    return workflows


def _manifest_workflow_names(manifest: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in _manifest_workflows(manifest):
        if isinstance(item, dict):
            name = str(item.get("name", "")).strip()
            if name:
                names.append(name)
    return names


def _safe_run(cmd: list[str], *, cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True)


def _run_async(awaitable):
    return asyncio.run(awaitable)


def _import_module_root(module_root: Path) -> Any:
    package_name = module_root.name
    parent = str(module_root.parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)

    stale = [
        name
        for name in list(sys.modules)
        if name == package_name or name.startswith(f"{package_name}.")
    ]
    for name in stale:
        sys.modules.pop(name, None)

    return importlib.import_module(package_name)


def _render_yaml(data: Any) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False).strip() or "{}"


def _parse_semver(version: str) -> tuple[int, int, int, tuple[str, ...]]:
    match = SEMVER_RE.match(str(version or "").strip())
    if not match:
        raise CLIError(f"无效的版本号: {version}")

    prerelease = tuple((match.group("prerelease") or "").split(".")) if match.group("prerelease") else ()
    for identifier in prerelease:
        if identifier.isdigit() and len(identifier) > 1 and identifier.startswith("0"):
            raise CLIError(f"无效的版本号: {version}")

    return (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
        prerelease,
    )


def _compare_versions(left: str, right: str) -> int:
    left_major, left_minor, left_patch, left_prerelease = _parse_semver(left)
    right_major, right_minor, right_patch, right_prerelease = _parse_semver(right)

    left_base = (left_major, left_minor, left_patch)
    right_base = (right_major, right_minor, right_patch)
    if left_base < right_base:
        return -1
    if left_base > right_base:
        return 1

    if not left_prerelease and not right_prerelease:
        return 0
    if not left_prerelease:
        return 1
    if not right_prerelease:
        return -1

    for left_identifier, right_identifier in zip(left_prerelease, right_prerelease):
        if left_identifier == right_identifier:
            continue

        left_numeric = left_identifier.isdigit()
        right_numeric = right_identifier.isdigit()
        if left_numeric and right_numeric:
            left_number = int(left_identifier)
            right_number = int(right_identifier)
            if left_number < right_number:
                return -1
            if left_number > right_number:
                return 1
            continue
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        if left_identifier < right_identifier:
            return -1
        return 1

    if len(left_prerelease) < len(right_prerelease):
        return -1
    if len(left_prerelease) > len(right_prerelease):
        return 1
    return 0


def _load_host_runtime() -> dict[str, Any]:
    try:
        from src.core.persistence import init_database
        from src.core.mms import get_module_registry, get_module_release_service
        from src.core.debug import ensure_vscode_attach_config
    except ImportError as exc:  # pragma: no cover - depends on runtime environment
        raise CLIError(
            "当前环境缺少 crawler4j 宿主运行时；host 命令只能在安装了 crawler4j 客户端的环境里使用"
        ) from exc

    runtime: dict[str, Any] = {
        "init_database": init_database,
        "get_module_registry": get_module_registry,
        "get_module_release_service": get_module_release_service,
        "ensure_vscode_attach_config": ensure_vscode_attach_config,
    }
    return runtime


def _init_host_runtime(runtime: dict[str, Any]) -> None:
    runtime["init_database"]()


def _detect_install_source(source: str) -> tuple[str, str | Path]:
    source_path = Path(source).expanduser()
    if source_path.exists():
        resolved = source_path.resolve()
        if resolved.is_dir():
            return "dir", resolved
        if resolved.suffix.lower() == ".zip":
            return "zip", resolved
        return "file", resolved
    return "repo", source


def _print_preview(
    *,
    source_label: str,
    manifest: Any,
    warnings: list[str] | None = None,
    archive_path: Path | None = None,
    release: Any | None = None,
) -> None:
    print(f"安装来源: {source_label}")
    print(f"模块名: {getattr(manifest, 'name', '')}")
    print(f"版本: {getattr(manifest, 'version', '')}")
    print(f"仓库: {getattr(getattr(manifest, 'upgrade_source', None), 'repo', '')}")
    if archive_path:
        print(f"安装包: {archive_path}")
    if release:
        print(f"Release 版本: {getattr(release, 'version', '')}")
        print(f"Release 页面: {getattr(release, 'html_url', '')}")
    if warnings:
        print("警告:")
        for item in warnings:
            print(f"  - {item}")


def _print_module_info(module: Any) -> None:
    manifest = getattr(module, "manifest", None)
    print(f"模块名: {getattr(module, 'name', '')}")
    print(f"版本: {getattr(manifest, 'version', '') if manifest else ''}")
    print(f"来源: {getattr(getattr(module, 'source', None), 'value', getattr(module, 'source', ''))}")
    print(f"路径: {getattr(module, 'path', '')}")


def _validate_ui_extension(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    ui_extension = manifest.get("ui_extension")
    if ui_extension is None:
        return errors
    if not isinstance(ui_extension, dict):
        return ["ui_extension 必须是 YAML 映射对象"]

    legacy_keys = [key for key in LEGACY_UI_EXTENSION_KEYS if key in ui_extension]
    if legacy_keys:
        errors.append(
            "ui_extension 不再支持旧字段: " + ", ".join(legacy_keys)
        )

    pages = ui_extension.get("pages")
    if pages is None:
        return errors
    if not isinstance(pages, list):
        errors.append("ui_extension.pages 必须是数组")
        return errors

    seen_ids: set[str] = set()
    for item in pages:
        if not isinstance(item, dict):
            errors.append("ui_extension.pages 里的每一项都必须是对象")
            continue

        page_id = str(item.get("id", "") or "").strip()
        if not is_valid_name(page_id):
            errors.append(f"无效的 ui_extension.pages[].id: {page_id or '<empty>'}")
            continue
        if page_id in seen_ids:
            errors.append(f"ui_extension.pages[].id 重复: {page_id}")
        seen_ids.add(page_id)

        label = str(item.get("label", "") or "").strip()
        if not label:
            errors.append(f"ui_extension.pages[{page_id}].label 不能为空")

        entry = str(item.get("entry", "") or "").strip()
        if _classify_ui_entry(page_id, entry) is None:
            errors.append(f"ui_extension.pages[{page_id}].entry 不受支持: {entry or '<empty>'}")
    return errors


def collect_structure_errors(module_root: Path, manifest: dict[str, Any]) -> list[str]:
    """Collect structure-level validation errors."""
    errors: list[str] = []

    required_files = ["module.yaml", "__init__.py", "module_runtime.py", "pyproject.toml"]
    required_dirs = ["tasks", "workflows"]
    for name in required_files:
        if not (module_root / name).exists():
            errors.append(f"缺少关键文件: {name}")
    for name in required_dirs:
        if not (module_root / name).is_dir():
            errors.append(f"缺少关键目录: {name}/")

    if not str(manifest.get("name", "")).strip():
        errors.append("module.yaml 缺少 name")
    if "sdk_version_range" in manifest:
        errors.append("module.yaml 不再允许声明 sdk_version_range")

    for legacy_file in ["config_schema.json", "strategy.yaml"]:
        if (module_root / legacy_file).exists():
            errors.append(f"残留旧配置文件: {legacy_file}")
    if (module_root / "ui").exists():
        errors.append("残留旧 UI 目录: ui/")

    workflow_names = _manifest_workflow_names(manifest)
    if not workflow_names:
        errors.append("module.yaml.workflows 不能为空")
    else:
        for workflow_name in workflow_names:
            if not is_valid_name(workflow_name):
                errors.append(f"无效的 workflow 名称: {workflow_name}")
                continue
            if not (module_root / "workflows" / f"{workflow_name}.py").exists():
                errors.append(f"module.yaml 声明的 workflow 缺少源码文件: workflows/{workflow_name}.py")

    declared = set(workflow_names)
    files = set(_list_python_modules(module_root / "workflows"))
    for extra in sorted(files - declared):
        errors.append(f"workflows/{extra}.py 未写入 module.yaml.workflows")

    errors.extend(_validate_ui_extension(manifest))
    return errors


def collect_release_errors(module_root: Path, manifest: dict[str, Any]) -> list[str]:
    """Collect release-readiness validation errors."""
    errors = collect_structure_errors(module_root, manifest)

    version = str(manifest.get("version", "") or "").strip()
    if not is_valid_semver(version):
        errors.append(f"module.yaml.version 不是合法版本号: {version or '<empty>'}")

    upgrade_source = manifest.get("upgrade_source")
    if not isinstance(upgrade_source, dict):
        errors.append("module.yaml.upgrade_source 必须是 YAML 映射对象")
    else:
        source_type = str(upgrade_source.get("type", "") or "").strip()
        repo = str(upgrade_source.get("repo", "") or "").strip()
        if source_type != "github_release":
            errors.append("upgrade_source.type 目前必须是 github_release")
        if not is_valid_repo(repo):
            errors.append("upgrade_source.repo 必须是 owner/repo 形式")

    try:
        config_defaults = _normalize_config_defaults(dict(manifest))
        declared_workflows = set(_manifest_workflow_names(manifest))
        for workflow_name in config_defaults["workflows"]:
            if workflow_name not in declared_workflows:
                errors.append(f"config_defaults.workflows 包含未声明的 workflow: {workflow_name}")
    except CLIError as exc:
        errors.append(str(exc))

    try:
        project_version = _load_project_version(module_root / "pyproject.toml")
    except CLIError as exc:
        errors.append(str(exc))
    else:
        if project_version != version:
            errors.append(
                "pyproject.toml [project].version 必须与 module.yaml.version 一致: "
                f"{project_version} != {version}"
            )

    if str(manifest.get("name", "")).strip() != module_root.name:
        errors.append("module.yaml.name 必须与模块根目录名一致")
    return errors


def collect_full_errors(module_root: Path, manifest: dict[str, Any]) -> list[str]:
    """Collect importability and runtime-level validation errors."""
    errors = collect_release_errors(module_root, manifest)
    if errors:
        return errors

    try:
        module = _import_module_root(module_root)
    except Exception as exc:  # pragma: no cover - exercised by tests via failure paths
        return [f"模块无法导入: {exc.__class__.__name__}: {exc}"]

    assembler = getattr(module, "assembler", None)
    if not assembler:
        errors.append("模块根入口缺少 assembler")
        return errors

    discovery_errors = getattr(assembler, "discovery_errors", {}) or {}
    for message in discovery_errors.values():
        errors.append(str(message))

    for task_name in _list_python_modules(module_root / "tasks"):
        try:
            importlib.import_module(f"{module_root.name}.tasks.{task_name}")
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(f"tasks/{task_name}.py 无法导入: {exc.__class__.__name__}: {exc}")

    workflow_names = _manifest_workflow_names(manifest)
    for workflow_name in workflow_names:
        try:
            importlib.import_module(f"{module_root.name}.workflows.{workflow_name}")
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(
                f"workflows/{workflow_name}.py 无法导入: {exc.__class__.__name__}: {exc}"
            )

    try:
        module_runtime = importlib.import_module(f"{module_root.name}.module_runtime")
    except Exception as exc:  # pragma: no cover - failure path
        errors.append(f"module_runtime.py 无法导入: {exc.__class__.__name__}: {exc}")
    else:
        errors.extend(_validate_declared_ui(module_root, module_runtime, manifest))

    assembler_workflows = set(getattr(assembler, "workflows", {}).keys())
    for workflow_name in workflow_names:
        if workflow_name not in assembler_workflows:
            errors.append(f"工作流未被 assembler 发现: {workflow_name}")

    return errors


def _collect_lock_key_conflicts(schema: dict[str, Any]) -> list[str]:
    raw_columns = schema.get("columns", [])
    if not isinstance(raw_columns, list):
        return []

    conflicts: list[str] = []
    for item in raw_columns:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip()
        label = str(item.get("label", "")).strip()
        if key in LOCK_KEY_BUSINESS_OCCUPANCY_COLUMN_KEYS or label in LOCK_KEY_BUSINESS_OCCUPANCY_COLUMN_LABELS:
            conflicts.append(key or label)
    return list(dict.fromkeys(conflicts))


def _validate_lock_key_usage_for_sdk(view_id: str, schema: dict[str, Any]) -> None:
    lock_key = str(schema.get("lock_key", "") or "").strip()
    if not lock_key:
        return

    conflicts = _collect_lock_key_conflicts(schema)
    if conflicts:
        rendered = ", ".join(conflicts)
        raise CLIError(
            f"数据表 {view_id} 误用 lock_key：lock_key 只用于 Core 临时锁，"
            f"不能与业务占用列同时声明；请删除这些列或移除 lock_key: {rendered}"
        )


class _DeclareUICheckLogger:
    def debug(self, message: str, environment_id: int | None = None) -> None:
        return None

    def info(self, message: str, environment_id: int | None = None) -> None:
        return None

    def warning(self, message: str, environment_id: int | None = None) -> None:
        return None

    def error(self, message: str, environment_id: int | None = None) -> None:
        return None

    def exception(self, message: str, environment_id: int | None = None) -> None:
        return None


class _DeclareUICheckTools:
    def __init__(self) -> None:
        self._pages: dict[str, dict[str, Any]] = {}
        self._schemas: dict[str, dict[str, Any]] = {}
        self._datasets: dict[str, list[dict[str, Any]]] = {}
        self._states: dict[str, Any] = {}
        self._tool_specs = [
            ToolSpec(name="db.acquire_lock", description="db.acquire_lock"),
            ToolSpec(name="db.append_event", description="db.append_event"),
            ToolSpec(name="db.exists_state", description="db.exists_state"),
            ToolSpec(name="db.get_state", description="db.get_state"),
            ToolSpec(name="db.is_locked", description="db.is_locked"),
            ToolSpec(name="db.list_records", description="db.list_records"),
            ToolSpec(name="db.query_events", description="db.query_events"),
            ToolSpec(name="db.release_lock", description="db.release_lock"),
            ToolSpec(name="db.replace_records", description="db.replace_records"),
            ToolSpec(name="db.set_state", description="db.set_state"),
            ToolSpec(name="ui.declare_page", description="ui.declare_page"),
            ToolSpec(name="ui.declare_data_table", description="ui.declare_data_table"),
            ToolSpec(name="ui.get_page", description="ui.get_page"),
            ToolSpec(name="ui.get_data_table", description="ui.get_data_table"),
        ]

    def has_tool(self, tool_name: str) -> bool:
        return tool_name in {spec.name for spec in self._tool_specs}

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tool_specs)

    def call(self, tool_name: str, /, **kwargs: Any) -> Any:
        if tool_name == "ui.declare_page":
            page_id = str(kwargs.get("page_id", "")).strip()
            try:
                self._pages[page_id] = normalize_page_schema(page_id, dict(kwargs.get("schema") or {}))
            except ValueError as exc:
                raise CLIError(f"宿主页 {page_id or '<empty>'} schema 无效: {exc}") from exc
            return True
        if tool_name == "ui.get_page":
            return dict(self._pages.get(str(kwargs.get("page_id", "")).strip(), {}))
        if tool_name == "ui.declare_data_table":
            view_id = str(kwargs.get("view_id", "")).strip()
            try:
                schema = normalize_table_schema(view_id, dict(kwargs.get("schema") or {}))
            except ValueError as exc:
                raise CLIError(f"数据表 {view_id or '<empty>'} schema 无效: {exc}") from exc
            _validate_lock_key_usage_for_sdk(view_id, schema)
            self._schemas[view_id] = schema
            return True
        if tool_name == "ui.get_data_table":
            return dict(self._schemas.get(str(kwargs.get("view_id", "")).strip(), {}))
        if tool_name == "db.list_records":
            dataset = str(kwargs.get("dataset", "")).strip()
            return [dict(row) for row in self._datasets.get(dataset, [])]
        if tool_name == "db.replace_records":
            dataset = str(kwargs.get("dataset", "")).strip()
            records = kwargs.get("records") or []
            self._datasets[dataset] = [dict(row) for row in records if isinstance(row, dict)]
            return True
        if tool_name == "db.append_event":
            raise CLIError("declare_ui 不允许调用 db.append_event；UI 声明必须保持无副作用")
        if tool_name == "db.query_events":
            return []
        if tool_name == "db.acquire_lock":
            return True
        if tool_name == "db.release_lock":
            return True
        if tool_name == "db.is_locked":
            return False
        if tool_name == "db.get_state":
            return self._states.get(str(kwargs.get("key", "")).strip())
        if tool_name == "db.set_state":
            self._states[str(kwargs.get("key", "")).strip()] = kwargs.get("value")
            return True
        if tool_name == "db.exists_state":
            return str(kwargs.get("key", "")).strip() in self._states
        raise KeyError(f"Unknown check tool: {tool_name}")


def _validate_declared_page_handlers(module_runtime: Any, declared_pages: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for page_id, schema in declared_pages.items():
        if not isinstance(schema, dict):
            errors.append(f"宿主页 {page_id} 的 schema 必须是对象")
            continue

        schema_type = str(schema.get("type", "") or "").strip()
        if schema_type != "Page":
            errors.append(f"宿主页 {page_id} 的 schema.type 必须是 Page")

        load_handler_name = str(schema.get("load_handler", "") or "").strip()
        if not load_handler_name:
            errors.append(f"宿主页 {page_id} 缺少 load_handler")
            continue

        error = _validate_runtime_handler(
            module_runtime,
            owner_label=f"宿主页 {page_id}",
            handler_field="load_handler",
            handler_name=load_handler_name,
            runtime_call_label="(context, page_id, params)",
            call_args=(page_id, None),
        )
        if error:
            errors.append(error)
    return errors


def _validate_runtime_handler(
    module_runtime: Any,
    *,
    owner_label: str,
    handler_field: str,
    handler_name: str,
    runtime_call_label: str,
    call_args: tuple[Any, ...],
) -> str | None:
    handler = getattr(module_runtime, handler_name, None)
    if handler is None or not callable(handler):
        return f"{owner_label} 的 {handler_field} 未在 module_runtime.py 中定义: {handler_name}"
    handler_call = getattr(handler, "__call__", None)
    if inspect.iscoroutinefunction(handler) or inspect.iscoroutinefunction(handler_call):
        return f"{owner_label} 的 {handler_field} 必须是同步函数: {handler_name}"
    try:
        signature = inspect.signature(handler)
    except (TypeError, ValueError) as exc:
        return f"{owner_label} 的 {handler_field} 无法解析签名: {handler_name} ({exc})"
    try:
        signature.bind(object(), *call_args)
    except TypeError:
        return (
            f"{owner_label} 的 {handler_field} 签名不兼容，"
            f"运行时会按 {runtime_call_label} 调用: {handler_name}"
        )
    return None


def _validate_declared_data_table_handlers(
    module_runtime: Any,
    declared_tables: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    for view_id, schema in declared_tables.items():
        if not isinstance(schema, dict):
            errors.append(f"数据表 {view_id} 的 schema 必须是对象")
            continue
        for handler_field, runtime_call_label, call_args in (
            ("create_handler", "(context, payload)", ({},)),
            ("update_handler", "(context, row_id, payload)", ("row-1", {})),
        ):
            handler_name = str(schema.get(handler_field, "") or "").strip()
            if not handler_name:
                continue
            error = _validate_runtime_handler(
                module_runtime,
                owner_label=f"数据表 {view_id}",
                handler_field=handler_field,
                handler_name=handler_name,
                runtime_call_label=runtime_call_label,
                call_args=call_args,
            )
            if error:
                errors.append(error)
    return errors


def _validate_declared_ui(module_root: Path, module_runtime: Any, manifest: dict[str, Any]) -> list[str]:
    declare_ui = getattr(module_runtime, "declare_ui", None)
    declared_manifest_pages = {
        str(item.get("id", "")).strip(): str(item.get("entry", "")).strip()
        for item in _manifest_ui_pages(manifest)
        if str(item.get("id", "")).strip()
    }
    if declare_ui is None:
        return ["module_runtime.py 缺少 declare_ui"] if declared_manifest_pages else []
    if inspect.iscoroutinefunction(declare_ui):
        return ["module_runtime.declare_ui 必须是同步函数"]

    tools = _DeclareUICheckTools()
    context = TaskContext(
        env_id=0,
        task_name=module_root.name,
        config={},
        logger=_DeclareUICheckLogger(),
        tools=tools,
        runtime={},
    )
    try:
        declare_ui(context)
    except CLIError as exc:
        return [str(exc)]
    except Exception as exc:
        return [f"declare_ui 校验失败: {exc.__class__.__name__}: {exc}"]

    errors = _validate_declared_page_handlers(module_runtime, tools._pages)
    errors.extend(_validate_declared_data_table_handlers(module_runtime, tools._schemas))

    expected_pages = {
        page_id
        for page_id, entry in declared_manifest_pages.items()
        if _classify_ui_entry(page_id, entry) == "page"
    }
    expected_data_tables = {
        page_id
        for page_id, entry in declared_manifest_pages.items()
        if _classify_ui_entry(page_id, entry) == "data_table"
    }

    missing_pages = sorted(expected_pages - set(tools._pages))
    missing_data_tables = sorted(expected_data_tables - set(tools._schemas))
    extra_pages = sorted(set(tools._pages) - expected_pages)
    extra_data_tables = sorted(set(tools._schemas) - expected_data_tables)

    errors.extend(
        f"module.yaml.ui_extension.pages 声明的宿主页未从 declare_ui 注册: {page_id}"
        for page_id in missing_pages
    )
    errors.extend(
        f"module.yaml.ui_extension.pages 声明的数据表未从 declare_ui 注册: {page_id}"
        for page_id in missing_data_tables
    )
    errors.extend(
        f"declare_ui 注册了未写入 module.yaml.ui_extension.pages 的宿主页: {page_id}"
        for page_id in extra_pages
    )
    errors.extend(
        f"declare_ui 注册了未写入 module.yaml.ui_extension.pages 的数据表: {page_id}"
        for page_id in extra_data_tables
    )
    return errors


def _run_check(level: str, module_root: Path) -> int:
    manifest = load_manifest(module_root)
    if level == "structure":
        errors = collect_structure_errors(module_root, manifest)
    elif level == "release":
        errors = collect_release_errors(module_root, manifest)
    elif level == "full":
        errors = collect_full_errors(module_root, manifest)
    else:  # pragma: no cover - parser guards this
        raise CLIError(f"未知校验级别: {level}")

    if errors:
        _print_error(f"{level} 校验失败")
        for item in errors:
            print(f"  - {item}")
        return 1

    _print_success(f"{level} 校验通过")
    return 0


def _archive_members(module_root: Path) -> list[tuple[Path, str]]:
    ignored_dirs = {
        ".git",
        ".idea",
        ".venv",
        ".vscode",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "__pycache__",
        "build",
        "dist",
    }
    ignored_files = {".DS_Store"}
    members: list[tuple[Path, str]] = []
    for path in module_root.rglob("*"):
        relative = path.relative_to(module_root)
        if any(part in ignored_dirs for part in relative.parts):
            continue
        if any(part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.is_dir():
            continue
        if path.name in ignored_files:
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        arcname = f"{module_root.name}/{relative.as_posix()}"
        members.append((path, arcname))
    return members


def _validate_archive_structure(archive_path: Path) -> tuple[str, list[str]]:
    with zipfile.ZipFile(archive_path, "r") as zf:
        names = [name for name in zf.namelist() if name and not name.startswith("__MACOSX/")]
        roots = {name.split("/", 1)[0] for name in names if "/" in name}
        if len(roots) != 1:
            raise CLIError("ZIP 包结构无效，应仅包含一个根目录")
        root_dir = roots.pop()
        if f"{root_dir}/module.yaml" not in names:
            raise CLIError("ZIP 包缺少根目录下的 module.yaml")
        return root_dir, names


def _extract_archive_to_temp(archive_path: Path) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="crawler4j_sdk_verify_"))
    with zipfile.ZipFile(archive_path, "r") as zf:
        zf.extractall(temp_dir)
    root_dir, _ = _validate_archive_structure(archive_path)
    return temp_dir / root_dir


def _fetch_latest_release(
    repo: str,
    *,
    allow_prerelease: bool = False,
    github_token: str | None = None,
) -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases",
        headers=_github_headers(
            accept="application/vnd.github+json",
            github_token=github_token,
        ),
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        message = _read_http_error_message(exc)
        raise CLIError(f"GitHub 请求失败 ({exc.code}): {message}") from exc

    if not isinstance(payload, list) or not payload:
        raise CLIError(f"仓库 {repo} 没有可用的 GitHub Release")

    for item in payload:
        if not isinstance(item, dict) or item.get("draft"):
            continue
        if item.get("prerelease") and not allow_prerelease:
            continue
        assets = item.get("assets") or []
        zip_assets = [
            asset
            for asset in assets
            if isinstance(asset, dict)
            and str(asset.get("name", "")).lower().endswith(".zip")
            and asset.get("browser_download_url")
        ]
        if len(zip_assets) != 1:
            raise CLIError("每个 Release 必须且只能上传一个 ZIP 安装包")
        tag = str(item.get("tag_name", "") or item.get("name", "") or "").strip().lstrip("v")
        if not is_valid_semver(tag):
            raise CLIError(f"Release 版本号无效: {tag or '<empty>'}")
        return {
            "version": tag,
            "tag_name": str(item.get("tag_name", "") or "").strip(),
            "title": str(item.get("name", "") or item.get("tag_name", "") or "").strip(),
            "published_at": str(item.get("published_at", "") or "").strip(),
            "asset_name": str(zip_assets[0].get("name", "") or "").strip(),
            "asset_download_url": str(zip_assets[0].get("browser_download_url", "") or "").strip(),
            "asset_api_url": str(zip_assets[0].get("url", "") or "").strip(),
            "html_url": str(item.get("html_url", "") or "").strip(),
        }

    if allow_prerelease:
        raise CLIError(f"仓库 {repo} 没有可用的 GitHub Release")
    raise CLIError(f"仓库 {repo} 没有稳定版 GitHub Release")


def cmd_module_init(args: argparse.Namespace) -> int:
    """Initialize a new module project."""
    module_name = str(args.name or "").strip()
    repo = str(args.repo or "").strip()
    if not is_valid_name(module_name):
        _print_error("模块名必须是小写 snake_case，并且能作为 Python 包名导入")
        return 1
    if not is_valid_repo(repo):
        _print_error("`--repo` 必须是 owner/repo 形式")
        return 1
    if not is_valid_name(args.workflow_name):
        _print_error("默认工作流名必须是小写 snake_case")
        return 1
    if not is_valid_semver(args.version):
        _print_error("模块版本必须是合法语义化版本号")
        return 1

    output_dir = Path(args.output).expanduser().resolve() if args.output else Path.cwd() / module_name
    if output_dir.exists() and not output_dir.is_dir():
        _print_error(f"目标路径不是目录: {output_dir}")
        return 1
    if output_dir.name != module_name:
        _print_error("输出目录名必须与模块名一致，避免 module.yaml.name 与包目录漂移")
        return 1
    if output_dir.exists() and any(output_dir.iterdir()) and not args.force:
        _print_error(f"目标目录已存在且非空: {output_dir}")
        return 1

    display_name = args.display_name or to_display_name(module_name)
    description = args.description or f"{display_name} 模块"
    workflow_display_name = args.workflow_display_name or to_display_name(args.workflow_name)
    workflow_description = args.workflow_description or f"{workflow_display_name} 工作流"
    sdk_dependency_spec = get_compatible_dependency_spec()

    output_dir.mkdir(parents=True, exist_ok=True)
    for subdir in ["tasks", "workflows", "tests"]:
        _ensure_package_dir(output_dir / subdir)

    try:
        _write_text(
            output_dir / "pyproject.toml",
            MODEL_PROJECT_PYPROJECT.format(
                project_name=module_name,
                version=args.version,
                display_name=display_name,
                python_version=args.python_version,
                sdk_dependency_spec=sdk_dependency_spec,
            ),
            force=args.force,
        )
        _write_text(
            output_dir / "README.md",
            MODEL_PROJECT_README.format(display_name=display_name),
            force=args.force,
        )
        _write_text(
            output_dir / "__init__.py",
            MODEL_MODULE_INIT.format(display_name=display_name),
            force=args.force,
        )
        _write_text(
            output_dir / "module_runtime.py",
            MODEL_RUNTIME_TEMPLATE.format(display_name=display_name),
            force=args.force,
        )
        _write_text(
            output_dir / "module.yaml",
            MODEL_MANIFEST_TEMPLATE.format(
                module_name=module_name,
                version=args.version,
                display_name=display_name,
                description=description,
                repo=repo,
                workflow_name=args.workflow_name,
                workflow_display_name=workflow_display_name,
                workflow_description=workflow_description,
            ),
            force=args.force,
        )
        _write_text(
            output_dir / "tasks" / "example_task.py",
            SCRIPT_TEMPLATE.format(
                name="example_task",
                class_name="ExampleTask",
                display_name="示例任务",
                description="示例任务脚本",
            ),
            force=args.force,
        )
        _write_text(
            output_dir / "workflows" / f"{args.workflow_name}.py",
            WORKFLOW_TEMPLATE.format(
                name=args.workflow_name,
                class_name=f"{to_class_name(args.workflow_name)}Workflow",
                display_name=workflow_display_name,
                description=workflow_description,
            ),
            force=args.force,
        )
        _write_text(output_dir / "tests" / "test_tasks.py", MODEL_TEST_TASK_TEMPLATE, force=args.force)
        _write_text(output_dir / ".gitignore", MODEL_GITIGNORE_TEMPLATE, force=args.force)
        _write_text(output_dir / ".python-version", f"{args.python_version}\n", force=args.force)
    except CLIError as exc:
        _print_error(str(exc))
        return 1

    try:
        if not args.no_git:
            _safe_run(["git", "init"], cwd=output_dir)
        if not args.no_install:
            _safe_run(["uv", "sync"], cwd=output_dir)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        _print_error(f"自动初始化失败: {exc}")
        return 1

    _print_success(f"已初始化模块项目: {output_dir}")
    print("  - 命令入口: `crawler4j module show`")
    print("  - 新建任务: `crawler4j task create <name>`")
    print("  - 新建工作流: `crawler4j workflow create <name>`")
    print("  - 完整校验: `crawler4j check full`")
    return 0


def cmd_module_show(args: argparse.Namespace) -> int:
    """Show the current module summary."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    hosted_pages = _manifest_ui_entries_by_kind(manifest, "page")
    data_tables = _manifest_ui_entries_by_kind(manifest, "data_table")
    workflow_names = _manifest_workflow_names(manifest)
    runtime_path = module_root / "module_runtime.py"
    default_workflow = _read_default_workflow(runtime_path) or (workflow_names[0] if workflow_names else "")

    print(f"模块目录: {module_root}")
    print(f"模块名: {manifest.get('name', '')}")
    print(f"版本: {manifest.get('version', '')}")
    print(f"仓库: {(manifest.get('upgrade_source') or {}).get('repo', '')}")
    print(f"默认工作流: {default_workflow}")
    print(f"任务: {', '.join(_list_python_modules(module_root / 'tasks')) or '(无)'}")
    print(f"工作流: {', '.join(workflow_names) or '(无)'}")
    print(
        "宿主页: "
        + (
            ", ".join(str(item.get("id", "")) for item in hosted_pages if item.get("id"))
            or "(无)"
        )
    )
    print(
        "数据表入口: "
        + (
            ", ".join(str(item.get("id", "")) for item in data_tables if item.get("id"))
            or "(无)"
        )
    )
    return 0


def cmd_module_set_repo(args: argparse.Namespace) -> int:
    """Set manifest upgrade_source.repo."""
    module_root = require_module_root()
    if not is_valid_repo(args.repo):
        _print_error("仓库必须是 owner/repo 形式")
        return 1
    manifest = load_manifest(module_root)
    upgrade_source = manifest.setdefault("upgrade_source", {})
    if not isinstance(upgrade_source, dict):
        _print_error("module.yaml.upgrade_source 必须是映射对象")
        return 1
    upgrade_source["type"] = "github_release"
    upgrade_source["repo"] = args.repo
    upgrade_source.setdefault("allow_prerelease", False)
    save_manifest(module_root, manifest)
    _print_success(f"已设置升级仓库: {args.repo}")
    return 0


def cmd_module_set_version(args: argparse.Namespace) -> int:
    """Set manifest version."""
    module_root = require_module_root()
    if not is_valid_semver(args.version):
        _print_error("版本号必须是合法语义化版本")
        return 1
    try:
        _set_project_version(module_root / "pyproject.toml", args.version)
    except CLIError as exc:
        _print_error(str(exc))
        return 1
    manifest = load_manifest(module_root)
    manifest["version"] = args.version
    save_manifest(module_root, manifest)
    _print_success(f"已设置模块版本: {args.version}")
    return 0


def cmd_module_set_default_workflow(args: argparse.Namespace) -> int:
    """Set DEFAULT_WORKFLOW inside module_runtime.py."""
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    workflow_name = str(args.workflow or "").strip()
    if workflow_name not in _manifest_workflow_names(manifest):
        _print_error(f"未声明的 workflow: {workflow_name}")
        return 1
    _set_default_workflow(module_root / "module_runtime.py", workflow_name)
    _print_success(f"已设置默认工作流: {workflow_name}")
    return 0


def cmd_task_create(args: argparse.Namespace) -> int:
    """Create a task script under tasks/."""
    module_root = require_module_root()
    name = str(args.name or "").strip()
    if not is_valid_name(name):
        _print_error("任务名必须是小写 snake_case")
        return 1
    try:
        _write_text(
            module_root / "tasks" / f"{name}.py",
            SCRIPT_TEMPLATE.format(
                name=name,
                class_name=f"{to_class_name(name)}Task",
                display_name=to_display_name(name),
                description=f"{to_display_name(name)} 任务",
            ),
            force=args.force,
        )
    except CLIError as exc:
        _print_error(str(exc))
        return 1
    _print_success(f"已创建任务脚本: tasks/{name}.py")
    return 0


def cmd_task_list(args: argparse.Namespace) -> int:
    """List task scripts in the current module."""
    del args
    module_root = require_module_root()
    tasks = _list_python_modules(module_root / "tasks")
    print("\n".join(tasks) if tasks else "(无任务)")
    return 0


def cmd_workflow_create(args: argparse.Namespace) -> int:
    """Create a workflow file and register it in module.yaml."""
    module_root = require_module_root()
    name = str(args.name or "").strip()
    if not is_valid_name(name):
        _print_error("工作流名必须是小写 snake_case")
        return 1
    manifest = load_manifest(module_root)
    try:
        _write_text(
            module_root / "workflows" / f"{name}.py",
            WORKFLOW_TEMPLATE.format(
                name=name,
                class_name=f"{to_class_name(name)}Workflow",
                display_name=args.display_name or to_display_name(name),
                description=args.description or f"{to_display_name(name)} 工作流",
            ),
            force=args.force,
        )
    except CLIError as exc:
        _print_error(str(exc))
        return 1

    workflows = _manifest_workflows(manifest)
    if not any(isinstance(item, dict) and item.get("name") == name for item in workflows):
        workflows.append(
            {
                "name": name,
                "display_name": args.display_name or to_display_name(name),
                "description": args.description or f"{to_display_name(name)} 工作流",
            }
        )
        save_manifest(module_root, manifest)
    _print_success(f"已创建工作流: workflows/{name}.py")
    return 0


def cmd_workflow_list(args: argparse.Namespace) -> int:
    """List workflows declared in module.yaml."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    names = _manifest_workflow_names(manifest)
    print("\n".join(names) if names else "(无工作流)")
    return 0


def cmd_page_create(args: argparse.Namespace) -> int:
    """Create a hosted page scaffold inside module_runtime.py."""
    module_root = require_module_root()
    name = str(args.name or "").strip()
    if not is_valid_name(name):
        _print_error("页面名必须是小写 snake_case")
        return 1

    manifest = load_manifest(module_root)
    pages = _normalize_ui_pages(manifest)
    existing_page = next(
        (item for item in pages if isinstance(item, dict) and item.get("id") == name),
        None,
    )
    if existing_page is not None:
        if not args.force:
            _print_error(f"页面入口已存在: {name}")
            return 1
        existing_page["label"] = args.display_name or to_display_name(name)
        existing_page["icon"] = "📄"
        existing_page["entry"] = f"core:page:{name}"
    else:
        pages.append(
            {
                "id": name,
                "label": args.display_name or to_display_name(name),
                "icon": "📄",
                "entry": f"core:page:{name}",
            }
        )
    runtime_path = module_root / "module_runtime.py"
    runtime_text = runtime_path.read_text(encoding="utf-8")
    helper_name = f"_declare_{name}_page"
    helper_block = PAGE_HELPER_TEMPLATE.format(
        page_id=name,
        display_name=args.display_name or to_display_name(name),
        description=args.description or f"{to_display_name(name)} 宿主页",
    )
    helper_functions = [
        helper_name,
        f"build_{name}_page_schema",
        f"load_{name}_page",
    ]
    if args.force:
        runtime_text = _upsert_function_block(runtime_text, helper_functions, helper_block)
    elif helper_name not in runtime_text:
        runtime_text += helper_block

    call_line = f"    {helper_name}(context)"
    try:
        runtime_text = _insert_declare_ui_call(runtime_text, call_line)
    except (CLIError, SyntaxError) as exc:
        _print_error(f"无法更新 module_runtime.py: {exc}")
        return 1

    runtime_path.write_text(runtime_text, encoding="utf-8")
    save_manifest(module_root, manifest)
    _print_success(f"已创建宿主页骨架: {name}")
    return 0


def cmd_page_list(args: argparse.Namespace) -> int:
    """List hosted pages declared in module.yaml."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    pages = [
        str(item.get("id", ""))
        for item in _manifest_ui_entries_by_kind(manifest, "page")
        if item.get("id")
    ]
    print("\n".join(pages) if pages else "(无页面)")
    return 0


def cmd_data_table_create(args: argparse.Namespace) -> int:
    """Register a managed core:data_table page and append a declare_ui helper."""
    module_root = require_module_root()
    view_id = str(args.view_id or "").strip()
    if not is_valid_name(view_id):
        _print_error("数据表 ID 必须是小写 snake_case")
        return 1

    manifest = load_manifest(module_root)
    pages = _normalize_ui_pages(manifest)
    if any(isinstance(item, dict) and item.get("id") == view_id for item in pages):
        _print_error(f"数据表入口已存在: {view_id}")
        return 1

    pages.append(
        {
            "id": view_id,
            "label": args.label or to_display_name(view_id),
            "icon": args.icon or "📋",
            "entry": f"core:data_table:{view_id}",
        }
    )
    runtime_path = module_root / "module_runtime.py"
    runtime_text = runtime_path.read_text(encoding="utf-8")
    helper_name = f"_declare_{view_id}_table"
    if helper_name not in runtime_text:
        runtime_text += DATA_TABLE_HELPER_TEMPLATE.format(
            view_id=view_id,
            display_name=args.label or to_display_name(view_id),
        )

    call_line = f"    {helper_name}(context)"
    try:
        runtime_text = _insert_declare_ui_call(runtime_text, call_line)
    except (CLIError, SyntaxError) as exc:
        _print_error(f"无法更新 module_runtime.py: {exc}")
        return 1

    runtime_path.write_text(runtime_text, encoding="utf-8")
    save_manifest(module_root, manifest)
    _print_success(f"已注册受控数据表入口: core:data_table:{view_id}")
    return 0


def cmd_data_table_list(args: argparse.Namespace) -> int:
    """List managed data-table pages from module.yaml."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    rows = [
        str(item.get("id", ""))
        for item in _manifest_ui_entries_by_kind(manifest, "data_table")
        if item.get("id")
    ]
    print("\n".join(rows) if rows else "(无数据表入口)")
    return 0


def cmd_env_selector_create(args: argparse.Namespace) -> int:
    """Append a new env_selector function into module_runtime.py."""
    module_root = require_module_root()
    name = str(args.name or "").strip()
    if not is_valid_name(name):
        _print_error("环境选择器名必须是小写 snake_case")
        return 1
    runtime_path = module_root / "module_runtime.py"
    text = runtime_path.read_text(encoding="utf-8")
    if f'name="{name}"' in text or f"name='{name}'" in text:
        _print_error(f"环境选择器已存在: {name}")
        return 1
    text += ENV_SELECTOR_TEMPLATE.format(
        name=name,
        display_name=args.display_name or to_display_name(name),
        description=args.description or f"{to_display_name(name)} 环境选择器",
        function_name=f"{name}_selector",
    )
    runtime_path.write_text(text, encoding="utf-8")
    _print_success(f"已创建环境选择器: {name}")
    return 0


def cmd_env_selector_list(args: argparse.Namespace) -> int:
    """List env_selector declarations."""
    del args
    module_root = require_module_root()
    try:
        module = _import_module_root(module_root)
        assembler = getattr(module, "assembler", None)
        selectors = []
        if assembler and hasattr(assembler, "list_env_selectors"):
            selectors = [item.name for item in assembler.list_env_selectors()]
        print("\n".join(selectors) if selectors else "(无环境选择器)")
        return 0
    except Exception:
        runtime_text = (module_root / "module_runtime.py").read_text(encoding="utf-8")
        names = re.findall(r'name\s*=\s*["\']([a-z][a-z0-9_]*)["\']', runtime_text)
        print("\n".join(sorted(set(names))) if names else "(无环境选择器)")
        return 0


def cmd_config_show(args: argparse.Namespace) -> int:
    """Show config_defaults from module.yaml."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    config_defaults = manifest.get("config_defaults") or {"module": {}, "workflows": {}}
    print(_render_yaml(config_defaults))
    return 0


def cmd_config_set_module(args: argparse.Namespace) -> int:
    """Set module-level default config from a YAML file."""
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    config_defaults = _normalize_config_defaults(manifest)
    config_defaults["module"] = _load_yaml_mapping(Path(args.file).expanduser().resolve())
    save_manifest(module_root, manifest)
    _print_success("已更新模块级默认配置")
    return 0


def cmd_config_set_workflow(args: argparse.Namespace) -> int:
    """Set workflow-level default config from a YAML file."""
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    workflow_name = str(args.workflow or "").strip()
    if workflow_name not in _manifest_workflow_names(manifest):
        _print_error(f"未声明的 workflow: {workflow_name}")
        return 1
    config_defaults = _normalize_config_defaults(manifest)
    config_defaults["workflows"][workflow_name] = _load_yaml_mapping(
        Path(args.file).expanduser().resolve()
    )
    save_manifest(module_root, manifest)
    _print_success(f"已更新工作流默认配置: {workflow_name}")
    return 0


def cmd_config_lint(args: argparse.Namespace) -> int:
    """Validate config_defaults structure and workflow references."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    config_defaults = manifest.get("config_defaults", {})
    test_manifest = dict(manifest)
    test_manifest["config_defaults"] = config_defaults
    errors = collect_release_errors(module_root, test_manifest)
    config_errors = [item for item in errors if item.startswith("config_defaults")]
    if config_errors:
        _print_error("默认配置校验失败")
        for item in config_errors:
            print(f"  - {item}")
        return 1
    _print_success("默认配置校验通过")
    return 0


def cmd_package_build(args: argparse.Namespace) -> int:
    """Build an installable single-root ZIP package for the current module."""
    module_root = require_module_root()
    if _run_check("full", module_root) != 0:
        return 1

    manifest = load_manifest(module_root)
    version = str(manifest.get("version", "") or "").strip()
    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else module_root / "dist" / f"{module_root.name}-{version}.zip"
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for source, arcname in _archive_members(module_root):
            zf.write(source, arcname)

    try:
        _validate_archive_structure(output)
    except CLIError as exc:
        _print_error(str(exc))
        return 1

    _print_success(f"已生成安装包: {output}")
    return 0


def cmd_package_verify(args: argparse.Namespace) -> int:
    """Verify a ZIP package follows the expected module archive layout."""
    archive_path = Path(args.archive).expanduser().resolve()
    if not archive_path.exists():
        _print_error(f"找不到 ZIP 文件: {archive_path}")
        return 1

    extracted_root: Path | None = None
    try:
        _validate_archive_structure(archive_path)
        extracted_root = _extract_archive_to_temp(archive_path)
        manifest = load_manifest(extracted_root)
        errors = collect_full_errors(extracted_root, manifest)
    except (CLIError, zipfile.BadZipFile) as exc:
        _print_error(str(exc))
        return 1
    finally:
        if extracted_root:
            shutil.rmtree(extracted_root.parent, ignore_errors=True)

    if errors:
        _print_error("ZIP 校验失败")
        for item in errors:
            print(f"  - {item}")
        return 1

    _print_success("ZIP 校验通过")
    return 0


def cmd_release_status(args: argparse.Namespace) -> int:
    """Show local release readiness for the current module."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    errors = collect_release_errors(module_root, manifest)
    version = str(manifest.get("version", "") or "").strip()
    repo = str((manifest.get("upgrade_source") or {}).get("repo", "") or "").strip()
    archive_path = module_root / "dist" / f"{module_root.name}-{version}.zip"

    print(f"模块: {manifest.get('name', '')}")
    print(f"版本: {version}")
    print(f"仓库: {repo or '(未设置)'}")
    print(f"安装包: {archive_path if archive_path.exists() else '(未构建)'}")
    if errors:
        print("发布状态: BLOCKED")
        for item in errors:
            print(f"  - {item}")
        return 1

    print("发布状态: READY")
    return 0


def cmd_release_check_remote(args: argparse.Namespace) -> int:
    """Compare local manifest version against the latest GitHub Release."""
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    repo = str((manifest.get("upgrade_source") or {}).get("repo", "") or "").strip()
    if not is_valid_repo(repo):
        _print_error("module.yaml.upgrade_source.repo 不是合法的 owner/repo")
        return 1

    allow_prerelease = bool((manifest.get("upgrade_source") or {}).get("allow_prerelease", False))
    local_version = str(manifest.get("version", "") or "").strip()
    try:
        remote = _fetch_latest_release(
            repo,
            allow_prerelease=allow_prerelease,
            github_token=getattr(args, "github_token", None),
        )
    except (CLIError, urllib.error.URLError) as exc:
        _print_error(f"远端版本检查失败: {exc}")
        return 1

    relation = "equal"
    if _compare_versions(local_version, remote["version"]) < 0:
        relation = "behind"
    elif _compare_versions(local_version, remote["version"]) > 0:
        relation = "ahead"

    print(f"本地版本: {local_version}")
    print(f"远端版本: {remote['version']}")
    print(f"Release: {remote['title'] or remote['tag_name']}")
    print(f"安装包: {remote['asset_name']}")
    print(f"状态: {relation}")
    return 0


def cmd_release_publish(args: argparse.Namespace) -> int:
    """Publish the local ZIP asset to a GitHub Release via gh CLI."""
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    repo = str((manifest.get("upgrade_source") or {}).get("repo", "") or "").strip()
    version = str(manifest.get("version", "") or "").strip()
    if not is_valid_repo(repo):
        _print_error("module.yaml.upgrade_source.repo 不是合法的 owner/repo")
        return 1
    if not is_valid_semver(version):
        _print_error("module.yaml.version 不是合法语义化版本")
        return 1

    tag = args.tag or f"v{version}"
    title = args.title or tag
    archive_path = (
        Path(args.archive).expanduser().resolve()
        if args.archive
        else module_root / "dist" / f"{module_root.name}-{version}.zip"
    )

    if args.rebuild or not archive_path.exists():
        build_result = cmd_package_build(argparse.Namespace(output=str(archive_path)))
        if build_result != 0:
            return build_result
    elif cmd_package_verify(argparse.Namespace(archive=str(archive_path))) != 0:
        return 1

    if args.notes and args.notes_file:
        _print_error("`--notes` 和 `--notes-file` 不能同时使用")
        return 1

    notes_args: list[str] = []
    if args.notes:
        notes_args = ["--notes", args.notes]
    elif args.notes_file:
        notes_args = ["--notes-file", str(Path(args.notes_file).expanduser().resolve())]

    view_cmd = ["gh", "release", "view", tag, "--repo", repo]
    create_cmd = [
        "gh",
        "release",
        "create",
        tag,
        str(archive_path),
        "--repo",
        repo,
        "--title",
        title,
        *notes_args,
    ]
    upload_cmd = [
        "gh",
        "release",
        "upload",
        tag,
        str(archive_path),
        "--repo",
        repo,
        "--clobber",
    ]
    if args.prerelease:
        create_cmd.append("--prerelease")

    if args.dry_run:
        print("将执行以下命令：")
        print("  " + " ".join(view_cmd))
        print("  " + " ".join(create_cmd))
        print("  " + " ".join(upload_cmd))
        return 0

    try:
        view_result = subprocess.run(view_cmd, check=False, capture_output=True, text=True)
        publish_cmd = upload_cmd if view_result.returncode == 0 else create_cmd
        subprocess.run(publish_cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        _print_error("未找到 `gh` 命令；请先安装 GitHub CLI 并完成登录")
        return 1
    except subprocess.CalledProcessError as exc:
        _print_error(exc.stderr.strip() or exc.stdout.strip() or str(exc))
        return 1

    _print_success(f"已发布 Release 资产: {repo} {tag}")
    return 0


def cmd_host_devlink_add(args: argparse.Namespace) -> int:
    """Register a local module path as a dev link in the host runtime."""
    runtime = _load_host_runtime()
    _init_host_runtime(runtime)
    registry = runtime["get_module_registry"]()
    module = registry.register_dev_link(Path(args.module_root).expanduser().resolve())
    _print_success("已注册 DevLink 模块")
    _print_module_info(module)
    return 0


def cmd_host_devlink_remove(args: argparse.Namespace) -> int:
    """Remove a dev link from the host runtime."""
    runtime = _load_host_runtime()
    _init_host_runtime(runtime)
    registry = runtime["get_module_registry"]()
    removed = registry.remove_dev_link(args.module_name)
    if not removed:
        _print_error(f"找不到 DevLink 模块: {args.module_name}")
        return 1
    _print_success(f"已移除 DevLink: {args.module_name}")
    return 0


def cmd_host_devlink_list(args: argparse.Namespace) -> int:
    """List host dev links."""
    del args
    runtime = _load_host_runtime()
    _init_host_runtime(runtime)
    registry = runtime["get_module_registry"]()
    links = list(registry.list_dev_links())
    if not links:
        print("(无 DevLink)")
        return 0
    for item in links:
        print(f"{item.module_name}\t{item.source_path}")
    return 0


def cmd_host_install_preview(args: argparse.Namespace) -> int:
    """Preview installing a local ZIP or GitHub repo into the host runtime."""
    runtime = _load_host_runtime()
    _init_host_runtime(runtime)
    registry = runtime["get_module_registry"]()
    service = runtime["get_module_release_service"]()
    source_kind, source_value = _detect_install_source(args.source)

    if source_kind == "dir":
        _print_error("目录源码请走 `crawler4j host devlink add <module_root>`，不要走 install")
        return 1
    if source_kind == "file":
        _print_error("install 目前只支持 ZIP 安装包或 GitHub 仓库")
        return 1

    try:
        if source_kind == "zip" and args.skip_remote_check:
            manifest, warnings = registry.validate_source(source_value)
            _print_preview(
                source_label="本地 ZIP（跳过远端仓库校验）",
                manifest=manifest,
                warnings=warnings,
                archive_path=Path(source_value),
            )
            return 0

        if source_kind == "zip":
            preview = _run_async(
                service.prepare_local_install(
                    source_value,
                    github_token=getattr(args, "github_token", None),
                )
            )
        else:
            preview = _run_async(
                service.prepare_github_install(
                    str(source_value),
                    github_token=getattr(args, "github_token", None),
                )
            )
    except Exception as exc:
        _print_error(str(exc))
        return 1

    _print_preview(
        source_label=preview.source_label,
        manifest=preview.manifest,
        warnings=list(preview.warnings),
        archive_path=preview.archive_path,
        release=preview.release,
    )
    return 0


def cmd_host_install_apply(args: argparse.Namespace) -> int:
    """Install a local ZIP or GitHub repo into the host runtime."""
    runtime = _load_host_runtime()
    _init_host_runtime(runtime)
    registry = runtime["get_module_registry"]()
    service = runtime["get_module_release_service"]()
    source_kind, source_value = _detect_install_source(args.source)

    if source_kind == "dir":
        _print_error("目录源码请走 `crawler4j host devlink add <module_root>`，不要走 install")
        return 1
    if source_kind == "file":
        _print_error("install 目前只支持 ZIP 安装包或 GitHub 仓库")
        return 1

    try:
        if source_kind == "zip" and args.skip_remote_check:
            module = registry.install(source_value)
        elif source_kind == "zip":
            preview = _run_async(
                service.prepare_local_install(
                    source_value,
                    github_token=getattr(args, "github_token", None),
                )
            )
            module = registry.install(preview.archive_path or source_value)
        else:
            preview = _run_async(
                service.prepare_github_install(
                    str(source_value),
                    github_token=getattr(args, "github_token", None),
                )
            )
            module = registry.install(preview.archive_path)
    except Exception as exc:
        _print_error(str(exc))
        return 1

    _print_success("模块安装完成")
    _print_module_info(module)
    return 0


def cmd_host_upgrade_check(args: argparse.Namespace) -> int:
    """Check whether an installed external module has a newer GitHub Release."""
    runtime = _load_host_runtime()
    _init_host_runtime(runtime)
    registry = runtime["get_module_registry"]()
    service = runtime["get_module_release_service"]()
    module = registry.get_module(args.module_name)
    if not module:
        _print_error(f"找不到模块: {args.module_name}")
        return 1

    try:
        update_info = _run_async(
            service.check_for_update(
                module,
                github_token=getattr(args, "github_token", None),
            )
        )
    except Exception as exc:
        _print_error(str(exc))
        return 1

    print(f"模块名: {update_info.module_name}")
    print(f"当前版本: {update_info.current_version}")
    print(f"远端版本: {update_info.latest_version}")
    print(f"是否可升级: {'yes' if update_info.has_update else 'no'}")
    if update_info.release:
        print(f"Release 页面: {update_info.release.html_url}")
        print(f"安装包: {update_info.release.asset_name}")
    if update_info.error:
        print(f"错误: {update_info.error}")
        return 1
    return 0


def cmd_host_upgrade_preview(args: argparse.Namespace) -> int:
    """Preview upgrading an installed module from GitHub Release."""
    runtime = _load_host_runtime()
    _init_host_runtime(runtime)
    registry = runtime["get_module_registry"]()
    service = runtime["get_module_release_service"]()
    module = registry.get_module(args.module_name)
    if not module:
        _print_error(f"找不到模块: {args.module_name}")
        return 1

    try:
        preview = _run_async(
            service.prepare_module_upgrade(
                module,
                github_token=getattr(args, "github_token", None),
            )
        )
    except Exception as exc:
        _print_error(str(exc))
        return 1

    _print_preview(
        source_label=preview.source_label,
        manifest=preview.manifest,
        warnings=list(preview.warnings),
        archive_path=preview.archive_path,
        release=preview.release,
    )
    return 0


def cmd_host_upgrade_apply(args: argparse.Namespace) -> int:
    """Download and install the newer GitHub Release for an external module."""
    runtime = _load_host_runtime()
    _init_host_runtime(runtime)
    registry = runtime["get_module_registry"]()
    service = runtime["get_module_release_service"]()
    module = registry.get_module(args.module_name)
    if not module:
        _print_error(f"找不到模块: {args.module_name}")
        return 1

    try:
        preview = _run_async(
            service.prepare_module_upgrade(
                module,
                github_token=getattr(args, "github_token", None),
            )
        )
        installed = _run_async(service.apply_module_upgrade(module, preview))
    except Exception as exc:
        _print_error(str(exc))
        return 1

    _print_success("模块升级完成")
    _print_module_info(installed)
    return 0


def cmd_host_debug_config(args: argparse.Namespace) -> int:
    """Generate or update a VS Code attach configuration for module debugging."""
    runtime = _load_host_runtime()
    source_path = (
        Path(args.module_root).expanduser().resolve()
        if args.module_root
        else require_module_root()
    )
    launch_path = runtime["ensure_vscode_attach_config"](
        source_path,
        host=args.host,
        port=args.port,
        configuration_name=args.configuration_name,
    )
    _print_success(f"已生成 VS Code 调试配置: {launch_path}")
    return 0


def cmd_check_structure(args: argparse.Namespace) -> int:
    """Run structure-level validation."""
    del args
    return _run_check("structure", require_module_root())


def cmd_check_release(args: argparse.Namespace) -> int:
    """Run release-level validation."""
    del args
    return _run_check("release", require_module_root())


def cmd_check_full(args: argparse.Namespace) -> int:
    """Run full validation including importability."""
    del args
    return _run_check("full", require_module_root())


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""
    parser = argparse.ArgumentParser(
        prog="crawler4j",
        description="Crawler4j SDK 模块工程 CLI",
    )
    subparsers = parser.add_subparsers(dest="group")

    module_parser = subparsers.add_parser(
        "module",
        help="模块项目操作：初始化、查看和修改 module.yaml 关键字段",
    )
    module_sub = module_parser.add_subparsers(dest="action")

    module_init = module_sub.add_parser(
        "init",
        help="初始化一个新的模块项目，生成标准骨架、module.yaml 和 module_runtime.py",
    )
    module_init.add_argument("name", help="模块包名，必须是 snake_case")
    module_init.add_argument("--repo", required=True, help="升级源 GitHub 仓库，格式 owner/repo")
    module_init.add_argument("--output", help="输出目录，默认在当前目录下创建同名目录")
    module_init.add_argument("--display-name", help="模块显示名")
    module_init.add_argument("--description", help="模块说明")
    module_init.add_argument("--version", default=DEFAULT_MODULE_VERSION, help="模块版本号")
    module_init.add_argument("--workflow-name", default="main_workflow", help="初始工作流名")
    module_init.add_argument("--workflow-display-name", help="初始工作流显示名")
    module_init.add_argument("--workflow-description", help="初始工作流说明")
    module_init.add_argument("--python-version", default=DEFAULT_PYTHON_VERSION, help="目标 Python 版本")
    module_init.add_argument("--no-git", action="store_true", help="不要执行 git init")
    module_init.add_argument("--no-install", action="store_true", help="不要执行 uv sync")
    module_init.add_argument("--force", action="store_true", help="允许覆盖脚手架管理文件")
    module_init.set_defaults(func=cmd_module_init)

    module_show = module_sub.add_parser(
        "show",
        help="显示当前模块的版本、仓库、默认工作流、宿主页和数据表入口",
    )
    module_show.set_defaults(func=cmd_module_show)

    module_set = module_sub.add_parser(
        "set",
        help="修改 module.yaml 或 module_runtime.py 中的关键字段",
    )
    module_set_sub = module_set.add_subparsers(dest="field")

    module_set_repo = module_set_sub.add_parser(
        "repo",
        help="设置 module.yaml.upgrade_source.repo",
    )
    module_set_repo.add_argument("repo", help="GitHub 仓库，格式 owner/repo")
    module_set_repo.set_defaults(func=cmd_module_set_repo)

    module_set_version = module_set_sub.add_parser(
        "version",
        help="设置 module.yaml.version",
    )
    module_set_version.add_argument("version", help="语义化版本号")
    module_set_version.set_defaults(func=cmd_module_set_version)

    module_set_default_workflow = module_set_sub.add_parser(
        "default-workflow",
        help="设置 module_runtime.py 里的 DEFAULT_WORKFLOW",
    )
    module_set_default_workflow.add_argument("workflow", help="已声明的 workflow 名称")
    module_set_default_workflow.set_defaults(func=cmd_module_set_default_workflow)

    task_parser = subparsers.add_parser(
        "task",
        help="任务脚本操作：在 tasks/ 下创建或列出 TaskScript 文件",
    )
    task_sub = task_parser.add_subparsers(dest="action")
    task_create = task_sub.add_parser(
        "create",
        help="创建一个新的 TaskScript 文件，不会修改 module.yaml",
    )
    task_create.add_argument("name", help="任务名，snake_case")
    task_create.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    task_create.set_defaults(func=cmd_task_create)
    task_list = task_sub.add_parser("list", help="列出 tasks/ 下的任务脚本")
    task_list.set_defaults(func=cmd_task_list)

    workflow_parser = subparsers.add_parser(
        "workflow",
        help="工作流操作：创建 workflow 文件并维护 module.yaml.workflows",
    )
    workflow_sub = workflow_parser.add_subparsers(dest="action")
    workflow_create = workflow_sub.add_parser(
        "create",
        help="创建工作流文件，并把 workflow 注册进 module.yaml",
    )
    workflow_create.add_argument("name", help="工作流名，snake_case")
    workflow_create.add_argument("--display-name", help="工作流显示名")
    workflow_create.add_argument("--description", help="工作流说明")
    workflow_create.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    workflow_create.set_defaults(func=cmd_workflow_create)
    workflow_list = workflow_sub.add_parser("list", help="列出 module.yaml 中声明的工作流")
    workflow_list.set_defaults(func=cmd_workflow_list)

    page_parser = subparsers.add_parser(
        "page",
        help="宿主页操作：在 module_runtime.py 生成 hosted page 骨架并维护 ui_extension.pages",
    )
    page_sub = page_parser.add_subparsers(dest="action")
    page_create = page_sub.add_parser(
        "create",
        help="创建一个宿主页骨架，并把它注册到 ui_extension.pages",
    )
    page_create.add_argument("name", help="页面名，snake_case")
    page_create.add_argument("--display-name", help="页面显示名")
    page_create.add_argument("--description", help="页面说明")
    page_create.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    page_create.set_defaults(func=cmd_page_create)
    page_list = page_sub.add_parser("list", help="列出 ui_extension.pages 中的宿主页入口")
    page_list.set_defaults(func=cmd_page_list)

    data_table_parser = subparsers.add_parser(
        "data-table",
        help="受控数据表操作：注册 ui_extension.pages 中的 core:data_table:<id> 入口并补 declare_ui 骨架",
    )
    data_table_sub = data_table_parser.add_subparsers(dest="action")
    data_table_create = data_table_sub.add_parser(
        "create",
        help="创建一个受控数据表入口，会更新 ui_extension.pages 并在 module_runtime.py 追加声明函数",
    )
    data_table_create.add_argument("view_id", help="数据表视图 ID，snake_case")
    data_table_create.add_argument("--label", help="数据表显示名")
    data_table_create.add_argument("--icon", help="数据表图标")
    data_table_create.set_defaults(func=cmd_data_table_create)
    data_table_list = data_table_sub.add_parser("list", help="列出 ui_extension.pages 中的受控数据表入口")
    data_table_list.set_defaults(func=cmd_data_table_list)

    selector_parser = subparsers.add_parser(
        "env-selector",
        help="环境选择器操作：在 module_runtime.py 中声明 @env_selector(...) 函数",
    )
    selector_sub = selector_parser.add_subparsers(dest="action")
    selector_create = selector_sub.add_parser(
        "create",
        help="创建一个环境选择策略函数，用于 ATM 的“选择环境”模式",
    )
    selector_create.add_argument("name", help="选择器名，snake_case")
    selector_create.add_argument("--display-name", help="显示名")
    selector_create.add_argument("--description", help="说明")
    selector_create.set_defaults(func=cmd_env_selector_create)
    selector_list = selector_sub.add_parser("list", help="列出模块声明的环境选择器")
    selector_list.set_defaults(func=cmd_env_selector_list)

    config_parser = subparsers.add_parser(
        "config",
        help="默认配置操作：管理 module.yaml.config_defaults",
    )
    config_sub = config_parser.add_subparsers(dest="action")
    config_show = config_sub.add_parser("show", help="显示 config_defaults 当前内容")
    config_show.set_defaults(func=cmd_config_show)
    config_set = config_sub.add_parser(
        "set",
        help="从 YAML 文件写入模块级或工作流级默认配置",
    )
    config_set_sub = config_set.add_subparsers(dest="scope")
    config_set_module = config_set_sub.add_parser(
        "module",
        help="把 YAML 文件写入 config_defaults.module",
    )
    config_set_module.add_argument("--file", required=True, help="YAML 文件路径")
    config_set_module.set_defaults(func=cmd_config_set_module)
    config_set_workflow = config_set_sub.add_parser(
        "workflow",
        help="把 YAML 文件写入 config_defaults.workflows.<workflow>",
    )
    config_set_workflow.add_argument("workflow", help="已声明的 workflow 名称")
    config_set_workflow.add_argument("--file", required=True, help="YAML 文件路径")
    config_set_workflow.set_defaults(func=cmd_config_set_workflow)
    config_lint = config_sub.add_parser(
        "lint",
        help="校验 config_defaults 的 YAML 结构和 workflow 引用是否正确",
    )
    config_lint.set_defaults(func=cmd_config_lint)

    package_parser = subparsers.add_parser(
        "package",
        help="安装包操作：构建或校验单根目录 ZIP 模块安装包",
    )
    package_sub = package_parser.add_subparsers(dest="action")
    package_build = package_sub.add_parser(
        "build",
        help="构建正式安装 ZIP；会先执行 release 级校验",
    )
    package_build.add_argument("--output", help="输出 ZIP 路径，默认 dist/<module>-<version>.zip")
    package_build.set_defaults(func=cmd_package_build)
    package_verify = package_sub.add_parser(
        "verify",
        help="校验已有 ZIP 是否符合模块安装包结构",
    )
    package_verify.add_argument("archive", help="待校验的 ZIP 文件")
    package_verify.set_defaults(func=cmd_package_verify)

    release_parser = subparsers.add_parser(
        "release",
        help="发布链路检查：看本地发布就绪状态，或对比远端 GitHub Release 版本",
    )
    release_sub = release_parser.add_subparsers(dest="action")
    release_status = release_sub.add_parser(
        "status",
        help="显示本地发布就绪状态，包括 repo、version、安装包和 release 校验结果",
    )
    release_status.set_defaults(func=cmd_release_status)
    release_remote = release_sub.add_parser(
        "check-remote",
        help="查询 GitHub Release 最新版本，并和本地 module.yaml.version 对比",
    )
    release_remote.add_argument(
        "--github-token",
        help="GitHub Token；不传则回退到 CRAWLER4J_GITHUB_TOKEN / GITHUB_TOKEN / GH_TOKEN",
    )
    release_remote.set_defaults(func=cmd_release_check_remote)
    release_publish = release_sub.add_parser(
        "publish",
        help="使用 GitHub CLI 把本地 ZIP 安装包发布到 GitHub Release",
    )
    release_publish.add_argument("--archive", help="待发布的 ZIP 路径，默认 dist/<module>-<version>.zip")
    release_publish.add_argument("--tag", help="Release tag，默认 v<version>")
    release_publish.add_argument("--title", help="Release 标题，默认与 tag 相同")
    release_publish.add_argument("--notes", help="Release notes 文本")
    release_publish.add_argument("--notes-file", help="Release notes 文件路径")
    release_publish.add_argument("--prerelease", action="store_true", help="以 prerelease 形式创建 Release")
    release_publish.add_argument("--rebuild", action="store_true", help="发布前强制重新构建 ZIP")
    release_publish.add_argument("--dry-run", action="store_true", help="只打印将要执行的 gh 命令")
    release_publish.set_defaults(func=cmd_release_publish)

    host_parser = subparsers.add_parser(
        "host",
        help="宿主桥接命令：通过 crawler4j-sdk CLI 操作宿主的 DevLink、安装、升级和调试配置",
    )
    host_sub = host_parser.add_subparsers(dest="action")

    host_devlink = host_sub.add_parser(
        "devlink",
        help="管理宿主侧 DevLink 模块注册",
    )
    host_devlink_sub = host_devlink.add_subparsers(dest="subaction")
    host_devlink_add = host_devlink_sub.add_parser(
        "add",
        help="把本地模块目录注册成宿主 DevLink",
    )
    host_devlink_add.add_argument("module_root", help="模块根目录路径")
    host_devlink_add.set_defaults(func=cmd_host_devlink_add)
    host_devlink_remove = host_devlink_sub.add_parser(
        "remove",
        help="移除宿主里的 DevLink 注册",
    )
    host_devlink_remove.add_argument("module_name", help="模块名")
    host_devlink_remove.set_defaults(func=cmd_host_devlink_remove)
    host_devlink_list = host_devlink_sub.add_parser(
        "list",
        help="列出宿主当前的 DevLink 模块",
    )
    host_devlink_list.set_defaults(func=cmd_host_devlink_list)

    host_install = host_sub.add_parser(
        "install",
        help="预览或执行宿主模块安装，来源可以是本地 ZIP 或 GitHub owner/repo",
    )
    host_install_sub = host_install.add_subparsers(dest="subaction")
    host_install_preview = host_install_sub.add_parser(
        "preview",
        help="只做安装预检，不实际安装",
    )
    host_install_preview.add_argument("source", help="ZIP 路径或 GitHub owner/repo")
    host_install_preview.add_argument(
        "--skip-remote-check",
        action="store_true",
        help="本地 ZIP 预览时跳过 upgrade_source.repo 的远端可达性校验",
    )
    host_install_preview.add_argument(
        "--github-token",
        help="GitHub Token；用于私有仓库安装或 ZIP 远端仓库校验",
    )
    host_install_preview.set_defaults(func=cmd_host_install_preview)
    host_install_apply = host_install_sub.add_parser(
        "apply",
        help="执行安装",
    )
    host_install_apply.add_argument("source", help="ZIP 路径或 GitHub owner/repo")
    host_install_apply.add_argument(
        "--skip-remote-check",
        action="store_true",
        help="本地 ZIP 安装时跳过 upgrade_source.repo 的远端可达性校验",
    )
    host_install_apply.add_argument(
        "--github-token",
        help="GitHub Token；用于私有仓库安装或 ZIP 远端仓库校验",
    )
    host_install_apply.set_defaults(func=cmd_host_install_apply)

    host_upgrade = host_sub.add_parser(
        "upgrade",
        help="检查、预览或执行正式安装模块的 GitHub Release 升级",
    )
    host_upgrade_sub = host_upgrade.add_subparsers(dest="subaction")
    host_upgrade_check = host_upgrade_sub.add_parser(
        "check",
        help="检查已安装模块是否有新版本",
    )
    host_upgrade_check.add_argument("module_name", help="已安装模块名")
    host_upgrade_check.add_argument(
        "--github-token",
        help="GitHub Token；不传则回退到环境变量",
    )
    host_upgrade_check.set_defaults(func=cmd_host_upgrade_check)
    host_upgrade_preview = host_upgrade_sub.add_parser(
        "preview",
        help="下载并预览升级包，但不安装",
    )
    host_upgrade_preview.add_argument("module_name", help="已安装模块名")
    host_upgrade_preview.add_argument(
        "--github-token",
        help="GitHub Token；不传则回退到环境变量",
    )
    host_upgrade_preview.set_defaults(func=cmd_host_upgrade_preview)
    host_upgrade_apply = host_upgrade_sub.add_parser(
        "apply",
        help="下载并安装升级包",
    )
    host_upgrade_apply.add_argument("module_name", help="已安装模块名")
    host_upgrade_apply.add_argument(
        "--github-token",
        help="GitHub Token；不传则回退到环境变量",
    )
    host_upgrade_apply.set_defaults(func=cmd_host_upgrade_apply)

    host_debug = host_sub.add_parser(
        "debug",
        help="生成宿主调试配置。当前 CLI 只负责 VS Code attach 配置，不直接托管调试会话生命周期",
    )
    host_debug_sub = host_debug.add_subparsers(dest="subaction")
    host_debug_config = host_debug_sub.add_parser(
        "config",
        help="为模块目录生成或更新 .vscode/launch.json 的 debugpy attach 配置",
    )
    host_debug_config.add_argument("--module-root", help="模块根目录，默认使用当前模块目录")
    host_debug_config.add_argument("--host", default="127.0.0.1", help="debugpy 监听地址")
    host_debug_config.add_argument("--port", type=int, default=5678, help="debugpy 监听端口")
    host_debug_config.add_argument(
        "--configuration-name",
        default="Attach to Crawler4j",
        help="VS Code 配置名称",
    )
    host_debug_config.set_defaults(func=cmd_host_debug_config)

    check_parser = subparsers.add_parser(
        "check",
        help="模块完整性校验：structure 只看骨架，release 看发布前提，full 再做导入校验",
    )
    check_sub = check_parser.add_subparsers(dest="level")
    check_structure = check_sub.add_parser(
        "structure",
        help="检查 module.yaml、module_runtime.py、目录结构、workflow 声明和 UI 入口格式",
    )
    check_structure.set_defaults(func=cmd_check_structure)
    check_release = check_sub.add_parser(
        "release",
        help="在 structure 基础上继续检查 version、upgrade_source.repo、config_defaults 等发布前提",
    )
    check_release.set_defaults(func=cmd_check_release)
    check_full = check_sub.add_parser(
        "full",
        help="在 release 基础上再尝试导入模块、任务、工作流并校验 hosted UI 声明，作为完整 gate",
    )
    check_full.set_defaults(func=cmd_check_full)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the crawler4j CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "group", None):
        parser.print_help()
        return 0
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    try:
        return int(args.func(args))
    except CLIError as exc:
        _print_error(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())

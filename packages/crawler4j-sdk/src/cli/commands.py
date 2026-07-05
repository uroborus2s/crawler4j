"""CLI commands for crawler4j SDK module projects."""

from __future__ import annotations

import argparse
import ast
import asyncio
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from crawler4j_sdk._version import (
    get_compatible_contracts_dependency_spec,
    get_compatible_sdk_dependency_spec,
)
from crawler4j_sdk.cli.templates import (
    COMPONENT_TEMPLATE,
    DATA_TABLE_TEMPLATE,
    DATA_VIEW_TEMPLATE,
    ENV_CLEANUP_CANDIDATES_TEMPLATE,
    ENV_CANDIDATES_TEMPLATE,
    INTERFACE_TEMPLATE,
    MODEL_GITIGNORE_TEMPLATE,
    MODEL_CANDIDATES_INIT_TEMPLATE,
    MODEL_CLEANUPS_INIT_TEMPLATE,
    MODEL_DATA_INIT_TEMPLATE,
    MODEL_INTERFACES_INIT_TEMPLATE,
    MODEL_MANIFEST_TEMPLATE,
    MODEL_MODULE_INIT,
    MODEL_OBJECTS_INIT_TEMPLATE,
    MODEL_PAGES_INIT_TEMPLATE,
    MODEL_PROJECT_PYPROJECT,
    MODEL_PROJECT_README,
    MODEL_TASKS_INIT_TEMPLATE,
    MODEL_TEST_TASK_TEMPLATE,
    MODEL_WORKFLOWS_INIT_TEMPLATE,
    SCRIPT_TEMPLATE,
    UI_ACTION_TEMPLATE,
    WORKFLOW_TEMPLATE,
    render_page_template,
)
from crawler4j_sdk.v2_scanner import CORE_NATIVE_V2_RUNTIME_API, V2_SCAN_DIRECTORIES, scan_v2_module


DEFAULT_PYTHON_VERSION = "3.12"
DEFAULT_MODULE_VERSION = "0.1.0"
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
DATA_TABLE_STORAGE_MODES = {"managed_dataset", "custom_table"}
WORKFLOW_HOST_SCENARIOS = {"existing_env_import"}
SEMVER_RE = re.compile(
    r"^v?"
    r"(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+(?P<build>[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
GITHUB_TOKEN_ENV_VARS = ("CRAWLER4J_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")
LEGACY_HOSTED_UI_PATHS: tuple[tuple[str, str], ...] = (
    ("ui", "dir"),
    ("config_schema.json", "file"),
    ("strategy.yaml", "file"),
)
REQUIRED_RUNTIME_API = CORE_NATIVE_V2_RUNTIME_API
MAX_ZIP_ENTRIES = 10_000
MAX_ZIP_UNCOMPRESSED_BYTES = 256 * 1024 * 1024
IGNORED_MODULE_DIRS = frozenset(
    {
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
)
IGNORED_MODULE_FILES = frozenset({".DS_Store"})


class CLIError(RuntimeError):
    """Raised when a CLI action cannot be completed safely."""


def _is_ignored_module_path(relative: Path, ignored_dirs: frozenset[str] = IGNORED_MODULE_DIRS) -> bool:
    return any(part in ignored_dirs or part.endswith(".egg-info") for part in relative.parts)


class _UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_mapping_without_duplicate_keys(loader, node, deep=False):
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            mark = getattr(key_node, "start_mark", None)
            location = f" line {mark.line + 1}, column {mark.column + 1}" if mark is not None else ""
            raise CLIError(f"YAML contains duplicate key: {key}{location}")
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_without_duplicate_keys,
)


def to_display_name(name: str) -> str:
    """Convert an identifier to a readable title."""
    return name.replace("_", " ").replace("-", " ").title()


def to_class_name(name: str) -> str:
    """Convert a snake_case identifier to PascalCase."""
    return "".join(part.capitalize() for part in re.split(r"[_-]+", str(name or "")) if part)


def _workflow_host_scenarios_arg(scenarios: list[str] | tuple[str, ...] | None) -> str:
    normalized: list[str] = []
    for scenario in scenarios or []:
        value = str(scenario or "").strip()
        if not value:
            continue
        if value not in WORKFLOW_HOST_SCENARIOS:
            raise CLIError(f"不支持的 workflow host scenario: {value}")
        if value not in normalized:
            normalized.append(value)
    if not normalized:
        return ""
    rendered = ", ".join(f'"{item}"' for item in normalized)
    return f", host_scenarios=[{rendered}]"


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
    data = yaml.load(manifest_path.read_text(encoding="utf-8"), Loader=_UniqueKeySafeLoader) or {}
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


def _module_display_name(module_root: Path, manifest: dict[str, Any]) -> str:
    """Resolve the human-facing module display name."""
    display_name = str(manifest.get("display_name", "") or "").strip()
    if display_name:
        return display_name
    module_name = str(manifest.get("name", "") or "").strip() or module_root.name
    return to_display_name(module_name)


def _resolve_module_import_name(module_root: Path, manifest: dict[str, Any] | None = None) -> str:
    module_name = str((manifest or {}).get("name", "") or "").strip()
    if module_name:
        return module_name
    return module_root.name


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


def _list_python_modules(package_dir: Path, *, recursive: bool = False) -> list[str]:
    if not package_dir.exists():
        return []
    paths = package_dir.rglob("*.py") if recursive else package_dir.glob("*.py")
    return sorted(
        ".".join(path.relative_to(package_dir).with_suffix("").parts)
        for path in paths
        if path.name != "__init__.py"
        and not path.name.startswith("_")
        and not any(part.startswith("_") for part in path.relative_to(package_dir).parts[:-1])
    )


def _page_owner_label(page_module_name: str) -> str:
    return f"pages/{page_module_name.replace('.', '/')}.py"


def _normalize_page_group(group: str | None) -> str:
    normalized_group = str(group or "").strip()
    if not normalized_group:
        return ""
    if "/" in normalized_group or "\\" in normalized_group or "." in normalized_group:
        raise CLIError("页面分组名必须是单层小写 snake_case")
    if not is_valid_name(normalized_group):
        raise CLIError("页面分组名必须是单层小写 snake_case")
    return normalized_group


def _page_source_relative_path(page_id: str, *, group: str | None = None) -> Path:
    normalized_page_id = str(page_id or "").strip()
    normalized_group = _normalize_page_group(group)
    if not normalized_group:
        return Path("pages") / f"{normalized_page_id}.py"

    prefix = f"{normalized_group}_"
    file_stem = normalized_page_id
    if normalized_page_id.startswith(prefix):
        candidate = normalized_page_id[len(prefix) :].strip()
        if candidate:
            file_stem = candidate
    return Path("pages") / normalized_group / f"{file_stem}.py"


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    payload = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeySafeLoader)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise CLIError(f"YAML 文件必须是映射对象: {path}")
    return payload


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


def _v2_scan(module_root: Path, manifest: dict[str, Any]):
    return scan_v2_module(module_root, manifest)


def _v2_declaration_names(module_root: Path, manifest: dict[str, Any], kind: str) -> list[str]:
    result = _v2_scan(module_root, manifest)
    return sorted(declaration.name for declaration in result.declarations if declaration.kind == kind)


def _manifest_lock_payload(module_root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    result = _v2_scan(module_root, manifest)
    declarations = [
        {
            "kind": declaration.kind,
            "name": declaration.name,
            "symbol": declaration.symbol,
            "source_path": declaration.source_path,
            "metadata": asdict(declaration.meta),
        }
        for declaration in sorted(
            result.declarations,
            key=lambda item: (item.kind, item.name, item.source_path, item.symbol),
        )
    ]
    return {
        "schema_version": 1,
        "runtime_api": CORE_NATIVE_V2_RUNTIME_API,
        "module": str(manifest.get("name", "") or module_root.name).strip(),
        "version": str(manifest.get("version", "") or "").strip(),
        "declarations": declarations,
    }


def _collect_manifest_lock_errors(module_root: Path, manifest: dict[str, Any]) -> list[str]:
    lock_path = module_root / ".crawler4j" / "manifest.lock.json"
    if not lock_path.exists():
        return ["缺少 manifest lock: .crawler4j/manifest.lock.json，请运行 `crawler4j manifest lock`"]
    try:
        actual = json.loads(lock_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"manifest lock 不是合法 JSON: {exc}"]

    try:
        expected = json.loads(
            json.dumps(
                _manifest_lock_payload(module_root, manifest),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    except CLIError as exc:
        return [str(exc)]
    if actual != expected:
        return ["manifest lock 已过期，请运行 `crawler4j manifest lock` 更新 .crawler4j/manifest.lock.json"]
    return []


def _write_manifest_lock(module_root: Path, manifest: dict[str, Any]) -> Path:
    lock_dir = module_root / ".crawler4j"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / "manifest.lock.json"
    lock_path.write_text(
        json.dumps(_manifest_lock_payload(module_root, manifest), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return lock_path


def _safe_run(cmd: list[str], *, cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True)


def _run_async(awaitable):
    return asyncio.run(awaitable)


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
        raise CLIError("当前环境缺少 crawler4j 宿主运行时；host 命令只能在安装了 crawler4j 客户端的环境里使用") from exc

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


def _collect_legacy_hosted_ui_errors(module_root: Path) -> list[str]:
    errors: list[str] = []
    for relative_path, expected_kind in LEGACY_HOSTED_UI_PATHS:
        candidate = module_root / relative_path
        if not candidate.exists():
            continue
        if expected_kind == "dir":
            if candidate.is_dir():
                errors.append(f"残留旧 UI 目录: {relative_path}/")
            else:
                errors.append(f"残留旧 UI 路径: {relative_path}")
            continue
        if candidate.is_file():
            errors.append(f"残留旧 UI 文件: {relative_path}")
        else:
            errors.append(f"残留旧 UI 路径: {relative_path}")
    return errors


def collect_structure_errors(module_root: Path, manifest: dict[str, Any]) -> list[str]:
    """Collect structure-level validation errors."""
    errors: list[str] = []

    required_files = ["module.yaml", "__init__.py"]
    required_dirs = ["interfaces", "objects", "workflows", "tasks", "data", "pages", "candidates"]
    for name in required_files:
        if not (module_root / name).exists():
            errors.append(f"缺少关键文件: {name}")
    for name in required_dirs:
        if not (module_root / name).is_dir():
            errors.append(f"缺少关键目录: {name}/")

    if not str(manifest.get("name", "")).strip():
        errors.append("module.yaml 缺少 name")
    if str(manifest.get("runtime_api", "")).strip() != REQUIRED_RUNTIME_API:
        errors.append(f"module.yaml.runtime_api 必须是 {REQUIRED_RUNTIME_API}")
    if (module_root / "module_runtime.py").exists():
        errors.append("core-native-v2 模块不允许保留旧运行时薄壳: module_runtime.py")
    for key in (
        "sdk_version_range",
        "default_workflow",
        "workflows",
        "data",
        "interfaces",
        "objects",
        "tasks",
        "ui_extension",
        "resource_pools",
    ):
        if key in manifest:
            errors.append(f"module.yaml 不再允许声明 {key}；请使用 core-native-v2 装饰器")
    errors.extend(_collect_legacy_hosted_ui_errors(module_root))
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
        workflow_defaults = config_defaults.get("workflows", {})
        if workflow_defaults:
            errors.append("core-native-v2 不再支持 config_defaults.workflows；对象参数应保存在运行模板")
    except CLIError as exc:
        errors.append(str(exc))

    pyproject_path = module_root / "pyproject.toml"
    if pyproject_path.exists():
        try:
            project_version = _load_project_version(pyproject_path)
        except CLIError as exc:
            errors.append(str(exc))
        else:
            if project_version != version:
                errors.append(
                    f"pyproject.toml [project].version 必须与 module.yaml.version 一致: {project_version} != {version}"
                )

    module_name = str(manifest.get("name", "")).strip()
    if module_name and not is_valid_name(module_name):
        errors.append("module.yaml.name 必须是可导入的 snake_case 包名")
    return errors


def collect_full_errors(
    module_root: Path,
    manifest: dict[str, Any],
    *,
    require_manifest_lock: bool = False,
) -> list[str]:
    """Collect importability and runtime-level validation errors."""
    errors = collect_release_errors(module_root, manifest)
    errors.extend(scan_v2_module(module_root, manifest).error_messages())
    errors.extend(_collect_legacy_db_tool_usage_errors(module_root, v2_runtime=True))
    errors.extend(_collect_removed_task_context_usage_errors(module_root, v2_runtime=True))
    if require_manifest_lock and not errors:
        errors.extend(_collect_manifest_lock_errors(module_root, manifest))
    return errors


def _iter_module_python_trees(module_root: Path, *, v2_runtime: bool = False):
    if v2_runtime:
        paths: list[Path] = []
        root_init = module_root / "__init__.py"
        if root_init.exists():
            paths.append(root_init)
        for directory_name in V2_SCAN_DIRECTORIES:
            directory = module_root / directory_name
            if directory.exists():
                paths.extend(path for path in directory.rglob("*.py") if path.name != "__init__.py")
    else:
        paths = list(module_root.rglob("*.py"))

    for path in sorted(paths):
        relative = path.relative_to(module_root)
        if any(part in {".venv", "__pycache__", ".pytest_cache", ".ruff_cache"} for part in relative.parts):
            continue
        text = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError:
            continue
        yield relative, tree


def _collect_legacy_db_tool_usage_errors(module_root: Path, *, v2_runtime: bool = False) -> list[str]:
    errors: list[str] = []
    for relative, tree in _iter_module_python_trees(module_root, v2_runtime=v2_runtime):
        legacy_calls = sorted(_collect_legacy_db_tool_call_lines(tree), key=int)
        errors.extend(
            f"{relative}:{line_no} 使用了已删除的旧数据库工具入口；请改用 ctx.db fluent API" for line_no in legacy_calls
        )
    return errors


def _collect_legacy_db_tool_call_lines(tree: ast.AST) -> list[int]:
    visitor = _LegacyDbToolUsageVisitor()
    visitor.visit(tree)
    return visitor.lines


class _LegacyDbToolUsageVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.lines: list[int] = []
        self._tool_alias_scopes: list[set[str]] = [set()]

    @property
    def _aliases(self) -> set[str]:
        return self._tool_alias_scopes[-1]

    def _push_scope(self, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda | ast.ClassDef) -> None:
        aliases = set(self._aliases)
        for name in _bound_argument_names(node):
            aliases.discard(name)
        self._tool_alias_scopes.append(aliases)

    def _pop_scope(self) -> None:
        self._tool_alias_scopes.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._push_scope(node)
        self.generic_visit(node)
        self._pop_scope()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._push_scope(node)
        self.generic_visit(node)
        self._pop_scope()

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._push_scope(node)
        self.generic_visit(node)
        self._pop_scope()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._push_scope(node)
        self.generic_visit(node)
        self._pop_scope()

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        is_tools_alias = _is_tools_reference(node.value, self._aliases)
        for target in node.targets:
            self._update_alias_target(target, is_tools_alias=is_tools_alias)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)
        is_tools_alias = node.value is not None and _is_tools_reference(node.value, self._aliases)
        self._update_alias_target(node.target, is_tools_alias=is_tools_alias)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self.visit(node.value)
        self._update_alias_target(
            node.target,
            is_tools_alias=_is_tools_reference(node.value, self._aliases),
        )

    def visit_Call(self, node: ast.Call) -> None:
        if _is_legacy_db_tool_call(node, self._aliases):
            self.lines.append(node.args[0].lineno)
        self.generic_visit(node)

    def _update_alias_target(self, target: ast.AST, *, is_tools_alias: bool) -> None:
        if isinstance(target, ast.Name):
            if is_tools_alias:
                self._aliases.add(target.id)
            else:
                self._aliases.discard(target.id)
            return
        if isinstance(target, ast.Starred):
            self._update_alias_target(target.value, is_tools_alias=False)
            return
        if isinstance(target, ast.Tuple | ast.List):
            for item in target.elts:
                self._update_alias_target(item, is_tools_alias=False)


def _bound_argument_names(node: ast.AST) -> set[str]:
    args = getattr(node, "args", None)
    if not isinstance(args, ast.arguments):
        return set()
    bound: set[str] = set()
    for arg in [*args.posonlyargs, *args.args, *args.kwonlyargs]:
        bound.add(arg.arg)
    if args.vararg:
        bound.add(args.vararg.arg)
    if args.kwarg:
        bound.add(args.kwarg.arg)
    return bound


def _is_tools_reference(node: ast.AST, aliases: set[str]) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "tools") or (
        isinstance(node, ast.Name) and node.id in aliases
    )


def _is_legacy_db_tool_call(node: ast.AST, aliases: set[str] | None = None) -> bool:
    tool_aliases = aliases or set()
    if not isinstance(node, ast.Call):
        return False
    if not isinstance(node.func, ast.Attribute) or node.func.attr not in {"call", "has_tool"}:
        return False
    if not _is_tools_reference(node.func.value, tool_aliases):
        return False
    if not node.args:
        return False
    first_arg = node.args[0]
    return (
        isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str) and first_arg.value.startswith("db.")
    )


def _collect_removed_task_context_usage_errors(module_root: Path, *, v2_runtime: bool = False) -> list[str]:
    errors: list[str] = []
    for relative, tree in _iter_module_python_trees(module_root, v2_runtime=v2_runtime):
        captured_data_accesses = sorted(
            (node.lineno for node in ast.walk(tree) if _is_removed_captured_data_access(node)),
            key=int,
        )
        errors.extend(
            f"{relative}:{line_no} 使用了已删除的 ctx.captured_data；临时状态请用 ctx.state，任务输出请返回 TaskResult.data"
            for line_no in captured_data_accesses
        )
    return errors


def _is_removed_captured_data_access(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "captured_data"


def cmd_data_list(args: argparse.Namespace) -> int:
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    print("tables: " + (", ".join(_v2_declaration_names(module_root, manifest, "data_table")) or "(无)"))
    print("views: " + (", ".join(_v2_declaration_names(module_root, manifest, "data_view")) or "(无)"))
    return 0


def cmd_data_table_create(args: argparse.Namespace) -> int:
    module_root = require_module_root()
    name = str(args.name or "").strip()
    if not is_valid_name(name):
        _print_error("数据表名必须是小写 snake_case")
        return 1
    storage_mode = str(getattr(args, "storage_mode", "custom_table") or "custom_table").strip().lower()
    if storage_mode not in DATA_TABLE_STORAGE_MODES:
        _print_error("storage_mode 只支持 managed_dataset/custom_table")
        return 1
    try:
        _write_text(
            module_root / "data" / f"{name}.py",
            DATA_TABLE_TEMPLATE.format(
                name=name,
                class_name=to_class_name(name),
                display_name=args.display_name or to_display_name(name),
                description=args.description or f"{to_display_name(name)} 数据表",
                storage_mode=storage_mode,
            ),
            force=args.force,
        )
    except CLIError as exc:
        _print_error(str(exc))
        return 1
    _print_success(f"已创建数据表声明: data/{name}.py")
    return 0


def cmd_data_view_create(args: argparse.Namespace) -> int:
    module_root = require_module_root()
    view_id = str(args.name or "").strip()
    if not is_valid_name(view_id):
        _print_error("视图名必须是小写 snake_case")
        return 1
    raw_source = args.source[0] if isinstance(args.source, list) else args.source
    source = str(raw_source or "").strip()
    if not is_valid_name(source):
        _print_error("--source 必须是已声明数据表名，且必须是小写 snake_case")
        return 1
    manifest = load_manifest(module_root)
    if source not in _v2_declaration_names(module_root, manifest, "data_table"):
        _print_error(f"未找到数据表声明: {source}")
        return 1
    try:
        _write_text(
            module_root / "data" / f"{view_id}.py",
            DATA_VIEW_TEMPLATE.format(
                name=view_id,
                source=source,
                display_name=args.display_name or to_display_name(view_id),
                description=args.description or f"{to_display_name(view_id)} 只读视图",
            ),
            force=args.force,
        )
    except CLIError as exc:
        _print_error(str(exc))
        return 1

    _print_success(f"已创建只读视图声明: data/{view_id}.py")
    return 0


def _run_check(level: str, module_root: Path) -> int:
    manifest = load_manifest(module_root)
    if level == "structure":
        errors = collect_structure_errors(module_root, manifest)
    elif level == "release":
        errors = collect_release_errors(module_root, manifest)
    elif level == "full":
        errors = collect_full_errors(module_root, manifest, require_manifest_lock=True)
    else:  # pragma: no cover - parser guards this
        raise CLIError(f"未知校验级别: {level}")

    if errors:
        _print_error(f"{level} 校验失败")
        for item in errors:
            print(f"  - {item}")
        return 1

    _print_success(f"{level} 校验通过")
    return 0


def _archive_members(module_root: Path, archive_root: str) -> list[tuple[Path, str]]:
    root = module_root.resolve()
    members: list[tuple[Path, str]] = []
    for path in module_root.rglob("*"):
        relative = path.relative_to(module_root)
        if _is_ignored_module_path(relative):
            continue
        if path.is_symlink():
            raise CLIError(f"模块文件不能是符号链接: {relative.as_posix()}")
        if path.is_dir():
            continue
        if path.name in IGNORED_MODULE_FILES:
            continue
        if path.suffix in {".pyc", ".pyo"}:
            continue
        try:
            path.resolve().relative_to(root)
        except ValueError as exc:
            raise CLIError(f"模块文件路径越界: {relative.as_posix()}") from exc
        arcname = f"{archive_root}/{relative.as_posix()}"
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


def _validate_zip_member(info: zipfile.ZipInfo, *, seen: set[str]) -> str:
    name = info.filename
    if not name or name.startswith("__MACOSX/"):
        return ""
    if "\\" in name:
        raise CLIError(f"ZIP 包含非法反斜杠路径: {name}")
    pure = PurePosixPath(name)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise CLIError(f"ZIP 包含非法路径: {name}")
    normalized = pure.as_posix()
    if normalized in seen:
        raise CLIError(f"ZIP 包含重复路径: {normalized}")
    seen.add(normalized)
    mode = info.external_attr >> 16
    if stat.S_ISLNK(mode):
        raise CLIError(f"ZIP 包含不允许的符号链接: {normalized}")
    return normalized


def _safe_extract_zip(zf: zipfile.ZipFile, target_dir: Path) -> None:
    infos = zf.infolist()
    if len(infos) > MAX_ZIP_ENTRIES:
        raise CLIError(f"ZIP 条目过多: {len(infos)} > {MAX_ZIP_ENTRIES}")
    seen: set[str] = set()
    total_size = 0
    root = target_dir.resolve()
    for info in infos:
        normalized = _validate_zip_member(info, seen=seen)
        if not normalized:
            continue
        total_size += int(info.file_size)
        if total_size > MAX_ZIP_UNCOMPRESSED_BYTES:
            raise CLIError("ZIP 解压后体积超过限制")
        destination = (root / normalized).resolve()
        try:
            destination.relative_to(root)
        except ValueError as exc:
            raise CLIError(f"ZIP 解压路径越界: {normalized}") from exc
        if info.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info, "r") as source, destination.open("wb") as target:
            shutil.copyfileobj(source, target)


def _extract_archive_to_temp(archive_path: Path) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="crawler4j_sdk_verify_"))
    with zipfile.ZipFile(archive_path, "r") as zf:
        _safe_extract_zip(zf, temp_dir)
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


def _prompt_required_value(
    prompt: str,
    *,
    validator,
    invalid_message: str,
) -> str:
    while True:
        try:
            value = input(f"{prompt}: ").strip()
        except EOFError as exc:
            raise CLIError(
                f"缺少必填参数: {prompt}。可在交互式终端运行 `crawler4j module init`，"
                "或一次性传入 `crawler4j module init <name> --repo owner/repo`。"
            ) from exc
        if not value:
            _print_error(f"{prompt} 是必填项")
            continue
        if not validator(value):
            _print_error(invalid_message)
            continue
        return value


def _resolve_module_init_args(args: argparse.Namespace) -> tuple[str, str]:
    module_name = str(getattr(args, "name", "") or "").strip()
    if not module_name:
        module_name = _prompt_required_value(
            "模块包名（snake_case）",
            validator=is_valid_name,
            invalid_message="模块名必须是小写 snake_case，并且能作为 Python 包名导入",
        )

    repo = str(getattr(args, "repo", "") or "").strip()
    if not repo:
        repo = _prompt_required_value(
            "升级源 GitHub 仓库（owner/repo）",
            validator=is_valid_repo,
            invalid_message="仓库必须是 owner/repo 形式",
        )

    runtime_api = str(getattr(args, "runtime_api", None) or CORE_NATIVE_V2_RUNTIME_API).strip()
    if runtime_api != CORE_NATIVE_V2_RUNTIME_API:
        raise CLIError(f"--runtime-api 只支持 {CORE_NATIVE_V2_RUNTIME_API}")

    args.name = module_name
    args.repo = repo
    args.runtime_api = runtime_api
    args.version = str(getattr(args, "version", None) or DEFAULT_MODULE_VERSION).strip()
    args.workflow_name = str(getattr(args, "workflow_name", None) or "main_workflow").strip()
    args.python_version = str(getattr(args, "python_version", None) or DEFAULT_PYTHON_VERSION).strip()
    return module_name, repo


def cmd_module_init(args: argparse.Namespace) -> int:
    """Initialize a new module project."""
    try:
        module_name, repo = _resolve_module_init_args(args)
    except CLIError as exc:
        _print_error(str(exc))
        return 1

    if not is_valid_name(module_name):
        _print_error("模块名必须是小写 snake_case，并且能作为 Python 包名导入")
        return 1
    if not is_valid_repo(repo):
        _print_error("`--repo` 必须是 owner/repo 形式")
        return 1
    if not is_valid_name(args.workflow_name):
        _print_error("初始工作流名必须是小写 snake_case")
        return 1
    if not is_valid_semver(args.version):
        _print_error("模块版本必须是合法语义化版本号")
        return 1

    output_dir = Path(args.output).expanduser().resolve() if args.output else Path.cwd() / module_name
    if output_dir.exists() and not output_dir.is_dir():
        _print_error(f"目标路径不是目录: {output_dir}")
        return 1
    if output_dir.exists() and any(output_dir.iterdir()) and not args.force:
        _print_error(f"目标目录已存在且非空: {output_dir}")
        return 1

    display_name = args.display_name or to_display_name(module_name)
    description = args.description or f"{display_name} 模块"
    workflow_display_name = args.workflow_display_name or to_display_name(args.workflow_name)
    workflow_description = args.workflow_description or f"{workflow_display_name} 工作流"
    contracts_dependency_spec = get_compatible_contracts_dependency_spec()
    sdk_dependency_spec = get_compatible_sdk_dependency_spec()

    output_dir.mkdir(parents=True, exist_ok=True)
    for subdir in [
        ".crawler4j",
        "interfaces",
        "objects",
        "tasks",
        "workflows",
        "pages",
        "candidates",
        "cleanups",
        "tests",
        "data",
    ]:
        (output_dir / subdir).mkdir(parents=True, exist_ok=True)

    try:
        _write_text(
            output_dir / "pyproject.toml",
            MODEL_PROJECT_PYPROJECT.format(
                project_name=module_name,
                version=args.version,
                display_name=display_name,
                python_version=args.python_version,
                contracts_dependency_spec=contracts_dependency_spec,
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
            output_dir / "tasks" / "__init__.py",
            MODEL_TASKS_INIT_TEMPLATE,
            force=args.force,
        )
        _write_text(
            output_dir / "workflows" / "__init__.py",
            MODEL_WORKFLOWS_INIT_TEMPLATE,
            force=args.force,
        )
        _write_text(
            output_dir / "interfaces" / "__init__.py",
            MODEL_INTERFACES_INIT_TEMPLATE,
            force=args.force,
        )
        _write_text(
            output_dir / "objects" / "__init__.py",
            MODEL_OBJECTS_INIT_TEMPLATE,
            force=args.force,
        )
        _write_text(
            output_dir / "data" / "__init__.py",
            MODEL_DATA_INIT_TEMPLATE,
            force=args.force,
        )
        _write_text(
            output_dir / "pages" / "__init__.py",
            MODEL_PAGES_INIT_TEMPLATE,
            force=args.force,
        )
        _write_text(
            output_dir / "candidates" / "__init__.py",
            MODEL_CANDIDATES_INIT_TEMPLATE,
            force=args.force,
        )
        _write_text(
            output_dir / "cleanups" / "__init__.py",
            MODEL_CLEANUPS_INIT_TEMPLATE,
            force=args.force,
        )
        _write_text(
            output_dir / "interfaces" / "labor.py",
            INTERFACE_TEMPLATE.format(
                name="labor",
                class_name="Labor",
                display_name="示例能力",
                description="示例可注入能力接口",
            ),
            force=args.force,
        )
        _write_text(
            output_dir / "objects" / "api_labor.py",
            COMPONENT_TEMPLATE.format(
                name="api_labor",
                implements="labor",
                class_name="ApiLabor",
                display_name="示例能力实现",
                description="示例可注入组件实现",
            ),
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
            output_dir / "data" / "accounts.py",
            DATA_TABLE_TEMPLATE.format(
                name="accounts",
                class_name="Accounts",
                display_name="示例账号",
                description="示例账号数据表",
                storage_mode="custom_table",
            ),
            force=args.force,
        )
        _write_text(
            output_dir / "data" / "account_overview.py",
            DATA_VIEW_TEMPLATE.format(
                name="account_overview",
                source="accounts",
                display_name="账号概览",
                description="示例账号只读视图",
            ),
            force=args.force,
        )
        _write_text(
            output_dir / "candidates" / "ready_accounts.py",
            ENV_CANDIDATES_TEMPLATE.format(
                name="ready_accounts",
                display_name="可用账号候选",
                description="示例环境候选函数",
            ),
            force=args.force,
        )
        _write_text(
            output_dir / "tasks" / "example_action.py",
            SCRIPT_TEMPLATE.format(
                name="example_action",
                display_name="示例页面操作",
                description="示例页面操作函数",
            ),
            force=args.force,
        )
        _write_text(
            output_dir / "workflows" / f"{args.workflow_name}.py",
            WORKFLOW_TEMPLATE.format(
                name=args.workflow_name,
                class_name=to_class_name(args.workflow_name),
                display_name=workflow_display_name,
                description=workflow_description,
                host_scenarios_arg="",
            ),
            force=args.force,
        )
        _write_text(output_dir / "tests" / "test_tasks.py", MODEL_TEST_TASK_TEMPLATE, force=args.force)
        _write_text(output_dir / "tests" / "__init__.py", "", force=args.force)
        _write_text(output_dir / ".gitignore", MODEL_GITIGNORE_TEMPLATE, force=args.force)
        _write_text(output_dir / ".python-version", f"{args.python_version}\n", force=args.force)
        _write_manifest_lock(output_dir, load_manifest(output_dir))
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
    print("  - 新建接口: `crawler4j interface create <name>`")
    print("  - 新建组件: `crawler4j component create <name> --implements <interface>`")
    print("  - 新建工作流: `crawler4j workflow create <name>`")
    print("  - 新建页面操作: `crawler4j page-action create <name>`")
    print("  - 新建页面: `crawler4j page create <page_id>`")
    print("  - 新建数据表: `crawler4j data table create <name>`")
    print("  - 新建只读视图: `crawler4j data view create <name> --source <data_table>`")
    print("  - 新建环境候选函数: `crawler4j candidate create <name>`")
    print("  - 新建环境清理候选函数: `crawler4j cleanup create <name>`")
    print("  - 更新 lock: `crawler4j manifest lock`")
    print("  - 完整校验: `crawler4j check full`")
    return 0


def cmd_module_show(args: argparse.Namespace) -> int:
    """Show the current module summary."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    result = _v2_scan(module_root, manifest)
    declarations_by_kind: dict[str, list[str]] = {}
    for declaration in result.declarations:
        declarations_by_kind.setdefault(declaration.kind, []).append(declaration.name)

    print(f"模块目录: {module_root}")
    print(f"模块名: {manifest.get('name', '')}")
    print(f"运行时协议: {manifest.get('runtime_api', '')}")
    print(f"版本: {manifest.get('version', '')}")
    print(f"仓库: {(manifest.get('upgrade_source') or {}).get('repo', '')}")
    print(f"接口: {', '.join(sorted(declarations_by_kind.get('interface', []))) or '(无)'}")
    print(f"组件: {', '.join(sorted(declarations_by_kind.get('component', []))) or '(无)'}")
    print(f"工作流: {', '.join(sorted(declarations_by_kind.get('workflow', []))) or '(无)'}")
    print(f"宿主页: {', '.join(sorted(declarations_by_kind.get('page', []))) or '(无)'}")
    print(f"页面操作: {', '.join(sorted(declarations_by_kind.get('page_action', []))) or '(无)'}")
    print(f"UI 操作: {', '.join(sorted(declarations_by_kind.get('ui_action', []))) or '(无)'}")
    print(f"数据表: {len(declarations_by_kind.get('data_table', []))}")
    print(f"只读视图: {len(declarations_by_kind.get('data_view', []))}")
    print(f"环境候选: {', '.join(sorted(declarations_by_kind.get('env_candidates', []))) or '(无)'}")
    print(f"环境清理候选: {', '.join(sorted(declarations_by_kind.get('env_cleanup_candidates', []))) or '(无)'}")
    if result.diagnostics:
        print(f"诊断: {len(result.diagnostics)}")
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


def cmd_module_repair_init(args: argparse.Namespace) -> int:
    """Rebuild the module root __init__.py from the current standard template."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    try:
        _write_text(
            module_root / "__init__.py",
            MODEL_MODULE_INIT.format(display_name=_module_display_name(module_root, manifest)),
            force=True,
        )
    except CLIError as exc:
        _print_error(str(exc))
        return 1
    _print_success("已重建模块根包文件: __init__.py")
    return 0


def cmd_interface_create(args: argparse.Namespace) -> int:
    """Create a core-native-v2 interface declaration."""
    module_root = require_module_root()
    name = str(args.name or "").strip()
    if not is_valid_name(name):
        _print_error("接口名必须是小写 snake_case")
        return 1
    try:
        _write_text(
            module_root / "interfaces" / f"{name}.py",
            INTERFACE_TEMPLATE.format(
                name=name,
                class_name=to_class_name(name),
                display_name=args.display_name or to_display_name(name),
                description=args.description or f"{to_display_name(name)} 接口",
            ),
            force=args.force,
        )
    except CLIError as exc:
        _print_error(str(exc))
        return 1
    _print_success(f"已创建接口声明: interfaces/{name}.py")
    return 0


def cmd_interface_list(args: argparse.Namespace) -> int:
    """List core-native-v2 interface declarations."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    names = _v2_declaration_names(module_root, manifest, "interface")
    print("\n".join(names) if names else "(无接口)")
    return 0


def cmd_component_create(args: argparse.Namespace) -> int:
    """Create a core-native-v2 component declaration."""
    module_root = require_module_root()
    name = str(args.name or "").strip()
    implements = str(args.implements or "").strip()
    if not is_valid_name(name):
        _print_error("组件名必须是小写 snake_case")
        return 1
    if not is_valid_name(implements):
        _print_error("--implements 必须是已声明接口名，且必须是小写 snake_case")
        return 1
    manifest = load_manifest(module_root)
    if implements not in _v2_declaration_names(module_root, manifest, "interface"):
        _print_error(f"未找到接口声明: {implements}")
        return 1
    try:
        _write_text(
            module_root / "objects" / f"{name}.py",
            COMPONENT_TEMPLATE.format(
                name=name,
                implements=implements,
                class_name=to_class_name(name),
                display_name=args.display_name or to_display_name(name),
                description=args.description or f"{to_display_name(name)} 组件",
            ),
            force=args.force,
        )
    except CLIError as exc:
        _print_error(str(exc))
        return 1
    _print_success(f"已创建组件声明: objects/{name}.py")
    return 0


def cmd_component_list(args: argparse.Namespace) -> int:
    """List core-native-v2 component declarations."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    names = _v2_declaration_names(module_root, manifest, "component")
    print("\n".join(names) if names else "(无组件)")
    return 0


def cmd_task_create(args: argparse.Namespace) -> int:
    """Create a page action under tasks/."""
    module_root = require_module_root()
    name = str(args.name or "").strip()
    if not is_valid_name(name):
        _print_error("页面操作名必须是小写 snake_case")
        return 1
    try:
        _write_text(
            module_root / "tasks" / f"{name}.py",
            SCRIPT_TEMPLATE.format(
                name=name,
                display_name=to_display_name(name),
                description=f"{to_display_name(name)} 页面操作",
            ),
            force=args.force,
        )
    except CLIError as exc:
        _print_error(str(exc))
        return 1
    _print_success(f"已创建页面操作: tasks/{name}.py")
    return 0


def cmd_task_list(args: argparse.Namespace) -> int:
    """List page actions in the current module."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    tasks = _v2_declaration_names(module_root, manifest, "page_action")
    print("\n".join(tasks) if tasks else "(无页面操作)")
    return 0


def cmd_ui_action_create(args: argparse.Namespace) -> int:
    """Create a hosted UI action under pages/."""
    module_root = require_module_root()
    name = str(args.name or "").strip()
    if not is_valid_name(name):
        _print_error("UI 操作名必须是小写 snake_case")
        return 1
    try:
        _write_text(
            module_root / "pages" / f"{name}.py",
            UI_ACTION_TEMPLATE.format(
                name=name,
                class_name=to_class_name(name),
                display_name=to_display_name(name),
                description=f"{to_display_name(name)} UI 操作",
            ),
            force=args.force,
        )
    except CLIError as exc:
        _print_error(str(exc))
        return 1
    _print_success(f"已创建 UI 操作: pages/{name}.py")
    return 0


def cmd_ui_action_list(args: argparse.Namespace) -> int:
    """List hosted UI actions in the current module."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    actions = _v2_declaration_names(module_root, manifest, "ui_action")
    print("\n".join(actions) if actions else "(无 UI 操作)")
    return 0


def cmd_workflow_create(args: argparse.Namespace) -> int:
    """Create a core-native-v2 workflow declaration."""
    module_root = require_module_root()
    name = str(args.name or "").strip()
    if not is_valid_name(name):
        _print_error("工作流名必须是小写 snake_case")
        return 1
    try:
        _write_text(
            module_root / "workflows" / f"{name}.py",
            WORKFLOW_TEMPLATE.format(
                name=name,
                class_name=to_class_name(name),
                display_name=args.display_name or to_display_name(name),
                description=args.description or f"{to_display_name(name)} 工作流",
                host_scenarios_arg=_workflow_host_scenarios_arg(getattr(args, "host_scenario", [])),
            ),
            force=args.force,
        )
    except CLIError as exc:
        _print_error(str(exc))
        return 1
    _print_success(f"已创建工作流: workflows/{name}.py")
    return 0


def cmd_workflow_list(args: argparse.Namespace) -> int:
    """List core-native-v2 workflow declarations."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    names = _v2_declaration_names(module_root, manifest, "workflow")
    print("\n".join(names) if names else "(无工作流)")
    return 0


def cmd_candidate_create(args: argparse.Namespace) -> int:
    """Create a pure env candidate function under candidates/."""
    module_root = require_module_root()
    name = str(args.name or "").strip()
    if not is_valid_name(name):
        _print_error("环境候选函数名必须是小写 snake_case")
        return 1
    try:
        _write_text(
            module_root / "candidates" / f"{name}.py",
            ENV_CANDIDATES_TEMPLATE.format(
                name=name,
                display_name=args.display_name or to_display_name(name),
                description=args.description or f"{to_display_name(name)} 环境候选函数",
            ),
            force=args.force,
        )
    except CLIError as exc:
        _print_error(str(exc))
        return 1
    _print_success(f"已创建环境候选函数: candidates/{name}.py")
    return 0


def cmd_candidate_list(args: argparse.Namespace) -> int:
    """List pure env candidate functions in the current module."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    names = _v2_declaration_names(module_root, manifest, "env_candidates")
    print("\n".join(names) if names else "(无环境候选函数)")
    return 0


def cmd_cleanup_create(args: argparse.Namespace) -> int:
    """Create a pure env cleanup candidate function under cleanups/."""
    module_root = require_module_root()
    name = str(args.name or "").strip()
    if not is_valid_name(name):
        _print_error("环境清理候选函数名必须是小写 snake_case")
        return 1
    try:
        _write_text(
            module_root / "cleanups" / f"{name}.py",
            ENV_CLEANUP_CANDIDATES_TEMPLATE.format(
                name=name,
                display_name=args.display_name or to_display_name(name),
                description=args.description or f"{to_display_name(name)} 环境清理候选函数",
            ),
            force=args.force,
        )
    except CLIError as exc:
        _print_error(str(exc))
        return 1
    _print_success(f"已创建环境清理候选函数: cleanups/{name}.py")
    return 0


def cmd_cleanup_list(args: argparse.Namespace) -> int:
    """List pure env cleanup candidate functions in the current module."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    names = _v2_declaration_names(module_root, manifest, "env_cleanup_candidates")
    print("\n".join(names) if names else "(无环境清理候选函数)")
    return 0


def cmd_page_create(args: argparse.Namespace) -> int:
    """Create a hosted page scaffold inside pages/ with a @page decorator."""
    module_root = require_module_root()
    name = str(args.name or "").strip()
    if not is_valid_name(name):
        _print_error("页面名必须是小写 snake_case")
        return 1
    try:
        page_relative_path = _page_source_relative_path(name, group=getattr(args, "group", None))
    except CLIError as exc:
        _print_error(str(exc))
        return 1

    manifest = load_manifest(module_root)
    if "ui_extension" in manifest:
        _print_error("core-native-v2 不再使用 module.yaml.ui_extension；页面菜单请写在 @page(menu=True) 中")
        return 1
    legacy_ui_errors = _collect_legacy_hosted_ui_errors(module_root)
    if legacy_ui_errors:
        _print_error("检测到旧 Hosted UI 产物，请先移除后再创建宿主页")
        for item in legacy_ui_errors:
            print(f"  - {item}")
        return 1
    _ensure_package_dir(module_root / "pages")
    no_menu = bool(getattr(args, "no_menu", False))
    try:
        _write_text(
            module_root / page_relative_path,
            render_page_template(
                page_id=name,
                display_name=args.display_name or to_display_name(name),
                description=args.description or f"{to_display_name(name)} 宿主页",
                menu=not no_menu,
            ),
            force=args.force,
        )
    except CLIError as exc:
        _print_error(str(exc))
        return 1

    _print_success(f"已创建宿主页骨架: {page_relative_path.as_posix()}")
    return 0


def cmd_page_list(args: argparse.Namespace) -> int:
    """List left-menu hosted pages declared with @page."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    result = _v2_scan(module_root, manifest)
    pages = [item.name for item in result.declarations if item.kind == "page" and item.meta.menu]
    print("\n".join(pages) if pages else "(无页面)")
    return 0


def cmd_config_show(args: argparse.Namespace) -> int:
    """Show config_defaults from module.yaml."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    config_defaults = manifest.get("config_defaults") or {"module": {}}
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


def cmd_config_lint(args: argparse.Namespace) -> int:
    """Validate config_defaults structure and workflow references."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    config_defaults = manifest.get("config_defaults", {})
    test_manifest = dict(manifest)
    test_manifest["config_defaults"] = config_defaults
    errors = collect_release_errors(module_root, test_manifest)
    config_errors = [
        item for item in errors if item.startswith("config_defaults") or "config_defaults.workflows" in item
    ]
    if config_errors:
        _print_error("默认配置校验失败")
        for item in config_errors:
            print(f"  - {item}")
        return 1
    _print_success("默认配置校验通过")
    return 0


def cmd_manifest_lock(args: argparse.Namespace) -> int:
    """Write .crawler4j/manifest.lock.json from v2 decorator scan."""
    del args
    module_root = require_module_root()
    manifest = load_manifest(module_root)
    errors = collect_full_errors(module_root, manifest)
    if errors:
        _print_error("manifest lock 生成失败")
        for item in errors:
            print(f"  - {item}")
        return 1
    lock_path = _write_manifest_lock(module_root, manifest)
    _print_success(f"已更新 manifest lock: {lock_path.relative_to(module_root).as_posix()}")
    return 0


def cmd_package_build(args: argparse.Namespace) -> int:
    """Build an installable single-root ZIP package for the current module."""
    module_root = require_module_root()
    if _run_check("full", module_root) != 0:
        return 1

    manifest = load_manifest(module_root)
    _write_manifest_lock(module_root, manifest)
    archive_root = _resolve_module_import_name(module_root, manifest)
    version = str(manifest.get("version", "") or "").strip()
    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else module_root / "dist" / f"{archive_root}-{version}.zip"
    )
    output.parent.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for source, arcname in _archive_members(module_root, archive_root):
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
        errors = collect_full_errors(extracted_root, manifest, require_manifest_lock=True)
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
    archive_root = _resolve_module_import_name(module_root, manifest)
    version = str(manifest.get("version", "") or "").strip()
    repo = str((manifest.get("upgrade_source") or {}).get("repo", "") or "").strip()
    archive_path = module_root / "dist" / f"{archive_root}-{version}.zip"

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
    archive_root = _resolve_module_import_name(module_root, manifest)
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
        else module_root / "dist" / f"{archive_root}-{version}.zip"
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
    source_path = Path(args.module_root).expanduser().resolve() if args.module_root else require_module_root()
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
    subparsers = parser.add_subparsers(dest="command")

    module_parser = subparsers.add_parser(
        "module",
        help="模块项目操作：初始化、查看和修改 module.yaml 关键字段",
    )
    module_sub = module_parser.add_subparsers(dest="action")

    module_init = module_sub.add_parser(
        "init",
        help="初始化一个新的模块项目，生成 core-native-v2 标准骨架与 module.yaml",
    )
    module_init.add_argument("name", nargs="?", help="模块包名，必须是 snake_case；省略时进入交互式输入")
    module_init.add_argument("--repo", help="升级源 GitHub 仓库，格式 owner/repo；省略时进入交互式输入")
    module_init.add_argument("--output", help="输出目录，默认在当前目录下创建同名目录")
    module_init.add_argument("--display-name", help="模块显示名")
    module_init.add_argument("--description", help="模块说明")
    module_init.add_argument("--version", default=DEFAULT_MODULE_VERSION, help="模块版本号")
    module_init.add_argument("--workflow-name", default="main_workflow", help="初始工作流名")
    module_init.add_argument("--workflow-display-name", help="初始工作流显示名")
    module_init.add_argument("--workflow-description", help="初始工作流说明")
    module_init.add_argument("--python-version", default=DEFAULT_PYTHON_VERSION, help="目标 Python 版本")
    module_init.add_argument(
        "--runtime-api",
        default=CORE_NATIVE_V2_RUNTIME_API,
        choices=[CORE_NATIVE_V2_RUNTIME_API],
        help="运行时协议；0.4.x 只支持 core-native-v2",
    )
    module_init.add_argument("--no-git", action="store_true", help="不要执行 git init")
    module_init.add_argument("--no-install", action="store_true", help="不要执行 uv sync")
    module_init.add_argument("--force", action="store_true", help="允许覆盖脚手架管理文件")
    module_init.set_defaults(func=cmd_module_init)

    module_show = module_sub.add_parser(
        "show",
        help="显示当前模块的版本、仓库、v2 声明和宿主页入口",
    )
    module_show.set_defaults(func=cmd_module_show)

    module_repair_init = module_sub.add_parser(
        "repair-init",
        help="按当前标准模板重建模块根 __init__.py，不修改其他脚手架文件",
    )
    module_repair_init.set_defaults(func=cmd_module_repair_init)

    data_parser = subparsers.add_parser(
        "data",
        help="数据契约操作：创建 core-native-v2 data_table / data_view 装饰器声明",
    )
    data_sub = data_parser.add_subparsers(dest="action")

    data_list = data_sub.add_parser(
        "list",
        help="列出当前模块已声明的数据表和只读视图",
    )
    data_list.set_defaults(func=cmd_data_list)

    data_table = data_sub.add_parser(
        "table",
        help="创建 @data_table 声明文件",
    )
    data_table_sub = data_table.add_subparsers(dest="subaction")
    data_table_create = data_table_sub.add_parser(
        "create",
        help="创建一个数据表声明",
    )
    data_table_create.add_argument("name", help="数据表名，snake_case")
    data_table_create.add_argument(
        "--storage-mode",
        choices=sorted(DATA_TABLE_STORAGE_MODES),
        default="custom_table",
        help="存储模式，默认 custom_table；低频快照可选 managed_dataset",
    )
    data_table_create.add_argument("--display-name", help="显示名")
    data_table_create.add_argument("--description", help="说明")
    data_table_create.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    data_table_create.set_defaults(func=cmd_data_table_create)

    data_view = data_sub.add_parser(
        "view",
        help="创建 @data_view 声明文件",
    )
    data_view_sub = data_view.add_subparsers(dest="subaction")
    data_view_create = data_view_sub.add_parser(
        "create",
        help="创建一个只读视图骨架",
    )
    data_view_create.add_argument("name", help="视图名，snake_case")
    data_view_create.add_argument(
        "--source",
        required=True,
        help="来源 data_table 名称",
    )
    data_view_create.add_argument("--display-name", help="显示名")
    data_view_create.add_argument("--description", help="说明")
    data_view_create.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    data_view_create.set_defaults(func=cmd_data_view_create)

    module_set = module_sub.add_parser(
        "set",
        help="修改 module.yaml 中的关键字段",
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

    interface_parser = subparsers.add_parser(
        "interface",
        help="接口声明操作：在 interfaces/ 中创建或列出 @interface",
    )
    interface_sub = interface_parser.add_subparsers(dest="action")
    interface_create = interface_sub.add_parser("create", help="创建 @interface 声明")
    interface_create.add_argument("name", help="接口名，snake_case")
    interface_create.add_argument("--display-name", help="显示名")
    interface_create.add_argument("--description", help="说明")
    interface_create.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    interface_create.set_defaults(func=cmd_interface_create)
    interface_list = interface_sub.add_parser("list", help="列出 @interface 声明")
    interface_list.set_defaults(func=cmd_interface_list)

    component_parser = subparsers.add_parser(
        "component",
        help="组件声明操作：在 objects/ 中创建或列出 @component",
    )
    component_sub = component_parser.add_subparsers(dest="action")
    component_create = component_sub.add_parser("create", help="创建 @component 声明")
    component_create.add_argument("name", help="组件名，snake_case")
    component_create.add_argument("--implements", required=True, help="实现的接口名")
    component_create.add_argument("--display-name", help="显示名")
    component_create.add_argument("--description", help="说明")
    component_create.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    component_create.set_defaults(func=cmd_component_create)
    component_list = component_sub.add_parser("list", help="列出 @component 声明")
    component_list.set_defaults(func=cmd_component_list)

    page_action_parser = subparsers.add_parser(
        "page-action",
        help="页面操作：在 tasks/ 下创建或列出 @page_action 函数",
    )
    page_action_sub = page_action_parser.add_subparsers(dest="action")
    page_action_create = page_action_sub.add_parser("create", help="创建一个新的 @page_action 函数")
    page_action_create.add_argument("name", help="页面操作名，snake_case")
    page_action_create.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    page_action_create.set_defaults(func=cmd_task_create)
    page_action_list = page_action_sub.add_parser("list", help="列出 @page_action")
    page_action_list.set_defaults(func=cmd_task_list)

    ui_action_parser = subparsers.add_parser(
        "ui-action",
        help="UI 操作：在 pages/ 下创建或列出 @ui_action 函数",
    )
    ui_action_sub = ui_action_parser.add_subparsers(dest="action")
    ui_action_create = ui_action_sub.add_parser("create", help="创建一个新的 @ui_action 函数")
    ui_action_create.add_argument("name", help="UI 操作名，snake_case")
    ui_action_create.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    ui_action_create.set_defaults(func=cmd_ui_action_create)
    ui_action_list = ui_action_sub.add_parser("list", help="列出 @ui_action")
    ui_action_list.set_defaults(func=cmd_ui_action_list)

    workflow_parser = subparsers.add_parser(
        "workflow",
        help="工作流操作：在 workflows/ 下创建或列出 @workflow",
    )
    workflow_sub = workflow_parser.add_subparsers(dest="action")
    workflow_create = workflow_sub.add_parser(
        "create",
        help="创建 @workflow 声明文件",
    )
    workflow_create.add_argument("name", help="工作流名，snake_case")
    workflow_create.add_argument("--display-name", help="工作流显示名")
    workflow_create.add_argument("--description", help="工作流说明")
    workflow_create.add_argument(
        "--host-scenario",
        action="append",
        choices=sorted(WORKFLOW_HOST_SCENARIOS),
        default=[],
        help="声明宿主运行场景，可选 existing_env_import",
    )
    workflow_create.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    workflow_create.set_defaults(func=cmd_workflow_create)
    workflow_list = workflow_sub.add_parser("list", help="列出 @workflow 声明")
    workflow_list.set_defaults(func=cmd_workflow_list)

    candidate_parser = subparsers.add_parser(
        "candidate",
        help="环境候选函数操作：在 candidates/ 下创建或列出 @env_candidates",
    )
    candidate_sub = candidate_parser.add_subparsers(dest="action")
    candidate_create = candidate_sub.add_parser(
        "create",
        help="创建 @env_candidates 同步纯函数",
    )
    candidate_create.add_argument("name", help="候选函数名，snake_case")
    candidate_create.add_argument("--display-name", help="显示名")
    candidate_create.add_argument("--description", help="说明")
    candidate_create.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    candidate_create.set_defaults(func=cmd_candidate_create)
    candidate_list = candidate_sub.add_parser("list", help="列出 @env_candidates 声明")
    candidate_list.set_defaults(func=cmd_candidate_list)

    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="环境清理候选函数操作：在 cleanups/ 下创建或列出 @env_cleanup_candidates",
    )
    cleanup_sub = cleanup_parser.add_subparsers(dest="action")
    cleanup_create = cleanup_sub.add_parser(
        "create",
        help="创建 @env_cleanup_candidates 同步纯函数",
    )
    cleanup_create.add_argument("name", help="清理候选函数名，snake_case")
    cleanup_create.add_argument("--display-name", help="显示名")
    cleanup_create.add_argument("--description", help="说明")
    cleanup_create.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    cleanup_create.set_defaults(func=cmd_cleanup_create)
    cleanup_list = cleanup_sub.add_parser("list", help="列出 @env_cleanup_candidates 声明")
    cleanup_list.set_defaults(func=cmd_cleanup_list)

    page_parser = subparsers.add_parser(
        "page",
        help="宿主页操作：在 pages/ 生成 @page 宿主页骨架",
    )
    page_sub = page_parser.add_subparsers(dest="action")
    page_create = page_sub.add_parser(
        "create",
        help="创建一个 @page 宿主页骨架；默认进入左侧菜单，可用 --no-menu 只创建可路由页面",
    )
    page_create.add_argument("name", help="页面名，snake_case")
    page_create.add_argument("--group", help="可选源码分组目录，单层 snake_case；例如 account")
    page_create.add_argument("--no-menu", action="store_true", help="生成 @page(menu=False)，不进入左侧菜单")
    page_create.add_argument("--display-name", help="页面显示名")
    page_create.add_argument("--description", help="页面说明")
    page_create.add_argument("--force", action="store_true", help="允许覆盖已有文件")
    page_create.set_defaults(func=cmd_page_create)
    page_list = page_sub.add_parser("list", help="列出 @page(menu=True) 左侧菜单入口")
    page_list.set_defaults(func=cmd_page_list)

    config_parser = subparsers.add_parser(
        "config",
        help="默认配置操作：管理 module.yaml.config_defaults",
    )
    config_sub = config_parser.add_subparsers(dest="action")
    config_show = config_sub.add_parser("show", help="显示 config_defaults 当前内容")
    config_show.set_defaults(func=cmd_config_show)
    config_set = config_sub.add_parser(
        "set",
        help="从 YAML 文件写入模块级默认配置",
    )
    config_set_sub = config_set.add_subparsers(dest="scope")
    config_set_module = config_set_sub.add_parser(
        "module",
        help="把 YAML 文件写入 config_defaults.module",
    )
    config_set_module.add_argument("--file", required=True, help="YAML 文件路径")
    config_set_module.set_defaults(func=cmd_config_set_module)
    config_lint = config_sub.add_parser(
        "lint",
        help="校验 config_defaults 的 YAML 结构是否正确",
    )
    config_lint.set_defaults(func=cmd_config_lint)

    manifest_parser = subparsers.add_parser(
        "manifest",
        help="manifest 辅助操作",
    )
    manifest_sub = manifest_parser.add_subparsers(dest="action")
    manifest_lock = manifest_sub.add_parser(
        "lock",
        help="扫描 core-native-v2 装饰器并生成 .crawler4j/manifest.lock.json",
    )
    manifest_lock.set_defaults(func=cmd_manifest_lock)

    package_parser = subparsers.add_parser(
        "package",
        help="安装包操作：构建或校验单根目录 ZIP 模块安装包",
    )
    package_sub = package_parser.add_subparsers(dest="action")
    package_build = package_sub.add_parser(
        "build",
        help="构建正式安装 ZIP；会先执行 full gate 并刷新 manifest lock",
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
        help="检查 module.yaml、core-native-v2 目录结构和 UI 入口格式",
    )
    check_structure.set_defaults(func=cmd_check_structure)
    check_release = check_sub.add_parser(
        "release",
        help="在 structure 基础上继续检查 version、upgrade_source.repo、config_defaults 等发布前提",
    )
    check_release.set_defaults(func=cmd_check_release)
    check_full = check_sub.add_parser(
        "full",
        help="在 release 基础上扫描 v2 装饰器并执行完整 gate",
    )
    check_full.set_defaults(func=cmd_check_full)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the crawler4j CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
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

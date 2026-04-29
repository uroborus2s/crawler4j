"""Shared helpers for release packaging scripts."""

from __future__ import annotations

import os
import shutil
import tomllib
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j"
PACKAGE_PYPROJECT = APP_ROOT / "pyproject.toml"
DEFAULT_ENV_FILE = WORKSPACE_ROOT / ".env"


def load_project_version(pyproject_path: Path = PACKAGE_PYPROJECT) -> str:
    with pyproject_path.open("rb") as f:
        pyproject = tomllib.load(f)
    return str(pyproject["project"]["version"])


def reset_output_dir(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    shutil.rmtree(resolved, ignore_errors=True)
    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def load_dotenv_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ValueError(f"{path}:{line_number} 缺少 '='。")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f"{path}:{line_number} 缺少环境变量名。")
        if value and value[0] in {'"', "'"}:
            quote = value[0]
            if len(value) < 2 or value[-1] != quote:
                raise ValueError(f"{path}:{line_number} 引号未闭合。")
            value = value[1:-1]
        values[key] = value
    return values


def resolve_runtime_env(
    env: dict[str, str] | None = None,
    *,
    env_file: Path | None = None,
    default_env_file: Path = DEFAULT_ENV_FILE,
) -> dict[str, str]:
    env_map: dict[str, str] = {}
    dotenv_path = env_file.expanduser().resolve() if env_file else default_env_file
    if env_file is not None:
        if not dotenv_path.exists():
            raise FileNotFoundError(f"未找到 dotenv 文件: {dotenv_path}")
        env_map.update(load_dotenv_file(dotenv_path))
    elif dotenv_path.exists():
        env_map.update(load_dotenv_file(dotenv_path))
    env_map.update(os.environ)
    if env:
        env_map.update(env)
    return env_map

"""Helpers for launching the debug worker across source and frozen runtimes."""

from __future__ import annotations

from collections.abc import Sequence
import os
from pathlib import Path
import shlex

EMBEDDED_DEBUG_WORKER_FLAG = "--crawler4j-debug-worker"
EMBEDDED_DEBUGPY_ADAPTER_FLAG = "--crawler4j-debugpy-adapter"
DEFAULT_WORKER_MODULE = "src.core.debug.worker_entry"


def build_debug_worker_command(
    executable: str,
    session_file: Path,
    *,
    worker_module: str = DEFAULT_WORKER_MODULE,
    frozen: bool,
) -> list[str]:
    if frozen:
        return [executable, EMBEDDED_DEBUG_WORKER_FLAG, str(session_file)]
    return [executable, "-m", worker_module, str(session_file)]


def extract_embedded_debug_worker_args(
    argv: Sequence[str],
    *,
    worker_module: str = DEFAULT_WORKER_MODULE,
) -> list[str] | None:
    args = list(argv)
    if len(args) >= 3 and args[1] == EMBEDDED_DEBUG_WORKER_FLAG:
        return args[2:]
    if len(args) >= 4 and args[1] == "-m" and args[2] == worker_module:
        return args[3:]
    return None


def create_debugpy_adapter_launcher(executable: str, session_dir: Path) -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        launcher = session_dir / "debugpy_adapter_launcher.cmd"
        launcher.write_text(
            f'@"{executable}" {EMBEDDED_DEBUGPY_ADAPTER_FLAG} %*\r\n',
            encoding="utf-8",
        )
        return launcher

    launcher = session_dir / "debugpy_adapter_launcher.sh"
    launcher.write_text(
        "#!/bin/sh\n"
        f"exec {shlex.quote(executable)} {EMBEDDED_DEBUGPY_ADAPTER_FLAG} \"$@\"\n",
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    return launcher


def configure_debugpy_for_frozen_bundle(
    debugpy_module,
    *,
    executable: str,
    session_dir: Path,
    frozen: bool,
) -> Path | None:
    if not frozen:
        return None
    launcher = create_debugpy_adapter_launcher(executable, session_dir)
    debugpy_module.configure(python=str(launcher))
    return launcher


def extract_embedded_debugpy_adapter_args(argv: Sequence[str]) -> list[str] | None:
    args = list(argv)
    if len(args) < 3 or args[1] != EMBEDDED_DEBUGPY_ADAPTER_FLAG:
        return None
    adapter_args = args[2:]
    if adapter_args and not adapter_args[0].startswith("-"):
        adapter_args = adapter_args[1:]
    return adapter_args

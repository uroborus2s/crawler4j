"""VS Code attach configuration helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_ATTACH_NAME = "Attach to Crawler4j"


def _build_attach_configuration(
    host: str,
    port: int,
    module_dir: Path,
    name: str = DEFAULT_ATTACH_NAME,
) -> dict[str, Any]:
    return {
        "name": name,
        "type": "debugpy",
        "request": "attach",
        "connect": {
            "host": host,
            "port": port,
        },
        "justMyCode": False,
        # VS Code may open the DevLink module through a workspace alias or symlink,
        # while the worker resolves and imports the real module path on disk.
        # Explicit pathMappings keeps breakpoints bound to the worker's source files.
        "pathMappings": [
            {
                "localRoot": "${workspaceFolder}",
                "remoteRoot": str(module_dir),
            }
        ],
    }


def ensure_vscode_attach_config(
    source_path: str | Path,
    *,
    host: str,
    port: int,
    configuration_name: str = DEFAULT_ATTACH_NAME,
) -> Path:
    module_dir = Path(source_path).expanduser().resolve()
    vscode_dir = module_dir / ".vscode"
    vscode_dir.mkdir(parents=True, exist_ok=True)
    launch_path = vscode_dir / "launch.json"

    payload: dict[str, Any] = {"version": "0.2.0", "configurations": []}
    if launch_path.exists():
        try:
            loaded = json.loads(launch_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                payload.update(loaded)
        except json.JSONDecodeError:
            pass

    configurations = payload.get("configurations")
    if not isinstance(configurations, list):
        configurations = []

    new_config = _build_attach_configuration(host, port, module_dir, configuration_name)
    replaced = False
    normalized_configs = []
    for item in configurations:
        if isinstance(item, dict) and item.get("name") == configuration_name:
            normalized_configs.append(new_config)
            replaced = True
        elif isinstance(item, dict):
            normalized_configs.append(item)

    if not replaced:
        normalized_configs.append(new_config)

    payload["version"] = payload.get("version") or "0.2.0"
    payload["configurations"] = normalized_configs
    launch_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return launch_path

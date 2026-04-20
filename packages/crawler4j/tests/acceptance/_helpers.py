from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import yaml


WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
APP_PACKAGE_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j"
SDK_PACKAGE_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j-sdk"
CONTRACTS_PACKAGE_ROOT = WORKSPACE_ROOT / "packages" / "crawler4j-contracts"
MODULE_NAME = "demo_model"
MODULE_REPO = "demo/demo_model"
MODULE_VERSION = "0.1.0"


@dataclass(frozen=True)
class AcceptanceGateCommand:
    name: str
    argv: tuple[str, ...]
    success_text: str
    needs_archive: bool = False


ACCEPTANCE_GATE_MATRIX = (
    AcceptanceGateCommand(
        name="structure",
        argv=("check", "structure"),
        success_text="structure 校验通过",
    ),
    AcceptanceGateCommand(
        name="release",
        argv=("check", "release"),
        success_text="release 校验通过",
    ),
    AcceptanceGateCommand(
        name="full",
        argv=("check", "full"),
        success_text="full 校验通过",
    ),
    AcceptanceGateCommand(
        name="package_verify",
        argv=("package", "verify"),
        success_text="ZIP 校验通过",
        needs_archive=True,
    ),
)


@dataclass(frozen=True)
class CliRunResult:
    args: tuple[str, ...]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str

    def describe(self) -> str:
        rendered = " ".join(self.args)
        return (
            f"command: {rendered}\n"
            f"cwd: {self.cwd}\n"
            f"returncode: {self.returncode}\n"
            f"stdout:\n{self.stdout}\n"
            f"stderr:\n{self.stderr}"
        )

    def assert_ok(self) -> None:
        assert self.returncode == 0, self.describe()

    def assert_failed(self, returncode: int = 1) -> None:
        assert self.returncode == returncode, self.describe()

    def assert_stdout_contains(self, text: str) -> None:
        assert text in self.stdout, self.describe()


def build_cli_env(*, home: Path | None = None, extra_env: Mapping[str, str] | None = None) -> dict[str, str]:
    env = os.environ.copy()
    python_path_parts = [
        str(APP_PACKAGE_ROOT),
        str(SDK_PACKAGE_ROOT),
        str(CONTRACTS_PACKAGE_ROOT),
    ]
    existing_python_path = env.get("PYTHONPATH", "")
    if existing_python_path:
        python_path_parts.append(existing_python_path)
    env["PYTHONPATH"] = os.pathsep.join(python_path_parts)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    if home is not None:
        home.mkdir(parents=True, exist_ok=True)
        env["HOME"] = str(home)
    if extra_env:
        env.update({key: str(value) for key, value in extra_env.items()})
    return env


def run_cli(
    *args: str,
    cwd: Path,
    home: Path | None = None,
    extra_env: Mapping[str, str] | None = None,
) -> CliRunResult:
    completed = subprocess.run(
        [sys.executable, "-m", "crawler4j_sdk.cli.commands", *args],
        cwd=str(cwd),
        env=build_cli_env(home=home, extra_env=extra_env),
        check=False,
        capture_output=True,
        text=True,
    )
    return CliRunResult(
        args=tuple(args),
        cwd=cwd,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def scaffold_module(base_dir: Path, *, module_name: str = MODULE_NAME, repo: str = MODULE_REPO) -> Path:
    module_root = base_dir / module_name
    result = run_cli(
        "module",
        "init",
        module_name,
        "--repo",
        repo,
        "--output",
        str(module_root),
        "--no-install",
        "--no-git",
        cwd=WORKSPACE_ROOT,
    )
    result.assert_ok()
    return module_root


def enrich_module(module_root: Path) -> Path:
    commands = (
        ("task", "create", "extra_task"),
        ("workflow", "create", "repair_orders"),
        ("page", "create", "dashboard"),
        ("data-table", "create", "accounts"),
        ("env-selector", "create", "pick_ready"),
    )
    for argv in commands:
        result = run_cli(*argv, cwd=module_root)
        result.assert_ok()
    return module_root


def build_package(module_root: Path) -> Path:
    result = run_cli("package", "build", cwd=module_root)
    result.assert_ok()
    archive_path = module_root / "dist" / f"{module_root.name}-{MODULE_VERSION}.zip"
    assert archive_path.exists(), result.describe()
    return archive_path


def load_manifest(module_root: Path) -> dict:
    with (module_root / "module.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def save_manifest(module_root: Path, manifest: dict) -> None:
    with (module_root / "module.yaml").open("w", encoding="utf-8") as handle:
        yaml.safe_dump(manifest, handle, allow_unicode=True, sort_keys=False)


def archive_members(archive_path: Path) -> list[str]:
    with zipfile.ZipFile(archive_path) as archive:
        return sorted(archive.namelist())


def get_host_app_data_dir(home: Path) -> Path:
    if sys.platform == "win32":
        return home / "AppData" / "Roaming" / "Crawler4j"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support" / "Crawler4j"
    return home / ".local" / "share" / "Crawler4j"

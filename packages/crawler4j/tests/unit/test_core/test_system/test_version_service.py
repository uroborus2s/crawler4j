from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import tomllib

PROJECT_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(PROJECT_ROOT))

MODULE_PATH = PROJECT_ROOT / "src" / "core" / "system" / "version_service.py"
MODULE_SPEC = importlib.util.spec_from_file_location("crawler4j_version_service", MODULE_PATH)
assert MODULE_SPEC and MODULE_SPEC.loader
version_module = importlib.util.module_from_spec(MODULE_SPEC)
sys.modules[MODULE_SPEC.name] = version_module
MODULE_SPEC.loader.exec_module(version_module)
VersionService = version_module.VersionService


def _load_pyproject_version() -> str:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as f:
        pyproject = tomllib.load(f)

    return str(pyproject["project"]["version"])


def test_runtime_version_matches_root_pyproject() -> None:
    assert version_module.get_current_version() == _load_pyproject_version()


def test_parse_version_accepts_dev_and_rc_formats() -> None:
    service = VersionService()

    assert service._parse_version("0.1.2.dev20260326") == (0, 1, 2)
    assert service._parse_version("0.2.0-rc.20260112") == (0, 2, 0)
    assert service._parse_version("v0.1.1") == (0, 1, 1)


def test_check_compatibility_uses_base_version_for_workspace_version(
    monkeypatch,
) -> None:
    monkeypatch.setattr(version_module, "_load_declared_version", lambda: "0.1.2.dev20260326")
    version_module.get_current_version.cache_clear()
    service = VersionService()

    assert service.check_compatibility(">=0.1.1") is True
    assert service.check_compatibility("^0.1.0") is True
    assert service.check_compatibility("^0.2.0") is False

from __future__ import annotations

from pathlib import Path
import tomllib

import src.core.system.version_service as version_module
from src.__version__ import VERSION
from src.core.system.version_service import VersionService


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def test_runtime_version_matches_root_pyproject() -> None:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as f:
        pyproject = tomllib.load(f)

    assert pyproject["project"]["version"] == VERSION


def test_parse_version_accepts_dev_and_legacy_rc_formats() -> None:
    service = VersionService()

    assert service._parse_version("0.1.2.dev20260326") == (0, 1, 2)
    assert service._parse_version("0.2.0-rc.20260112") == (0, 2, 0)
    assert service._parse_version("v0.1.1") == (0, 1, 1)


def test_check_compatibility_uses_base_version_for_workspace_version(
    monkeypatch,
) -> None:
    monkeypatch.setattr(version_module, "VERSION", "0.1.2.dev20260326")
    service = VersionService()

    assert service.check_compatibility(">=0.1.1") is True
    assert service.check_compatibility("^0.1.0") is True
    assert service.check_compatibility("^0.2.0") is False

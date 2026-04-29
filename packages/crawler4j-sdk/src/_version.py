"""Version helpers backed by package metadata and pyproject.toml."""

from __future__ import annotations

import re
import tomllib
from importlib import metadata
from pathlib import Path


PACKAGE_NAME = "crawler4j-sdk"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PYPROJECT_PATH = PACKAGE_ROOT / "pyproject.toml"
CONTRACTS_PACKAGE_NAME = "crawler4j-contracts"
CONTRACTS_PYPROJECT_PATH = PACKAGE_ROOT.parent / "crawler4j-contracts" / "pyproject.toml"
BASE_VERSION_RE = re.compile(r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)")


def _load_version_from_metadata(package_name: str = PACKAGE_NAME) -> str | None:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return None


def _load_version_from_pyproject(pyproject_path: Path = PYPROJECT_PATH) -> str:
    with pyproject_path.open("rb") as f:
        pyproject = tomllib.load(f)
    return str(pyproject["project"]["version"])


def get_version() -> str:
    """Resolve the package version from build metadata or the source pyproject."""
    if PYPROJECT_PATH.exists():
        return _load_version_from_pyproject()
    return _load_version_from_metadata() or _load_version_from_pyproject()


def get_base_version(version: str | None = None) -> str:
    """Extract major.minor.patch from the declared version string."""
    resolved = version or get_version()
    match = BASE_VERSION_RE.match(resolved.strip())
    if not match:
        raise ValueError(f"Unsupported version format: {resolved}")
    return f"{match.group('major')}.{match.group('minor')}.{match.group('patch')}"


def get_compatible_dependency_spec() -> str:
    """Build the default scaffold dependency range for the current SDK version."""
    base_version = get_base_version()
    return get_compatible_sdk_dependency_spec(base_version)


def get_compatible_sdk_dependency_spec(version: str | None = None) -> str:
    """Build the default crawler4j-sdk dependency range for development helpers."""
    base_version = get_base_version(version)
    major, minor, _patch = (int(part) for part in base_version.split(".", 2))
    if major == 0:
        upper_bound = f"0.{minor + 1}.0"
    else:
        upper_bound = f"{major + 1}.0.0"
    return f"{PACKAGE_NAME}>={base_version},<{upper_bound}"


def _load_contracts_version() -> str:
    # Inside the source workspace, keep generated dependencies aligned with the local contracts checkout.
    if CONTRACTS_PYPROJECT_PATH.exists():
        return _load_version_from_pyproject(CONTRACTS_PYPROJECT_PATH)

    resolved = _load_version_from_metadata(CONTRACTS_PACKAGE_NAME)
    if resolved:
        return resolved
    return _load_version_from_pyproject(CONTRACTS_PYPROJECT_PATH)


def get_compatible_contracts_dependency_spec() -> str:
    """Build the default crawler4j-contracts dependency range for generated modules."""
    base_version = get_base_version(_load_contracts_version())
    major, minor, _patch = (int(part) for part in base_version.split(".", 2))
    if major == 0:
        upper_bound = f"0.{minor + 1}.0"
    else:
        upper_bound = f"{major + 1}.0.0"
    return f"{CONTRACTS_PACKAGE_NAME}>={base_version},<{upper_bound}"

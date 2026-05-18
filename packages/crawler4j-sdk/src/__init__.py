"""Crawler4j SDK - CLI and development helpers for core-native-v2 modules."""

from crawler4j_sdk._version import (
    get_compatible_contracts_dependency_spec,
    get_compatible_dependency_spec,
    get_compatible_sdk_dependency_spec,
    get_version,
)

__version__ = get_version()

__all__ = [
    "get_version",
    "get_compatible_dependency_spec",
    "get_compatible_sdk_dependency_spec",
    "get_compatible_contracts_dependency_spec",
]

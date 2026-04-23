"""Crawler4j SDK - CLI and development helpers for core-native-v1 modules."""

from crawler4j_sdk._version import (
    get_compatible_contracts_dependency_spec,
    get_compatible_dependency_spec,
    get_compatible_sdk_dependency_spec,
    get_version,
)
from crawler4j_sdk.resource_pool import (
    bind_resource_pool,
    mark_resource_pool_eligible,
    mark_resource_pool_ineligible,
    remove_resource_pool,
    replace_resource_pool_snapshot,
)

__version__ = get_version()

__all__ = [
    "get_version",
    "get_compatible_dependency_spec",
    "get_compatible_sdk_dependency_spec",
    "get_compatible_contracts_dependency_spec",
    "bind_resource_pool",
    "mark_resource_pool_eligible",
    "mark_resource_pool_ineligible",
    "remove_resource_pool",
    "replace_resource_pool_snapshot",
]

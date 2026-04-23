"""Shared module declaration specs for core-native-v1 modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TaskSpec:
    """Declarative task metadata exported from ``tasks/*.py``."""

    name: str
    display_name: str = ""
    description: str = ""
    default_config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkflowSpec:
    """Declarative workflow metadata exported from ``workflows/*.py``."""

    name: str
    display_name: str = ""
    description: str = ""
    tasks: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EnvSelectorSpec:
    """Declarative env-selector metadata exported from ``env_selectors/*.py``."""

    name: str
    display_name: str = ""
    description: str = ""
    returns_none: bool = False


@dataclass(frozen=True)
class PageSpec:
    """Declarative hosted-page metadata exported from ``pages/*.py``."""

    id: str
    label: str = ""
    icon: str = "📋"
    schema: dict[str, Any] = field(default_factory=dict)

"""Hosted UI page declaration specs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PageSpec:
    """Declarative hosted-page metadata exported from ``pages/*.py``."""

    id: str
    label: str = ""
    icon: str = "📋"
    schema: dict[str, Any] = field(default_factory=dict)

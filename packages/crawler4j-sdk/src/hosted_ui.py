"""SDK compatibility re-export for hosted UI schema helpers."""

from __future__ import annotations

from crawler4j_contracts import hosted_ui as _hosted_ui
from crawler4j_contracts.hosted_ui import *  # noqa: F401,F403

__all__ = [name for name in dir(_hosted_ui) if not name.startswith("_")]


def __getattr__(name: str):
    return getattr(_hosted_ui, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_hosted_ui)))

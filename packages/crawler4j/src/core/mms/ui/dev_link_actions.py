"""Shared helpers for dev-link removal UI flows."""

from __future__ import annotations

from dataclasses import dataclass

from src.core.mms import ModuleSource, get_module_registry
from src.core.mms.models import ModuleInfo


@dataclass(frozen=True, slots=True)
class DevLinkRemovalResult:
    fallback: ModuleInfo | None
    title: str
    message: str


def remove_dev_link_and_describe(module_name: str) -> DevLinkRemovalResult:
    registry = get_module_registry()
    if not registry.remove_dev_link(module_name):
        raise ValueError(f"未找到开发链接: {module_name}")

    fallback = registry.get_module(module_name)
    if fallback is None:
        return DevLinkRemovalResult(
            fallback=None,
            title="已移除",
            message=f"已移除开发链接: {module_name}",
        )

    source_label = "内置模块" if fallback.source == ModuleSource.BUILTIN else "正式安装模块"
    return DevLinkRemovalResult(
        fallback=fallback,
        title="已切换",
        message=f"已移除开发链接，当前已回退到 {source_label}: {fallback.name}",
    )

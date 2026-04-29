"""YAML validation helpers for module configuration payloads."""

from __future__ import annotations

from typing import Any

import yaml


class YamlConfigValidationError(ValueError):
    """Raised when module configuration YAML cannot be accepted."""

    def __init__(self, message: str, *, line: int | None = None, column: int | None = None) -> None:
        super().__init__(message)
        self.line = line
        self.column = column


class _UniqueKeySafeLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def _construct_mapping_without_duplicate_keys(
    loader: _UniqueKeySafeLoader,
    node: yaml.nodes.MappingNode,
    deep: bool = False,
) -> dict[Any, Any]:
    loader.flatten_mapping(node)
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            mark = getattr(key_node, "start_mark", None)
            line = None
            column = None
            if mark is not None:
                line = mark.line + 1
                column = mark.column + 1
            location = f"（第 {line} 行，第 {column} 列）" if line is not None and column is not None else ""
            raise YamlConfigValidationError(f"YAML 中存在重复键: {key}{location}", line=line, column=column)
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_without_duplicate_keys,
)


def parse_yaml_config_mapping(raw: str, *, scope_name: str = "配置") -> dict[str, Any]:
    """Parse a YAML document and require a mapping root.

    Empty input is accepted as an empty mapping. Standard YAML flow mappings are
    accepted and later normalized by the caller when dumping back to the editor.
    """

    if not raw.strip():
        return {}

    try:
        payload = yaml.load(raw, Loader=_UniqueKeySafeLoader)
    except YamlConfigValidationError:
        raise
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = mark.line + 1 if mark is not None else None
        column = mark.column + 1 if mark is not None else None
        raise YamlConfigValidationError(f"{scope_name} YAML 格式错误: {exc}", line=line, column=column) from exc

    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise YamlConfigValidationError(f"{scope_name}必须是 YAML 映射对象")

    return payload

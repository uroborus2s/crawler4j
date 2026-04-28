"""Schema-driven host configuration center."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Literal

from PyQt6.QtCore import QObject, pyqtSignal

from src.core.persistence.database import CONFIG_DB, get_connection


ConfigValueType = Literal["bool", "int", "float", "string", "secret", "path", "enum"]
ConfigEffect = Literal["immediate", "new_tasks_only", "restart_required"]


class ConfigValidationError(ValueError):
    """Raised when a config value does not match its registered schema."""


@dataclass(frozen=True)
class ConfigChoice:
    value: Any
    label: str


@dataclass(frozen=True)
class ConfigSectionSpec:
    id: str
    title: str
    order: int = 100


@dataclass(frozen=True)
class ConfigDomainSpec:
    id: str
    title: str
    order: int = 100
    sections: tuple[ConfigSectionSpec, ...] = ()


@dataclass(frozen=True)
class ConfigItemSpec:
    key: str
    label: str
    value_type: ConfigValueType
    default: Any
    domain: str
    section: str
    description: str = ""
    unit: str = ""
    choices: tuple[ConfigChoice, ...] = ()
    min_value: int | float | None = None
    max_value: int | float | None = None
    effect: ConfigEffect = "immediate"
    advanced: bool = False
    namespace: str = ""
    key_path: str = ""

    def storage_namespace(self) -> str:
        return self.namespace or _default_namespace_for_key(self.key)

    def storage_key_path(self) -> str:
        return self.key_path or _default_key_path_for_key(self.key)


@dataclass(frozen=True)
class ConfigValue:
    spec: ConfigItemSpec
    value: Any
    source: Literal["default", "stored"] = "default"


@dataclass(frozen=True)
class ConfigRegistry:
    domains: tuple[ConfigDomainSpec, ...]
    items: tuple[ConfigItemSpec, ...]
    _items_by_key: dict[str, ConfigItemSpec] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_items_by_key", {item.key: item for item in self.items})

    def get_item(self, key: str) -> ConfigItemSpec:
        try:
            return self._items_by_key[key]
        except KeyError as exc:
            raise KeyError(f"Unknown config key: {key}") from exc

    def list_domains(self) -> tuple[ConfigDomainSpec, ...]:
        return tuple(sorted(self.domains, key=lambda domain: (domain.order, domain.title)))

    def list_items(self, *, domain: str | None = None, section: str | None = None) -> tuple[ConfigItemSpec, ...]:
        items = self.items
        if domain is not None:
            items = tuple(item for item in items if item.domain == domain)
        if section is not None:
            items = tuple(item for item in items if item.section == section)
        return tuple(sorted(items, key=lambda item: (item.domain, item.section, item.label)))


def _default_namespace_for_key(key: str) -> str:
    parts = [part for part in str(key).split(".") if part]
    if len(parts) >= 2 and parts[0] in {"browser", "mms"}:
        return ".".join(parts[:2])
    return parts[0] if parts else "system"


def _default_key_path_for_key(key: str) -> str:
    parts = [part for part in str(key).split(".") if part]
    if len(parts) >= 2 and parts[0] in {"browser", "mms"}:
        return ".".join(parts[2:]) or parts[-1]
    return ".".join(parts[1:]) if len(parts) > 1 else str(key)


DEFAULT_CONFIG_REGISTRY = ConfigRegistry(
    domains=(
        ConfigDomainSpec(
            id="system",
            title="系统",
            order=10,
            sections=(
                ConfigSectionSpec("appearance", "外观", 10),
            ),
        ),
        ConfigDomainSpec(
            id="update",
            title="应用升级",
            order=20,
            sections=(
                ConfigSectionSpec("control", "升级", 10),
            ),
        ),
        ConfigDomainSpec(
            id="network",
            title="网络",
            order=30,
            sections=(ConfigSectionSpec("proxy", "代理", 10),),
        ),
        ConfigDomainSpec(
            id="browser",
            title="外部浏览器",
            order=40,
            sections=(
                ConfigSectionSpec("bitbrowser", "BitBrowser", 10),
                ConfigSectionSpec("virtualbrowser", "VirtualBrowser", 20),
            ),
        ),
        ConfigDomainSpec(
            id="atm",
            title="任务运行",
            order=50,
            sections=(
                ConfigSectionSpec("execution", "执行默认值", 10),
                ConfigSectionSpec("finalization", "收尾保护预算", 20),
            ),
        ),
        ConfigDomainSpec(
            id="resources",
            title="资源",
            order=60,
            sections=(
                ConfigSectionSpec("logging", "日志", 10),
                ConfigSectionSpec("rem", "环境管理", 20),
            ),
        ),
    ),
    items=(
        ConfigItemSpec(
            key="system.theme",
            label="主题",
            value_type="enum",
            default="dark",
            domain="system",
            section="appearance",
            choices=(
                ConfigChoice("dark", "深色"),
                ConfigChoice("light", "浅色"),
                ConfigChoice("system", "跟随系统"),
            ),
        ),
        ConfigItemSpec(
            key="system.locale",
            label="语言",
            value_type="enum",
            default="system",
            domain="system",
            section="appearance",
            choices=(
                ConfigChoice("system", "跟随系统"),
                ConfigChoice("zh_CN", "简体中文"),
                ConfigChoice("en_US", "English"),
            ),
            effect="restart_required",
        ),
        ConfigItemSpec(
            key="system.auto_update",
            label="自动检查更新",
            value_type="bool",
            default=True,
            domain="update",
            section="control",
            description="控制 Sparkle 或 Velopack 的自动检查行为。",
        ),
        ConfigItemSpec(
            key="network.proxy_mode",
            label="代理模式",
            value_type="enum",
            default="system",
            domain="network",
            section="proxy",
            choices=(
                ConfigChoice("system", "跟随系统"),
                ConfigChoice("none", "不使用代理"),
                ConfigChoice("manual", "手动配置"),
            ),
            effect="restart_required",
        ),
        ConfigItemSpec(
            key="network.http_proxy",
            label="HTTP 代理",
            value_type="string",
            default="",
            domain="network",
            section="proxy",
            description="例如 http://127.0.0.1:7890",
        ),
        ConfigItemSpec(
            key="browser.bitbrowser.port",
            label="API 端口",
            value_type="int",
            default=54345,
            domain="browser",
            section="bitbrowser",
            min_value=1024,
            max_value=65535,
        ),
        ConfigItemSpec(
            key="browser.bitbrowser.path",
            label="程序位置",
            value_type="path",
            default="",
            domain="browser",
            section="bitbrowser",
        ),
        ConfigItemSpec(
            key="browser.virtualbrowser.port",
            label="API 端口",
            value_type="int",
            default=9002,
            domain="browser",
            section="virtualbrowser",
            min_value=1024,
            max_value=65535,
        ),
        ConfigItemSpec(
            key="browser.virtualbrowser.apikey",
            label="API 密钥",
            value_type="secret",
            default="",
            domain="browser",
            section="virtualbrowser",
        ),
        ConfigItemSpec(
            key="browser.virtualbrowser.path",
            label="程序位置",
            value_type="path",
            default="",
            domain="browser",
            section="virtualbrowser",
        ),
        ConfigItemSpec(
            key="atm.default_execution_timeout_seconds",
            label="新建任务默认执行超时",
            value_type="int",
            default=600,
            domain="atm",
            section="execution",
            description="0 表示不自动超时，只影响新建运行模板。",
            unit="秒",
            min_value=0,
            max_value=7 * 24 * 60 * 60,
        ),
        ConfigItemSpec(
            key="atm.terminal_hook_timeout_seconds",
            label="终态 Hook 超时",
            value_type="int",
            default=60,
            domain="atm",
            section="finalization",
            unit="秒",
            min_value=1,
            max_value=3600,
            effect="new_tasks_only",
        ),
        ConfigItemSpec(
            key="atm.cleanup_hook_timeout_seconds",
            label="Cleanup Hook 超时",
            value_type="int",
            default=300,
            domain="atm",
            section="finalization",
            unit="秒",
            min_value=1,
            max_value=3600,
            effect="new_tasks_only",
        ),
        ConfigItemSpec(
            key="atm.env_action_timeout_seconds",
            label="环境动作超时",
            value_type="int",
            default=60,
            domain="atm",
            section="finalization",
            unit="秒",
            min_value=1,
            max_value=3600,
            effect="new_tasks_only",
        ),
        ConfigItemSpec(
            key="logging.level",
            label="日志级别",
            value_type="enum",
            default="INFO",
            domain="resources",
            section="logging",
            choices=(
                ConfigChoice("DEBUG", "调试"),
                ConfigChoice("INFO", "信息"),
                ConfigChoice("WARNING", "警告"),
                ConfigChoice("ERROR", "错误"),
            ),
        ),
        ConfigItemSpec(
            key="logging.retention_days",
            label="日志保留",
            value_type="int",
            default=29,
            domain="resources",
            section="logging",
            unit="天",
            min_value=1,
            max_value=365,
        ),
        ConfigItemSpec(
            key="rem.max_instances",
            label="最大环境实例数",
            value_type="int",
            default=50,
            domain="resources",
            section="rem",
            min_value=1,
            max_value=1000,
            effect="restart_required",
        ),
    ),
)


class ConfigCenterService(QObject):
    """Host-wide config center backed by config.db.config_entries."""

    config_changed = pyqtSignal(str, object, str)

    def __init__(self, registry: ConfigRegistry = DEFAULT_CONFIG_REGISTRY, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.registry = registry

    def get(self, key: str) -> Any:
        return self.get_value(key).value

    def get_value(self, key: str) -> ConfigValue:
        spec = self.registry.get_item(key)
        stored = self._read_storage_value(spec.storage_namespace(), spec.storage_key_path())
        if stored is None:
            return ConfigValue(spec=spec, value=spec.default, source="default")
        try:
            value = json.loads(stored["value_json"])
            return ConfigValue(spec=spec, value=self._coerce_value(spec, value), source="stored")
        except Exception:
            return ConfigValue(spec=spec, value=spec.default, source="default")

    def set(self, key: str, value: Any) -> None:
        spec = self.registry.get_item(key)
        normalized = self._validate_value(spec, value)
        self._write_storage_value(
            spec.storage_namespace(),
            spec.storage_key_path(),
            normalized,
            self._infer_value_type(normalized, spec.value_type),
        )
        self.config_changed.emit(spec.key, normalized, spec.effect)

    def reset(self, key: str) -> bool:
        spec = self.registry.get_item(key)
        deleted = self.delete_internal(spec.storage_namespace(), spec.storage_key_path())
        if deleted:
            self.config_changed.emit(spec.key, spec.default, spec.effect)
        return deleted

    def reset_domain(self, domain: str) -> int:
        count = 0
        for spec in self.registry.list_items(domain=domain):
            count += int(self.reset(spec.key))
        return count

    def list_values(self, *, domain: str | None = None) -> list[ConfigValue]:
        return [self.get_value(item.key) for item in self.registry.list_items(domain=domain)]

    def get_internal(self, namespace: str, key_path: str, default: Any = None) -> Any:
        stored = self._read_storage_value(namespace, key_path)
        if stored is None:
            return default
        return json.loads(stored["value_json"])

    def set_internal(self, namespace: str, key_path: str, value: Any) -> None:
        self._write_storage_value(namespace, key_path, value, self._infer_value_type(value))

    def delete_internal(self, namespace: str, key_path: str) -> bool:
        with get_connection(CONFIG_DB) as conn:
            cursor = conn.execute(
                """
                DELETE FROM config_entries
                WHERE namespace = ? AND scope_type = 'global' AND scope_name = '' AND key_path = ?
                """,
                (namespace, key_path),
            )
        return bool(cursor.rowcount)

    def _read_storage_value(self, namespace: str, key_path: str) -> Any | None:
        with get_connection(CONFIG_DB) as conn:
            return conn.execute(
                """
                SELECT value_json, value_type
                FROM config_entries
                WHERE namespace = ? AND scope_type = 'global' AND scope_name = '' AND key_path = ?
                """,
                (namespace, key_path),
            ).fetchone()

    def _write_storage_value(self, namespace: str, key_path: str, value: Any, value_type: str) -> None:
        now = int(time.time())
        with get_connection(CONFIG_DB) as conn:
            conn.execute(
                """
                INSERT INTO config_entries (
                    namespace, scope_type, scope_name, key_path, value_json, value_type, updated_at
                ) VALUES (?, 'global', '', ?, ?, ?, ?)
                ON CONFLICT(namespace, scope_type, scope_name, key_path) DO UPDATE SET
                    value_json = excluded.value_json,
                    value_type = excluded.value_type,
                    updated_at = excluded.updated_at
                """,
                (namespace, key_path, json.dumps(value, ensure_ascii=False), value_type, now),
            )

    def _validate_value(self, spec: ConfigItemSpec, value: Any) -> Any:
        normalized = self._coerce_value(spec, value)
        if spec.choices:
            allowed = {choice.value for choice in spec.choices}
            if normalized not in allowed:
                raise ConfigValidationError(f"{spec.key} must be one of {sorted(allowed)!r}")
        if isinstance(normalized, (int, float)) and not isinstance(normalized, bool):
            if spec.min_value is not None and normalized < spec.min_value:
                raise ConfigValidationError(f"{spec.key} must be >= {spec.min_value}")
            if spec.max_value is not None and normalized > spec.max_value:
                raise ConfigValidationError(f"{spec.key} must be <= {spec.max_value}")
        return normalized

    def _coerce_value(self, spec: ConfigItemSpec, value: Any) -> Any:
        if spec.value_type == "bool":
            return bool(value)
        if spec.value_type == "int":
            if isinstance(value, bool):
                raise ConfigValidationError(f"{spec.key} must be an integer")
            return int(value)
        if spec.value_type == "float":
            if isinstance(value, bool):
                raise ConfigValidationError(f"{spec.key} must be a number")
            return float(value)
        return str(value or "") if value is not None else ""

    def _infer_value_type(self, value: Any, fallback: str | None = None) -> str:
        if fallback in {"secret", "path", "enum"}:
            return "string"
        if fallback:
            return fallback
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int) and not isinstance(value, bool):
            return "int"
        if isinstance(value, float):
            return "float"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return "string"


_config_center: ConfigCenterService | None = None


def get_config_center() -> ConfigCenterService:
    global _config_center
    if _config_center is None:
        _config_center = ConfigCenterService()
    return _config_center

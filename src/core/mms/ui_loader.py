"""MMS 自定义页面加载与 trust gate。"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtWidgets import QWidget

from src.core.foundation.logging import logger
from src.core.mms.models import ModuleInfo, ModuleSource
from src.core.persistence import get_config_store

UI_ALLOWLIST_KEY = "mms.ui.allowlist"


class ModuleUIAccessDenied(RuntimeError):
    """模块 UI 未通过 trust gate。"""


class ModuleUILoadError(RuntimeError):
    """模块 UI 加载失败。"""


@dataclass(slots=True)
class ModuleUITrustDecision:
    allowed: bool
    reason: str = ""


class ModuleCustomPageLoader:
    """代码型模块页面加载器。"""

    def __init__(self):
        self._config_store = get_config_store()

    def _get_allowlist(self) -> set[str]:
        raw = self._config_store.get_setting(UI_ALLOWLIST_KEY)
        if not raw:
            return set()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("[MMS] UI allowlist 配置不是合法 JSON，已忽略")
            return set()

        if not isinstance(parsed, list):
            logger.warning("[MMS] UI allowlist 应为 JSON 数组，已忽略")
            return set()

        return {str(item).strip() for item in parsed if str(item).strip()}

    def evaluate_trust(self, module: ModuleInfo, entry: str) -> ModuleUITrustDecision:
        entry = entry.strip()

        if entry.startswith("core:data_table:"):
            return ModuleUITrustDecision(True)

        if not entry.startswith("ui:"):
            return ModuleUITrustDecision(False, f"不支持的自定义页面入口: {entry}")

        if module.manifest.ui_extension.type != "micro_app":
            return ModuleUITrustDecision(
                False,
                "只有 `ui_extension.type = micro_app` 的模块才允许加载 `ui:*` 页面",
            )

        if module.source in {ModuleSource.BUILTIN, ModuleSource.DEV_LINK}:
            return ModuleUITrustDecision(True)

        if module.name in self._get_allowlist():
            return ModuleUITrustDecision(True)

        if module.manifest.ui_extension.trusted:
            return ModuleUITrustDecision(
                False,
                "模块虽声明 `trusted: true`，但当前实现仍要求外部模块命中 `mms.ui.allowlist` 才允许加载代码 UI",
            )

        return ModuleUITrustDecision(
            False,
            "外部模块代码 UI 未通过 trust gate，请将模块名加入系统设置 `mms.ui.allowlist` 后重试",
        )

    def load_widget(self, module: ModuleInfo, entry: str) -> QWidget:
        decision = self.evaluate_trust(module, entry)
        if not decision.allowed:
            raise ModuleUIAccessDenied(decision.reason)

        if entry.startswith("core:data_table:"):
            raise ModuleUILoadError("core:data_table 页面应由调用方单独处理")

        widget_name = entry.split(":", 1)[1].strip()
        if not widget_name:
            raise ModuleUILoadError(f"无效的自定义页面入口: {entry}")

        ui_module = self._load_ui_module(module)
        widget_cls = getattr(ui_module, widget_name, None)
        if widget_cls is None:
            raise ModuleUILoadError(f"`{module.name}.ui` 中未找到页面类 `{widget_name}`")

        widget = self._instantiate_widget(widget_cls, module)
        if not isinstance(widget, QWidget):
            raise ModuleUILoadError(f"`{widget_name}` 实例化后不是 QWidget")

        return widget

    def _instantiate_widget(self, widget_cls, module: ModuleInfo) -> QWidget:
        try:
            return widget_cls(module)
        except TypeError:
            try:
                return widget_cls()
            except TypeError as exc:
                raise ModuleUILoadError(
                    f"`{widget_cls.__name__}` 的构造函数不受支持，请使用 `__init__()` 或 `__init__(module)`"
                ) from exc

    def _purge_module_namespace(self, module_name: str) -> None:
        prefix = f"{module_name}."
        for loaded_name in list(sys.modules):
            if loaded_name == module_name or loaded_name.startswith(prefix):
                sys.modules.pop(loaded_name, None)

    def _load_root_module_from_path(self, module_name: str, module_path: Path):
        package_root = Path(module_path).resolve()
        package_init = package_root / "__init__.py"
        if not package_init.exists():
            raise ModuleUILoadError(f"模块目录缺少 __init__.py: {package_root}")

        existing = sys.modules.get(module_name)
        existing_file = getattr(existing, "__file__", "") if existing else ""
        same_origin = bool(existing_file) and Path(existing_file).resolve() == package_init

        if existing and not same_origin:
            self._purge_module_namespace(module_name)
        elif same_origin:
            return existing

        importlib.invalidate_caches()
        spec = importlib.util.spec_from_file_location(
            module_name,
            package_init,
            submodule_search_locations=[str(package_root)],
        )
        if spec is None or spec.loader is None:
            raise ModuleUILoadError(f"无法从 `{package_root}` 构建模块加载规格")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    def _load_ui_module(self, module: ModuleInfo):
        if not module.path:
            raise ModuleUILoadError(f"模块 `{module.name}` 没有可用路径")

        self._load_root_module_from_path(module.name, Path(module.path))
        importlib.invalidate_caches()

        try:
            return importlib.import_module(f"{module.name}.ui")
        except Exception as exc:
            raise ModuleUILoadError(f"导入 `{module.name}.ui` 失败: {exc}") from exc


_custom_page_loader: ModuleCustomPageLoader | None = None


def get_module_custom_page_loader() -> ModuleCustomPageLoader:
    global _custom_page_loader
    if _custom_page_loader is None:
        _custom_page_loader = ModuleCustomPageLoader()
    return _custom_page_loader

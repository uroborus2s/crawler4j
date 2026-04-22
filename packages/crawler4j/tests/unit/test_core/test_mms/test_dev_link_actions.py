from types import SimpleNamespace

from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource
from src.core.mms.ui.dev_link_actions import remove_dev_link_and_describe


def test_remove_dev_link_and_describe_reports_plain_removal_without_fallback(monkeypatch):
    monkeypatch.setattr(
        "src.core.mms.ui.dev_link_actions.get_module_registry",
        lambda: SimpleNamespace(
            remove_dev_link=lambda name: name == "demo_module",
            get_module=lambda name: None,
        ),
    )

    result = remove_dev_link_and_describe("demo_module")

    assert result.fallback is None
    assert result.title == "已移除"
    assert result.message == "已移除开发链接: demo_module"


def test_remove_dev_link_and_describe_reports_builtin_fallback(monkeypatch):
    fallback = ModuleInfo(
        name="demo_module",
        manifest=ModuleManifest(name="demo_module", display_name="Demo Module"),
        source=ModuleSource.BUILTIN,
        path=None,
    )
    monkeypatch.setattr(
        "src.core.mms.ui.dev_link_actions.get_module_registry",
        lambda: SimpleNamespace(
            remove_dev_link=lambda name: name == "demo_module",
            get_module=lambda name: fallback if name == "demo_module" else None,
        ),
    )

    result = remove_dev_link_and_describe("demo_module")

    assert result.fallback is fallback
    assert result.title == "已切换"
    assert result.message == "已移除开发链接，当前已回退到 内置模块: demo_module"

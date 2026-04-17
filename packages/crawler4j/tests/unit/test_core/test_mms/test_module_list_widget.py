from pathlib import Path
from types import SimpleNamespace

from PyQt6.QtWidgets import QMessageBox, QPushButton

from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource
from src.core.mms.release_service import ModuleUpdateInfo
from src.core.mms.ui.module_list_widget import ModuleListWidget


def _make_module(tmp_path: Path, *, source: ModuleSource) -> ModuleInfo:
    module_dir = tmp_path / source.value / "demo_module"
    module_dir.mkdir(parents=True, exist_ok=True)
    return ModuleInfo(
        name="demo_module",
        manifest=ModuleManifest(name="demo_module", display_name="Demo Module"),
        source=source,
        path=module_dir,
    )


def test_refresh_button_forces_registry_refresh(qtbot, tmp_path, monkeypatch):
    module = _make_module(tmp_path, source=ModuleSource.DEV_LINK)
    refresh_calls: list[int] = []
    registry = SimpleNamespace(
        refresh=lambda: refresh_calls.append(1),
        list_modules=lambda: [module],
    )

    monkeypatch.setattr("src.core.mms.ui.module_list_widget.get_module_registry", lambda: registry)

    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    widget.refresh_btn.click()

    assert refresh_calls == [1]


def test_dev_link_row_uses_remove_action(qtbot, tmp_path):
    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    action_widget = widget._create_action_widget(_make_module(tmp_path, source=ModuleSource.DEV_LINK))
    texts = [button.text() for button in action_widget.findChildren(QPushButton)]

    assert "移除开发链接" in texts
    assert "🗑️" not in texts


def test_remove_dev_link_calls_registry_and_refreshes(qtbot, tmp_path, monkeypatch):
    module = _make_module(tmp_path, source=ModuleSource.DEV_LINK)
    remove_calls: list[str] = []
    refresh_calls: list[int] = []
    registry = SimpleNamespace(
        refresh=lambda: refresh_calls.append(1),
        list_modules=lambda: [module],
        remove_dev_link=lambda name: remove_calls.append(name) or True,
        get_module=lambda name: None,
    )

    monkeypatch.setattr("src.core.mms.ui.module_list_widget.get_module_registry", lambda: registry)
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.QMessageBox.question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )
    info_messages: list[str] = []
    monkeypatch.setattr(
        "src.core.mms.ui.module_list_widget.QMessageBox.information",
        lambda *args: info_messages.append(args[2]),
    )

    widget = ModuleListWidget()
    qtbot.addWidget(widget)
    widget._remove_dev_link("demo_module")

    assert remove_calls == ["demo_module"]
    assert refresh_calls == [1]
    assert any("已移除开发链接" in message for message in info_messages)


def test_external_module_row_shows_upgrade_button_when_update_available(qtbot, tmp_path):
    widget = ModuleListWidget()
    qtbot.addWidget(widget)

    module = _make_module(tmp_path, source=ModuleSource.EXTERNAL)
    widget._update_states[module.name] = ModuleUpdateInfo(
        module_name=module.name,
        current_version="1.0.0",
        latest_version="1.1.0",
        has_update=True,
    )

    action_widget = widget._create_action_widget(module)
    texts = [button.text() for button in action_widget.findChildren(QPushButton)]

    assert "升级" in texts

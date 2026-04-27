from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import src.core.system.velopack as velopack


def _write_update_config(bundle_dir: Path) -> None:
    (bundle_dir / velopack.UPDATE_CONFIG_FILENAME).write_text(
        json.dumps({"feed_url": "https://updates.example.com/win/releases.win.json"}, ensure_ascii=False),
        encoding="utf-8",
    )


def _patch_windows_runtime(monkeypatch: pytest.MonkeyPatch, executable: Path) -> None:
    monkeypatch.setattr(velopack.sys, "platform", "win32")
    monkeypatch.setattr(velopack.sys, "frozen", True, raising=False)
    monkeypatch.setattr(velopack.sys, "executable", str(executable))


def _fake_velopack_module() -> SimpleNamespace:
    class FakeUpdateManager:
        def __init__(self, feed_url: str):
            self.feed_url = feed_url

        def check_for_updates(self):
            return None

        def download_updates(self, _update_info):
            return None

        def apply_updates_and_restart(self, _update_info):
            return None

    return SimpleNamespace(UpdateManager=FakeUpdateManager)


def test_velopack_availability_accepts_installed_layout_without_is_installed_attr(tmp_path, monkeypatch):
    install_root = tmp_path / "io.github.uroborus2s.crawler4j"
    bundle_dir = install_root / "current"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "Crawler4j.exe").write_text("", encoding="utf-8")
    (bundle_dir / "sq.version").write_text("0.3.1", encoding="utf-8")
    (install_root / "Update.exe").write_text("", encoding="utf-8")
    _write_update_config(bundle_dir)
    _patch_windows_runtime(monkeypatch, bundle_dir / "Crawler4j.exe")
    monkeypatch.setattr(velopack, "_load_velopack_module", _fake_velopack_module)

    availability = velopack.velopack_availability()

    assert availability.supported is True
    assert availability.reason == ""


def test_velopack_availability_accepts_portable_layout_without_is_installed_attr(tmp_path, monkeypatch):
    bundle_dir = tmp_path / "portable"
    current_dir = bundle_dir / "current"
    current_dir.mkdir(parents=True)
    (bundle_dir / "Crawler4j.exe").write_text("", encoding="utf-8")
    (bundle_dir / "Update.exe").write_text("", encoding="utf-8")
    (current_dir / "sq.version").write_text("0.3.1", encoding="utf-8")
    _write_update_config(bundle_dir)
    _patch_windows_runtime(monkeypatch, bundle_dir / "Crawler4j.exe")
    monkeypatch.setattr(velopack, "_load_velopack_module", _fake_velopack_module)

    availability = velopack.velopack_availability()

    assert availability.supported is True
    assert availability.reason == ""


def test_velopack_availability_rejects_bare_bundle_without_release_layout(tmp_path, monkeypatch):
    bundle_dir = tmp_path / "Crawler4j"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "Crawler4j.exe").write_text("", encoding="utf-8")
    _write_update_config(bundle_dir)
    _patch_windows_runtime(monkeypatch, bundle_dir / "Crawler4j.exe")
    monkeypatch.setattr(velopack, "_load_velopack_module", _fake_velopack_module)

    availability = velopack.velopack_availability()

    assert availability.supported is False
    assert availability.reason == "当前 Windows 包不是 Velopack 正式发布产物，不能执行宿主自更新。"


def test_velopack_updater_accepts_installed_layout_without_is_installed_attr(tmp_path, monkeypatch):
    install_root = tmp_path / "io.github.uroborus2s.crawler4j"
    bundle_dir = install_root / "current"
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "Crawler4j.exe").write_text("", encoding="utf-8")
    (bundle_dir / "sq.version").write_text("0.3.1", encoding="utf-8")
    (install_root / "Update.exe").write_text("", encoding="utf-8")
    _write_update_config(bundle_dir)
    _patch_windows_runtime(monkeypatch, bundle_dir / "Crawler4j.exe")
    monkeypatch.setattr(velopack, "_load_velopack_module", _fake_velopack_module)

    updater = velopack.VelopackUpdater()

    assert updater.can_check_for_updates() is True

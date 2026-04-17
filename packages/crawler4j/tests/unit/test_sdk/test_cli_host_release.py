"""Unit tests for release/host commands in the refactored crawler4j SDK CLI."""

from __future__ import annotations

import subprocess
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

from crawler4j_sdk.cli import commands


def _make_manifest(repo: str = "demo/demo_model", version: str = "0.1.0"):
    return {
        "name": "demo_model",
        "version": version,
        "display_name": "Demo Model",
        "description": "Demo Model 模块",
        "upgrade_source": {
            "type": "github_release",
            "repo": repo,
            "allow_prerelease": False,
        },
        "config_defaults": {
            "module": {},
            "workflows": {},
        },
        "workflows": [
            {
                "name": "main_workflow",
                "display_name": "Main Workflow",
                "description": "Main Workflow 工作流",
            }
        ],
    }


def _fake_module(path: Path, *, name: str = "demo_model", version: str = "0.1.0", source: str = "external"):
    return SimpleNamespace(
        name=name,
        path=path,
        source=SimpleNamespace(value=source),
        manifest=SimpleNamespace(
            name=name,
            version=version,
            upgrade_source=SimpleNamespace(repo="demo/demo_model", allow_prerelease=False),
        ),
    )


def _fake_runtime(registry, service, ensure_vscode_attach_config=None):
    return {
        "init_database": lambda: None,
        "get_module_registry": lambda: registry,
        "get_module_release_service": lambda: service,
        "ensure_vscode_attach_config": ensure_vscode_attach_config
        or (lambda source_path, *, host, port, configuration_name: Path(source_path) / ".vscode" / "launch.json"),
    }


def test_release_publish_uses_gh_release_create(monkeypatch, tmp_path: Path):
    module_root = tmp_path / "demo_model"
    module_root.mkdir()
    (module_root / "module.yaml").write_text(
        commands.yaml.safe_dump(_make_manifest(), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    archive_dir = module_root / "dist"
    archive_dir.mkdir()
    archive_path = archive_dir / "demo_model-0.1.0.zip"
    archive_path.write_text("fake zip", encoding="utf-8")

    monkeypatch.chdir(module_root)
    monkeypatch.setattr(commands, "cmd_package_verify", lambda args: 0)

    calls: list[list[str]] = []

    def fake_run(cmd, check=False, capture_output=False, text=False):
        calls.append(list(cmd))
        if cmd[:3] == ["gh", "release", "view"]:
            return subprocess.CompletedProcess(cmd, 1, "", "not found")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(commands.subprocess, "run", fake_run)

    result = commands.cmd_release_publish(
        Namespace(
            archive=None,
            tag=None,
            title=None,
            notes=None,
            notes_file=None,
            prerelease=False,
            rebuild=False,
            dry_run=False,
        )
    )

    assert result == 0
    assert calls[0][:3] == ["gh", "release", "view"]
    assert calls[1][:3] == ["gh", "release", "create"]
    assert calls[1][3] == "v0.1.0"


def test_fetch_latest_release_adds_authorization_header(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return commands.json.dumps(
                [
                    {
                        "tag_name": "v1.2.0",
                        "name": "v1.2.0",
                        "draft": False,
                        "prerelease": False,
                        "assets": [
                            {
                                "name": "demo_model-1.2.0.zip",
                                "browser_download_url": "https://example.com/demo_model-1.2.0.zip",
                                "url": "https://api.github.com/repos/demo/demo_model/releases/assets/1",
                            }
                        ],
                        "html_url": "https://github.com/demo/demo_model/releases/tag/v1.2.0",
                    }
                ]
            ).encode("utf-8")

    def fake_urlopen(request, timeout=0):  # noqa: ARG001
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        return FakeResponse()

    monkeypatch.setattr(commands.urllib.request, "urlopen", fake_urlopen)

    payload = commands._fetch_latest_release("demo/demo_model", github_token="cli-token")

    assert payload["version"] == "1.2.0"
    assert payload["asset_api_url"] == "https://api.github.com/repos/demo/demo_model/releases/assets/1"
    assert captured["url"] == "https://api.github.com/repos/demo/demo_model/releases"
    assert captured["headers"]["Authorization"] == "Bearer cli-token"


def test_release_check_remote_treats_stable_as_newer_than_prerelease(
    monkeypatch, tmp_path: Path, capsys
):
    module_root = tmp_path / "demo_model"
    module_root.mkdir()

    monkeypatch.setattr(commands, "require_module_root", lambda: module_root)
    monkeypatch.setattr(
        commands,
        "load_manifest",
        lambda root: _make_manifest(version="1.2.0-rc.1"),
    )
    monkeypatch.setattr(
        commands,
        "_fetch_latest_release",
        lambda repo, allow_prerelease=False, github_token=None: {
            "version": "1.2.0",
            "title": "v1.2.0",
            "tag_name": "v1.2.0",
            "asset_name": "demo_model-1.2.0.zip",
        },
    )

    result = commands.cmd_release_check_remote(Namespace(github_token=None))

    captured = capsys.readouterr()
    assert result == 0
    assert "状态: behind" in captured.out


def test_release_check_remote_prefers_explicit_github_token(monkeypatch, tmp_path: Path):
    module_root = tmp_path / "demo_model"
    module_root.mkdir()
    captured: list[tuple[str, bool, str | None]] = []

    monkeypatch.setattr(commands, "require_module_root", lambda: module_root)
    monkeypatch.setattr(commands, "load_manifest", lambda root: _make_manifest(version="1.0.0"))
    monkeypatch.setattr(
        commands,
        "_fetch_latest_release",
        lambda repo, allow_prerelease=False, github_token=None: (
            captured.append((repo, allow_prerelease, github_token))
            or {
                "version": "1.0.0",
                "title": "v1.0.0",
                "tag_name": "v1.0.0",
                "asset_name": "demo_model-1.0.0.zip",
            }
        ),
    )
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")

    result = commands.cmd_release_check_remote(Namespace(github_token="explicit-token"))

    assert result == 0
    assert captured == [("demo/demo_model", False, "explicit-token")]


def test_host_devlink_commands_delegate_to_registry(monkeypatch, tmp_path: Path):
    calls: list[tuple[str, object]] = []
    module = _fake_module(tmp_path / "demo_model", source="dev_link")

    class FakeRegistry:
        def register_dev_link(self, source_path):
            calls.append(("register", Path(source_path)))
            return module

        def remove_dev_link(self, module_name):
            calls.append(("remove", module_name))
            return True

        def list_dev_links(self):
            return [SimpleNamespace(module_name="demo_model", source_path=str(tmp_path / "demo_model"))]

    monkeypatch.setattr(commands, "_load_host_runtime", lambda: _fake_runtime(FakeRegistry(), object()))

    assert commands.cmd_host_devlink_add(Namespace(module_root=str(tmp_path / "demo_model"))) == 0
    assert commands.cmd_host_devlink_list(Namespace()) == 0
    assert commands.cmd_host_devlink_remove(Namespace(module_name="demo_model")) == 0
    assert calls == [
        ("register", (tmp_path / "demo_model").resolve()),
        ("remove", "demo_model"),
    ]


def test_host_install_preview_and_apply_support_local_zip_skip_remote(monkeypatch, tmp_path: Path):
    archive_path = tmp_path / "demo_model-0.1.0.zip"
    archive_path.write_text("fake zip", encoding="utf-8")
    calls: list[tuple[str, object]] = []
    module = _fake_module(tmp_path / "installed_demo")

    class FakeRegistry:
        def validate_source(self, source):
            calls.append(("validate", Path(source)))
            return (
                SimpleNamespace(
                    name="demo_model",
                    version="0.1.0",
                    upgrade_source=SimpleNamespace(repo="demo/demo_model"),
                ),
                ["warn"],
            )

        def install(self, source):
            calls.append(("install", Path(source)))
            return module

    monkeypatch.setattr(commands, "_load_host_runtime", lambda: _fake_runtime(FakeRegistry(), object()))

    assert commands.cmd_host_install_preview(
        Namespace(source=str(archive_path), skip_remote_check=True)
    ) == 0
    assert commands.cmd_host_install_apply(
        Namespace(source=str(archive_path), skip_remote_check=True)
    ) == 0
    assert calls == [
        ("validate", archive_path.resolve()),
        ("install", archive_path.resolve()),
    ]


def test_host_install_preview_passes_github_token(monkeypatch, tmp_path: Path):
    calls: list[tuple[str, object, object]] = []

    class FakeRegistry:
        def validate_source(self, source):  # pragma: no cover - should not be used
            raise AssertionError(source)

    class FakeService:
        async def prepare_github_install(self, repo_input, *, github_token=None):
            calls.append(("prepare_github_install", repo_input, github_token))
            return SimpleNamespace(
                source_label="GitHub Release",
                manifest=SimpleNamespace(
                    name="demo_model",
                    version="0.2.0",
                    upgrade_source=SimpleNamespace(repo="demo/demo_model"),
                ),
                warnings=[],
                archive_path=tmp_path / "demo_model-0.2.0.zip",
                release=SimpleNamespace(version="0.2.0", html_url="https://example.com/release"),
            )

    monkeypatch.setattr(commands, "_load_host_runtime", lambda: _fake_runtime(FakeRegistry(), FakeService()))

    result = commands.cmd_host_install_preview(
        Namespace(source="demo/demo_model", skip_remote_check=False, github_token="host-token")
    )

    assert result == 0
    assert calls == [("prepare_github_install", "demo/demo_model", "host-token")]


def test_host_upgrade_commands_delegate_to_release_service(monkeypatch, tmp_path: Path):
    archive_path = tmp_path / "demo_model-0.2.0.zip"
    module = _fake_module(tmp_path / "installed_demo")
    installed = _fake_module(tmp_path / "installed_demo", version="0.2.0")
    calls: list[tuple[str, object]] = []

    class FakeRegistry:
        def get_module(self, module_name):
            calls.append(("get_module", module_name))
            return module

        def install(self, source):
            calls.append(("install", Path(source)))
            return installed

    class FakeService:
        async def check_for_update(self, module_info, *, github_token=None):
            calls.append(("check_for_update", module_info.name, github_token))
            return SimpleNamespace(
                module_name=module_info.name,
                current_version="0.1.0",
                latest_version="0.2.0",
                has_update=True,
                release=SimpleNamespace(html_url="https://example.com/release", asset_name="demo_model-0.2.0.zip"),
                error="",
            )

        async def prepare_module_upgrade(self, module_info, *, github_token=None):
            calls.append(("prepare_module_upgrade", module_info.name, github_token))
            return SimpleNamespace(
                source_label="GitHub Release",
                manifest=SimpleNamespace(
                    name=module_info.name,
                    version="0.2.0",
                    upgrade_source=SimpleNamespace(repo="demo/demo_model"),
                ),
                warnings=[],
                archive_path=archive_path,
                release=SimpleNamespace(version="0.2.0", html_url="https://example.com/release"),
            )

        async def apply_module_upgrade(self, module_info, preview):
            calls.append(("apply_module_upgrade", module_info.name, Path(preview.archive_path)))
            return installed

    monkeypatch.setattr(commands, "_load_host_runtime", lambda: _fake_runtime(FakeRegistry(), FakeService()))

    assert commands.cmd_host_upgrade_check(Namespace(module_name="demo_model", github_token="upgrade-token")) == 0
    assert commands.cmd_host_upgrade_preview(Namespace(module_name="demo_model", github_token="upgrade-token")) == 0
    assert commands.cmd_host_upgrade_apply(Namespace(module_name="demo_model", github_token="upgrade-token")) == 0
    assert calls == [
        ("get_module", "demo_model"),
        ("check_for_update", "demo_model", "upgrade-token"),
        ("get_module", "demo_model"),
        ("prepare_module_upgrade", "demo_model", "upgrade-token"),
        ("get_module", "demo_model"),
        ("prepare_module_upgrade", "demo_model", "upgrade-token"),
        ("apply_module_upgrade", "demo_model", archive_path),
    ]


def test_host_debug_config_delegates_to_vscode_helper(monkeypatch, tmp_path: Path):
    calls: list[tuple[Path, str, int, str]] = []
    expected_path = tmp_path / ".vscode" / "launch.json"

    def fake_ensure(source_path, *, host, port, configuration_name):
        calls.append((Path(source_path), host, port, configuration_name))
        return expected_path

    monkeypatch.setattr(
        commands,
        "_load_host_runtime",
        lambda: _fake_runtime(object(), object(), ensure_vscode_attach_config=fake_ensure),
    )

    result = commands.cmd_host_debug_config(
        Namespace(
            module_root=str(tmp_path),
            host="127.0.0.1",
            port=6789,
            configuration_name="Attach Test",
        )
    )

    assert result == 0
    assert calls == [(tmp_path.resolve(), "127.0.0.1", 6789, "Attach Test")]

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource, UpgradeSourceInfo
from src.core.mms.release_service import ModulePackagePreview, ModuleReleaseInfo, ModuleReleaseService


def _make_module(tmp_path: Path, *, version: str = "1.0.0", repo: str = "example/demo_module") -> ModuleInfo:
    module_dir = tmp_path / "modules" / "demo_module"
    module_dir.mkdir(parents=True, exist_ok=True)
    return ModuleInfo(
        name="demo_module",
        manifest=ModuleManifest(
            name="demo_module",
            version=version,
            upgrade_source=UpgradeSourceInfo(repo=repo),
        ),
        source=ModuleSource.EXTERNAL,
        path=module_dir,
    )


def test_normalize_repo_accepts_owner_repo_and_github_url():
    assert ModuleReleaseService.normalize_repo("example/demo") == "example/demo"
    assert (
        ModuleReleaseService.normalize_repo("https://github.com/example/demo/releases/latest")
        == "example/demo"
    )


def test_normalize_repo_rejects_non_github_url():
    with pytest.raises(ValueError):
        ModuleReleaseService.normalize_repo("https://gitlab.com/example/demo")


def test_compare_versions_treats_stable_as_newer_than_prerelease():
    service = ModuleReleaseService()

    assert service._compare_versions("1.2.0", "1.2.0-rc.1") > 0
    assert service._compare_versions("1.2.0-rc.2", "1.2.0-rc.1") > 0
    assert service._compare_versions("1.2.0-rc.1", "1.2.0-rc.1") == 0


@pytest.mark.asyncio
async def test_prepare_dev_link_warns_when_repo_check_fails_but_still_returns_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    service = ModuleReleaseService()
    module_dir = tmp_path / "demo_module"
    module_dir.mkdir(parents=True, exist_ok=True)
    manifest = ModuleManifest(
        name="demo_module",
        version="1.0.0",
        upgrade_source=UpgradeSourceInfo(repo="example/demo_module"),
    )
    registry = SimpleNamespace(validate_source=lambda path: (manifest, ["base warning"]))

    async def fake_repo(repo: str, *, github_token: str | None = None) -> dict[str, str]:  # noqa: ARG001
        raise ValueError(f"GitHub 请求失败 (404): {repo}")

    monkeypatch.setattr("src.core.mms.release_service.get_module_registry", lambda: registry)
    monkeypatch.setattr(service, "_fetch_repo_metadata", fake_repo)

    resolved_manifest, warnings = await service.prepare_dev_link(module_dir)

    assert resolved_manifest is manifest
    assert resolved_manifest.upgrade_source.repo == "example/demo_module"
    assert warnings == [
        "base warning",
        "GitHub 仓库可达性检查失败，已跳过远端预检: GitHub 请求失败 (404): example/demo_module",
    ]


@pytest.mark.asyncio
async def test_request_json_raises_value_error_without_logger_signature_crash(
    monkeypatch: pytest.MonkeyPatch,
):
    service = ModuleReleaseService()
    warning_messages: list[str] = []

    class FakeResponse:
        status = 404

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return {"message": "Not Found"}

        async def text(self):
            return "Not Found"

    class FakeSession:
        def get(self, url: str, **kwargs):  # noqa: ARG002
            return FakeResponse()

    async def fake_get_session():
        return FakeSession()

    monkeypatch.setattr("src.core.mms.release_service.AsyncHttpClient.get_session", fake_get_session)
    monkeypatch.setattr("src.core.mms.release_service.AsyncHttpClient._get_proxy", lambda: None)
    monkeypatch.setattr("src.core.mms.release_service.logger.warning", lambda message: warning_messages.append(message))

    with pytest.raises(ValueError) as exc_info:
        await service._request_json("https://api.github.com/repos/example/demo_module")

    assert str(exc_info.value) == "GitHub 请求失败 (404): Not Found"
    assert warning_messages == [
        "[MMS] GitHub API request failed: 404 https://api.github.com/repos/example/demo_module Not Found"
    ]


@pytest.mark.asyncio
async def test_request_json_adds_authorization_header_from_repo_store(
    monkeypatch: pytest.MonkeyPatch,
):
    service = ModuleReleaseService()
    captured: dict[str, Any] = {}

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def json(self):
            return {"ok": True}

    class FakeSession:
        def get(self, url: str, **kwargs):
            captured["url"] = url
            captured["headers"] = dict(kwargs.get("headers", {}))
            return FakeResponse()

    async def fake_get_session():
        return FakeSession()

    monkeypatch.setattr("src.core.mms.release_service.AsyncHttpClient.get_session", fake_get_session)
    monkeypatch.setattr("src.core.mms.release_service.AsyncHttpClient._get_proxy", lambda: None)
    monkeypatch.setattr(
        "src.core.mms.release_service.get_github_credential_store",
        lambda: SimpleNamespace(get_token=lambda repo: "stored-token"),  # noqa: ARG005
    )

    payload = await service._request_json(
        "https://api.github.com/repos/example/demo_module",
        repo="example/demo_module",
    )

    assert payload == {"ok": True}
    assert captured["url"] == "https://api.github.com/repos/example/demo_module"
    assert captured["headers"]["Authorization"] == "Bearer stored-token"


@pytest.mark.asyncio
async def test_download_release_asset_uses_asset_api_url_with_authorization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    service = ModuleReleaseService()
    release = ModuleReleaseInfo(
        repo="example/demo_module",
        tag_name="v1.2.0",
        version="1.2.0",
        title="v1.2.0",
        release_notes="notes",
        published_at="2026-04-17T00:00:00Z",
        html_url="https://github.com/example/demo_module/releases/tag/v1.2.0",
        asset_name="demo_module-1.2.0.zip",
        asset_download_url="https://github.com/example/demo_module/releases/download/v1.2.0/demo_module-1.2.0.zip",
        asset_api_url="https://api.github.com/repos/example/demo_module/releases/assets/123",
        prerelease=False,
    )
    captured: dict[str, Any] = {}

    class FakeContent:
        async def iter_chunked(self, size: int):  # noqa: ARG002
            yield b"fake zip"

    class FakeResponse:
        status = 200
        content = FakeContent()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeSession:
        def get(self, url: str, **kwargs):
            captured["url"] = url
            captured["headers"] = dict(kwargs.get("headers", {}))
            return FakeResponse()

    async def fake_get_session():
        return FakeSession()

    monkeypatch.setattr("src.core.mms.release_service.AsyncHttpClient.get_session", fake_get_session)
    monkeypatch.setattr("src.core.mms.release_service.AsyncHttpClient._get_proxy", lambda: None)
    monkeypatch.setattr("src.core.mms.release_service.get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        "src.core.mms.release_service.get_github_credential_store",
        lambda: SimpleNamespace(get_token=lambda repo: "stored-download-token"),  # noqa: ARG005
    )

    archive_path = await service._download_release_asset(release)

    assert archive_path.read_bytes() == b"fake zip"
    assert captured["url"] == release.asset_api_url
    assert captured["headers"]["Authorization"] == "Bearer stored-download-token"
    assert captured["headers"]["Accept"] == "application/octet-stream"


@pytest.mark.asyncio
async def test_download_release_asset_wraps_timeout_and_removes_partial_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    service = ModuleReleaseService()
    release = ModuleReleaseInfo(
        repo="example/demo_module",
        tag_name="v1.2.0",
        version="1.2.0",
        title="v1.2.0",
        release_notes="notes",
        published_at="2026-04-17T00:00:00Z",
        html_url="https://github.com/example/demo_module/releases/tag/v1.2.0",
        asset_name="demo_module-1.2.0.zip",
        asset_download_url="https://example.invalid/demo_module-1.2.0.zip",
        asset_api_url="https://api.github.com/repos/example/demo_module/releases/assets/123",
        prerelease=False,
    )

    class FakeContent:
        async def iter_chunked(self, size: int):  # noqa: ARG002
            yield b"partial zip bytes"
            raise asyncio.TimeoutError()

    class FakeResponse:
        status = 200
        content_length = 1024
        content = FakeContent()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeSession:
        def get(self, url: str, **kwargs):  # noqa: ARG002
            return FakeResponse()

    async def fake_get_session():
        return FakeSession()

    monkeypatch.setattr("src.core.mms.release_service.AsyncHttpClient.get_session", fake_get_session)
    monkeypatch.setattr("src.core.mms.release_service.AsyncHttpClient._get_proxy", lambda: None)
    monkeypatch.setattr("src.core.mms.release_service.get_app_data_dir", lambda: tmp_path)

    with pytest.raises(ValueError) as exc_info:
        await service._download_release_asset(release)

    assert "下载模块安装包超时" in str(exc_info.value)
    target_dir = tmp_path / "downloads" / "modules" / "example__demo_module"
    assert list(target_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_download_release_asset_rejects_incomplete_archive_and_removes_partial_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    service = ModuleReleaseService()
    release = ModuleReleaseInfo(
        repo="example/demo_module",
        tag_name="v1.2.0",
        version="1.2.0",
        title="v1.2.0",
        release_notes="notes",
        published_at="2026-04-17T00:00:00Z",
        html_url="https://github.com/example/demo_module/releases/tag/v1.2.0",
        asset_name="demo_module-1.2.0.zip",
        asset_download_url="https://example.invalid/demo_module-1.2.0.zip",
        asset_api_url="https://api.github.com/repos/example/demo_module/releases/assets/123",
        prerelease=False,
    )

    class FakeContent:
        async def iter_chunked(self, size: int):  # noqa: ARG002
            yield b"1234"

    class FakeResponse:
        status = 200
        content_length = 8
        content = FakeContent()

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeSession:
        def get(self, url: str, **kwargs):  # noqa: ARG002
            return FakeResponse()

    async def fake_get_session():
        return FakeSession()

    monkeypatch.setattr("src.core.mms.release_service.AsyncHttpClient.get_session", fake_get_session)
    monkeypatch.setattr("src.core.mms.release_service.AsyncHttpClient._get_proxy", lambda: None)
    monkeypatch.setattr("src.core.mms.release_service.get_app_data_dir", lambda: tmp_path)

    with pytest.raises(ValueError) as exc_info:
        await service._download_release_asset(release)

    assert "下载模块安装包不完整" in str(exc_info.value)
    target_dir = tmp_path / "downloads" / "modules" / "example__demo_module"
    assert list(target_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_prepare_github_install_rejects_manifest_repo_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    service = ModuleReleaseService()

    async def fake_repo(repo: str, *, github_token: str | None = None) -> dict:  # noqa: ARG001
        return {"full_name": repo}

    async def fake_release(
        repo: str,
        *,
        allow_prerelease: bool = False,
        github_token: str | None = None,
    ) -> ModuleReleaseInfo:  # noqa: ARG001
        return ModuleReleaseInfo(
            repo=repo,
            tag_name="v1.2.0",
            version="1.2.0",
            title="v1.2.0",
            release_notes="notes",
            published_at="2026-04-17T00:00:00Z",
            html_url="https://github.com/example/demo/releases/tag/v1.2.0",
            asset_name="demo_module-1.2.0.zip",
            asset_download_url="https://example.invalid/demo_module-1.2.0.zip",
            prerelease=False,
        )

    archive = tmp_path / "demo_module-1.2.0.zip"
    archive.write_bytes(b"zip")

    async def fake_download(*args, **kwargs) -> Path:  # noqa: ARG001
        return archive

    manifest = ModuleManifest(
        name="demo_module",
        version="1.2.0",
        upgrade_source=UpgradeSourceInfo(repo="example/other"),
    )

    monkeypatch.setattr(service, "_fetch_repo_metadata", fake_repo)
    monkeypatch.setattr(service, "_fetch_latest_release", fake_release)
    monkeypatch.setattr(service, "_download_release_asset", fake_download)
    monkeypatch.setattr(service, "_validate_archive", lambda path: (manifest, []))

    with pytest.raises(ValueError) as exc_info:
        await service.prepare_github_install("example/demo")

    assert "仓库不一致" in str(exc_info.value)


@pytest.mark.asyncio
async def test_check_for_update_detects_newer_release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    service = ModuleReleaseService()
    module = _make_module(tmp_path, version="1.0.0")

    async def fake_release(
        repo: str,
        *,
        allow_prerelease: bool = False,
        github_token: str | None = None,
    ) -> ModuleReleaseInfo:  # noqa: ARG001
        return ModuleReleaseInfo(
            repo=repo,
            tag_name="v1.1.0",
            version="1.1.0",
            title="v1.1.0",
            release_notes="notes",
            published_at="2026-04-17T00:00:00Z",
            html_url="https://github.com/example/demo_module/releases/tag/v1.1.0",
            asset_name="demo_module-1.1.0.zip",
            asset_download_url="https://example.invalid/demo_module-1.1.0.zip",
            prerelease=False,
        )

    monkeypatch.setattr(service, "_fetch_latest_release", fake_release)

    result = await service.check_for_update(module)

    assert result.has_update is True
    assert result.current_version == "1.0.0"
    assert result.latest_version == "1.1.0"


@pytest.mark.asyncio
async def test_check_for_update_treats_stable_as_newer_than_prerelease(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    service = ModuleReleaseService()
    module = _make_module(tmp_path, version="1.2.0-rc.1")

    async def fake_release(
        repo: str,
        *,
        allow_prerelease: bool = False,
        github_token: str | None = None,
    ) -> ModuleReleaseInfo:  # noqa: ARG001
        return ModuleReleaseInfo(
            repo=repo,
            tag_name="v1.2.0",
            version="1.2.0",
            title="v1.2.0",
            release_notes="notes",
            published_at="2026-04-17T00:00:00Z",
            html_url="https://github.com/example/demo_module/releases/tag/v1.2.0",
            asset_name="demo_module-1.2.0.zip",
            asset_download_url="https://example.invalid/demo_module-1.2.0.zip",
            prerelease=False,
        )

    monkeypatch.setattr(service, "_fetch_latest_release", fake_release)

    result = await service.check_for_update(module)

    assert result.has_update is True
    assert result.current_version == "1.2.0-rc.1"
    assert result.latest_version == "1.2.0"


@pytest.mark.asyncio
async def test_prepare_module_upgrade_rejects_same_or_older_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    service = ModuleReleaseService()
    module = _make_module(tmp_path, version="1.1.0")

    async def fake_release(
        repo: str,
        *,
        allow_prerelease: bool = False,
        github_token: str | None = None,
    ) -> ModuleReleaseInfo:  # noqa: ARG001
        return ModuleReleaseInfo(
            repo=repo,
            tag_name="v1.1.0",
            version="1.1.0",
            title="v1.1.0",
            release_notes="notes",
            published_at="2026-04-17T00:00:00Z",
            html_url="https://github.com/example/demo_module/releases/tag/v1.1.0",
            asset_name="demo_module-1.1.0.zip",
            asset_download_url="https://example.invalid/demo_module-1.1.0.zip",
            prerelease=False,
        )

    monkeypatch.setattr(service, "_fetch_latest_release", fake_release)

    with pytest.raises(ValueError) as exc_info:
        await service.prepare_module_upgrade(module)

    assert "已经是最新版本" in str(exc_info.value)


@pytest.mark.asyncio
async def test_prepare_module_upgrade_rejects_manifest_release_version_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    service = ModuleReleaseService()
    module = _make_module(tmp_path, version="1.0.0")

    async def fake_check_for_update(
        module_info: ModuleInfo,
        *,
        github_token: str | None = None,
    ):  # noqa: ARG001
        return SimpleNamespace(
            module_name=module_info.name,
            current_version="1.0.0",
            latest_version="1.2.0",
            has_update=True,
            release=ModuleReleaseInfo(
                repo="example/demo_module",
                tag_name="v1.2.0",
                version="1.2.0",
                title="v1.2.0",
                release_notes="notes",
                published_at="2026-04-17T00:00:00Z",
                html_url="https://github.com/example/demo_module/releases/tag/v1.2.0",
                asset_name="demo_module-1.2.0.zip",
                asset_download_url="https://example.invalid/demo_module-1.2.0.zip",
                prerelease=False,
            ),
            error="",
        )

    archive = tmp_path / "demo_module-1.2.1.zip"
    archive.write_bytes(b"zip")
    manifest = ModuleManifest(
        name="demo_module",
        version="1.2.1",
        upgrade_source=UpgradeSourceInfo(repo="example/demo_module"),
    )

    monkeypatch.setattr(service, "check_for_update", fake_check_for_update)
    monkeypatch.setattr(service, "_ensure_module_idle", AsyncMock())
    monkeypatch.setattr(service, "_download_release_asset", AsyncMock(return_value=archive))
    monkeypatch.setattr(service, "_validate_archive", lambda path: (manifest, []))

    with pytest.raises(ValueError) as exc_info:
        await service.prepare_module_upgrade(module)

    assert "Release 不一致" in str(exc_info.value)


@pytest.mark.asyncio
async def test_apply_module_upgrade_rechecks_idle_before_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    service = ModuleReleaseService()
    module = _make_module(tmp_path, version="1.0.0")
    preview = ModulePackagePreview(
        install_kind="module_upgrade",
        manifest=ModuleManifest(
            name="demo_module",
            version="1.1.0",
            upgrade_source=UpgradeSourceInfo(repo="example/demo_module"),
        ),
        warnings=[],
        archive_path=tmp_path / "demo_module-1.1.0.zip",
        source_label="GitHub Release",
        release=ModuleReleaseInfo(
            repo="example/demo_module",
            tag_name="v1.1.0",
            version="1.1.0",
            title="v1.1.0",
            release_notes="notes",
            published_at="2026-04-17T00:00:00Z",
            html_url="https://github.com/example/demo_module/releases/tag/v1.1.0",
            asset_name="demo_module-1.1.0.zip",
            asset_download_url="https://example.invalid/demo_module-1.1.0.zip",
            prerelease=False,
        ),
    )

    registry = SimpleNamespace(
        get_module=lambda name: module if name == module.name else None,
        install=lambda source: pytest.fail(f"install should not run: {source}"),
    )

    @asynccontextmanager
    async def fake_lock(module_name: str):  # noqa: ARG001
        yield

    monkeypatch.setattr("src.core.mms.release_service.get_module_registry", lambda: registry)
    monkeypatch.setattr(service, "hold_module_upgrade_lock", fake_lock)
    monkeypatch.setattr(
        service,
        "_ensure_module_idle",
        AsyncMock(side_effect=ValueError("模块 demo_module 当前有 1 个运行中任务，暂时不能升级")),
    )

    with pytest.raises(ValueError) as exc_info:
        await service.apply_module_upgrade(module, preview)

    assert "运行中任务" in str(exc_info.value)


def test_package_preview_builds_source_lines(tmp_path: Path):
    preview = ModulePackagePreview(
        install_kind="github_release",
        manifest=ModuleManifest(
            name="demo_module",
            version="1.2.0",
            upgrade_source=UpgradeSourceInfo(repo="example/demo_module"),
        ),
        warnings=[],
        archive_path=tmp_path / "demo_module-1.2.0.zip",
        source_label="GitHub Release",
        release=ModuleReleaseInfo(
            repo="example/demo_module",
            tag_name="v1.2.0",
            version="1.2.0",
            title="v1.2.0",
            release_notes="notes",
            published_at="2026-04-17T00:00:00Z",
            html_url="https://github.com/example/demo_module/releases/tag/v1.2.0",
            asset_name="demo_module-1.2.0.zip",
            asset_download_url="https://example.invalid/demo_module-1.2.0.zip",
            prerelease=False,
        ),
    )

    lines = dict(preview.describe_source())
    assert lines["安装来源"] == "GitHub Release"
    assert lines["GitHub 仓库"] == "example/demo_module"
    assert lines["Release 版本"] == "1.2.0"

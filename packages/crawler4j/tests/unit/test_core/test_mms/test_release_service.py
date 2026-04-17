from __future__ import annotations

from pathlib import Path

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


@pytest.mark.asyncio
async def test_prepare_github_install_rejects_manifest_repo_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    service = ModuleReleaseService()

    async def fake_repo(repo: str) -> dict:
        return {"full_name": repo}

    async def fake_release(repo: str, *, allow_prerelease: bool = False) -> ModuleReleaseInfo:  # noqa: ARG001
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

    async def fake_release(repo: str, *, allow_prerelease: bool = False) -> ModuleReleaseInfo:  # noqa: ARG001
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
async def test_prepare_module_upgrade_rejects_same_or_older_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    service = ModuleReleaseService()
    module = _make_module(tmp_path, version="1.1.0")

    async def fake_release(repo: str, *, allow_prerelease: bool = False) -> ModuleReleaseInfo:  # noqa: ARG001
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

"""模块 GitHub Release 安装与升级服务。"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.core.foundation.logging import logger
from src.core.foundation.network import AsyncHttpClient
from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource
from src.core.mms.registry import get_module_registry
from src.utils.paths import get_app_data_dir


GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
BASE_VERSION_RE = re.compile(
    r"^v?(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(?:[.-].*)?$"
)


@dataclass(slots=True)
class ModuleReleaseInfo:
    repo: str
    tag_name: str
    version: str
    title: str
    release_notes: str
    published_at: str
    html_url: str
    asset_name: str
    asset_download_url: str
    prerelease: bool = False


@dataclass(slots=True)
class ModuleUpdateInfo:
    module_name: str
    current_version: str
    latest_version: str
    has_update: bool
    release: ModuleReleaseInfo | None = None
    error: str = ""


@dataclass(slots=True)
class ModulePackagePreview:
    install_kind: str
    manifest: ModuleManifest
    warnings: list[str] = field(default_factory=list)
    archive_path: Path | None = None
    source_label: str = ""
    release: ModuleReleaseInfo | None = None

    def describe_source(self) -> list[tuple[str, str]]:
        lines = [("安装来源", self.source_label or self.install_kind)]
        if self.archive_path:
            lines.append(("安装包", self.archive_path.name))
        repo = str(self.manifest.upgrade_source.repo or "").strip()
        if repo:
            lines.append(("GitHub 仓库", repo))
        if self.release:
            lines.append(("Release 版本", self.release.version))
            if self.release.published_at:
                lines.append(("发布时间", self.release.published_at))
        return lines


class ModuleReleaseService:
    """统一处理模块的 GitHub Release 安装与升级。"""

    GITHUB_API_BASE = "https://api.github.com"
    GITHUB_HOSTS = {"github.com", "www.github.com"}

    @staticmethod
    def normalize_repo(repo_input: str) -> str:
        normalized = str(repo_input or "").strip()
        if not normalized:
            raise ValueError("GitHub 仓库不能为空")

        if "://" not in normalized:
            if not GITHUB_REPO_RE.match(normalized):
                raise ValueError("GitHub 仓库必须是 owner/repo 形式")
            return normalized.strip("/")

        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in ModuleReleaseService.GITHUB_HOSTS:
            raise ValueError("当前只支持 GitHub 仓库 URL")

        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            raise ValueError("GitHub 仓库 URL 必须包含 owner/repo")

        owner, repo = parts[0], parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]
        candidate = f"{owner}/{repo}"
        if not GITHUB_REPO_RE.match(candidate):
            raise ValueError("GitHub 仓库必须是 owner/repo 形式")
        return candidate

    async def prepare_local_install(self, archive_path: str | Path) -> ModulePackagePreview:
        path = Path(archive_path).expanduser().resolve()
        manifest, warnings = self._validate_archive(path)
        repo = await self.verify_repo_accessible(manifest.upgrade_source.repo)
        manifest.upgrade_source.repo = repo
        return ModulePackagePreview(
            install_kind="local_zip",
            manifest=manifest,
            warnings=warnings,
            archive_path=path,
            source_label="本地 ZIP",
        )

    async def prepare_github_install(self, repo_input: str) -> ModulePackagePreview:
        repo = self.normalize_repo(repo_input)
        await self._fetch_repo_metadata(repo)
        release = await self._fetch_latest_release(repo)
        archive_path = await self._download_release_asset(release)
        manifest, warnings = self._validate_archive(archive_path)

        manifest_repo = self.normalize_repo(manifest.upgrade_source.repo)
        if manifest_repo != repo:
            raise ValueError(
                f"安装包声明的升级源仓库不一致: 期望 {repo}，实际 {manifest_repo}。"
            )

        return ModulePackagePreview(
            install_kind="github_release",
            manifest=manifest,
            warnings=warnings,
            archive_path=archive_path,
            source_label="GitHub Release",
            release=release,
        )

    async def prepare_dev_link(self, module_path: str | Path) -> tuple[ModuleManifest, list[str]]:
        path = Path(module_path).expanduser().resolve()
        registry = get_module_registry()
        manifest, warnings = registry.validate_source(path)
        repo = await self.verify_repo_accessible(manifest.upgrade_source.repo)
        manifest.upgrade_source.repo = repo
        return manifest, warnings

    async def verify_repo_accessible(self, repo_input: str) -> str:
        repo = self.normalize_repo(repo_input)
        await self._fetch_repo_metadata(repo)
        return repo

    async def check_for_update(self, module: ModuleInfo) -> ModuleUpdateInfo:
        current_version = str(module.manifest.version or "").strip()
        repo = str(module.manifest.upgrade_source.repo or "").strip()
        if module.source != ModuleSource.EXTERNAL or not repo:
            return ModuleUpdateInfo(
                module_name=module.name,
                current_version=current_version,
                latest_version=current_version,
                has_update=False,
            )

        normalized_repo = self.normalize_repo(repo)
        release = await self._fetch_latest_release(
            normalized_repo,
            allow_prerelease=module.manifest.upgrade_source.allow_prerelease,
        )
        has_update = self._compare_versions(release.version, current_version) > 0
        return ModuleUpdateInfo(
            module_name=module.name,
            current_version=current_version,
            latest_version=release.version,
            has_update=has_update,
            release=release,
        )

    async def prepare_module_upgrade(self, module: ModuleInfo) -> ModulePackagePreview:
        if module.source != ModuleSource.EXTERNAL:
            raise ValueError("只有正式安装的模块才支持在线升级")

        update_info = await self.check_for_update(module)
        if not update_info.has_update or not update_info.release:
            raise ValueError("已经是最新版本，无需升级")

        await self._ensure_module_idle(module.name)

        release = update_info.release
        archive_path = await self._download_release_asset(release)
        manifest, warnings = self._validate_archive(archive_path)
        if manifest.name != module.name:
            raise ValueError(
                f"升级包模块名不匹配: 当前模块为 {module.name}，安装包为 {manifest.name}"
            )

        manifest_repo = self.normalize_repo(manifest.upgrade_source.repo)
        current_repo = self.normalize_repo(module.manifest.upgrade_source.repo)
        if manifest_repo != current_repo:
            raise ValueError(
                f"升级包声明的升级源仓库不一致: 期望 {current_repo}，实际 {manifest_repo}。"
            )

        if self._compare_versions(manifest.version, module.manifest.version) <= 0:
            raise ValueError("下载到的升级包版本没有高于当前版本")

        return ModulePackagePreview(
            install_kind="module_upgrade",
            manifest=manifest,
            warnings=warnings,
            archive_path=archive_path,
            source_label="GitHub Release",
            release=release,
        )

    async def _ensure_module_idle(self, module_name: str) -> None:
        from src.core.atm.service import get_task_service

        service = get_task_service()
        jobs = await service.list_jobs()
        related_jobs = [
            job for job in jobs
            if job.run_profile
            and job.run_profile.execution
            and job.run_profile.execution.module == module_name
        ]
        if not related_jobs:
            return

        active_counts = await asyncio.gather(
            *(service.count_active_tasks(job.id) for job in related_jobs)
        )
        active_total = sum(active_counts)
        if active_total > 0:
            raise ValueError(f"模块 {module_name} 当前有 {active_total} 个运行中任务，暂时不能升级")

    async def _fetch_repo_metadata(self, repo: str) -> dict[str, Any]:
        return await self._request_json(f"{self.GITHUB_API_BASE}/repos/{repo}")

    async def _fetch_latest_release(
        self,
        repo: str,
        *,
        allow_prerelease: bool = False,
    ) -> ModuleReleaseInfo:
        payload = await self._request_json(f"{self.GITHUB_API_BASE}/repos/{repo}/releases")
        if not isinstance(payload, list) or not payload:
            raise ValueError(f"仓库 {repo} 没有可用的 GitHub Release")

        for item in payload:
            if not isinstance(item, dict) or item.get("draft"):
                continue
            if item.get("prerelease") and not allow_prerelease:
                continue
            return self._parse_release(repo, item)

        if allow_prerelease:
            raise ValueError(f"仓库 {repo} 没有可用的 GitHub Release")
        raise ValueError(f"仓库 {repo} 没有稳定版 GitHub Release")

    async def _download_release_asset(self, release: ModuleReleaseInfo) -> Path:
        target_dir = get_app_data_dir() / "downloads" / "modules" / release.repo.replace("/", "__")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / release.asset_name

        headers = {"User-Agent": "crawler4j-module-updater", "Accept": "application/octet-stream"}
        session = await AsyncHttpClient.get_session()
        proxy = AsyncHttpClient._get_proxy()
        request_kwargs: dict[str, Any] = {"headers": headers}
        if proxy:
            request_kwargs["proxy"] = proxy

        async with session.get(release.asset_download_url, **request_kwargs) as response:
            if response.status >= 400:
                message = await response.text()
                raise ValueError(
                    f"下载模块安装包失败 ({response.status}): {message or release.asset_download_url}"
                )

            with target_path.open("wb") as fh:
                async for chunk in response.content.iter_chunked(65536):
                    fh.write(chunk)

        return target_path

    def _validate_archive(self, path: Path) -> tuple[ModuleManifest, list[str]]:
        registry = get_module_registry()
        return registry.validate_source(path)

    async def _request_json(self, url: str) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "crawler4j-module-updater",
        }
        session = await AsyncHttpClient.get_session()
        proxy = AsyncHttpClient._get_proxy()
        request_kwargs: dict[str, Any] = {"headers": headers}
        if proxy:
            request_kwargs["proxy"] = proxy

        async with session.get(url, **request_kwargs) as response:
            if response.status >= 400:
                message = ""
                try:
                    payload = await response.json()
                    if isinstance(payload, dict):
                        message = str(payload.get("message", ""))
                except Exception:
                    message = await response.text()
                logger.warning("[MMS] GitHub API request failed: %s %s %s", response.status, url, message)
                raise ValueError(f"GitHub 请求失败 ({response.status}): {message or url}")
            return await response.json()

    def _parse_release(self, repo: str, payload: dict[str, Any]) -> ModuleReleaseInfo:
        assets = payload.get("assets") or []
        zip_assets = [
            asset for asset in assets
            if isinstance(asset, dict)
            and str(asset.get("name", "")).lower().endswith(".zip")
            and asset.get("browser_download_url")
        ]
        if len(zip_assets) != 1:
            raise ValueError(
                f"仓库 {repo} 的 Release {payload.get('tag_name') or payload.get('name') or '<unknown>'} "
                "必须且只能上传一个 ZIP 安装包"
            )

        asset = zip_assets[0]
        version = self._extract_release_version(payload)
        return ModuleReleaseInfo(
            repo=repo,
            tag_name=str(payload.get("tag_name", "") or "").strip(),
            version=version,
            title=str(payload.get("name", "") or payload.get("tag_name", "") or "").strip(),
            release_notes=str(payload.get("body", "") or "").strip(),
            published_at=str(payload.get("published_at", "") or "").strip(),
            html_url=str(payload.get("html_url", "") or "").strip(),
            asset_name=str(asset.get("name", "") or "").strip(),
            asset_download_url=str(asset.get("browser_download_url", "") or "").strip(),
            prerelease=bool(payload.get("prerelease", False)),
        )

    def _extract_release_version(self, payload: dict[str, Any]) -> str:
        candidates = [
            str(payload.get("tag_name", "") or "").strip(),
            str(payload.get("name", "") or "").strip(),
        ]
        for candidate in candidates:
            version = candidate.lstrip("v")
            if BASE_VERSION_RE.match(candidate) or BASE_VERSION_RE.match(version):
                return version
        raise ValueError(f"Release 版本号无效: {candidates[0] or candidates[1] or '<empty>'}")

    def _compare_versions(self, left: str, right: str) -> int:
        left_parts = self._parse_version(left)
        right_parts = self._parse_version(right)
        if left_parts < right_parts:
            return -1
        if left_parts > right_parts:
            return 1
        return 0

    def _parse_version(self, version_str: str) -> tuple[int, int, int]:
        match = BASE_VERSION_RE.match(str(version_str or "").strip())
        if not match:
            raise ValueError(f"无效的版本号: {version_str}")
        return (
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
        )


_release_service: ModuleReleaseService | None = None


def get_module_release_service() -> ModuleReleaseService:
    global _release_service
    if _release_service is None:
        _release_service = ModuleReleaseService()
    return _release_service

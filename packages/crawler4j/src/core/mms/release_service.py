"""模块 GitHub Release 安装与升级服务。"""

from __future__ import annotations

import asyncio
import re
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from src.core.foundation.logging import logger
from src.core.foundation.network import AsyncHttpClient
from src.core.mms.github_credentials import get_github_credential_store
from src.core.mms.models import ModuleInfo, ModuleManifest, ModuleSource
from src.core.mms.registry import get_module_registry
from src.core.mms.semver import compare_semver, is_valid_semver
from src.core.persistence import get_kv_store
from src.utils.paths import get_app_data_dir


GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MODULE_UPGRADE_LOCK_TTL = 10 * 60
_module_upgrade_process_locks: dict[str, asyncio.Lock] = {}


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
    asset_api_url: str = ""
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

    async def prepare_local_install(
        self,
        archive_path: str | Path,
        *,
        github_token: str | None = None,
    ) -> ModulePackagePreview:
        path = Path(archive_path).expanduser().resolve()
        manifest, warnings = self._validate_archive(path)
        repo = await self.verify_repo_accessible(
            manifest.upgrade_source.repo,
            github_token=github_token,
        )
        manifest.upgrade_source.repo = repo
        return ModulePackagePreview(
            install_kind="local_zip",
            manifest=manifest,
            warnings=warnings,
            archive_path=path,
            source_label="本地 ZIP",
        )

    async def prepare_github_install(
        self,
        repo_input: str,
        *,
        github_token: str | None = None,
    ) -> ModulePackagePreview:
        repo = self.normalize_repo(repo_input)
        await self._fetch_repo_metadata(repo, github_token=github_token)
        release = await self._fetch_latest_release(repo, github_token=github_token)
        archive_path = await self._download_release_asset(release, github_token=github_token)
        manifest, warnings = self._validate_archive(archive_path)

        manifest_repo = self.normalize_repo(manifest.upgrade_source.repo)
        if manifest_repo != repo:
            raise ValueError(
                f"安装包声明的升级源仓库不一致: 期望 {repo}，实际 {manifest_repo}。"
            )
        self._ensure_manifest_matches_release(manifest, release)

        return ModulePackagePreview(
            install_kind="github_release",
            manifest=manifest,
            warnings=warnings,
            archive_path=archive_path,
            source_label="GitHub Release",
            release=release,
        )

    async def prepare_dev_link(
        self,
        module_path: str | Path,
        *,
        github_token: str | None = None,
    ) -> tuple[ModuleManifest, list[str]]:
        path = Path(module_path).expanduser().resolve()
        registry = get_module_registry()
        manifest, warnings = registry.validate_source(path)
        repo = self.normalize_repo(manifest.upgrade_source.repo)
        try:
            await self._fetch_repo_metadata(repo, github_token=github_token)
        except ValueError as exc:
            warnings.append(
                f"GitHub 仓库可达性检查失败，已跳过远端预检: {exc}"
            )
        manifest.upgrade_source.repo = repo
        return manifest, warnings

    async def verify_repo_accessible(
        self,
        repo_input: str,
        *,
        github_token: str | None = None,
    ) -> str:
        repo = self.normalize_repo(repo_input)
        await self._fetch_repo_metadata(repo, github_token=github_token)
        return repo

    async def check_for_update(
        self,
        module: ModuleInfo,
        *,
        github_token: str | None = None,
    ) -> ModuleUpdateInfo:
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
            github_token=github_token,
        )
        has_update = self._compare_versions(release.version, current_version) > 0
        return ModuleUpdateInfo(
            module_name=module.name,
            current_version=current_version,
            latest_version=release.version,
            has_update=has_update,
            release=release,
        )

    async def prepare_module_upgrade(
        self,
        module: ModuleInfo,
        *,
        github_token: str | None = None,
    ) -> ModulePackagePreview:
        if module.source != ModuleSource.EXTERNAL:
            raise ValueError("只有正式安装的模块才支持在线升级")

        update_info = await self.check_for_update(module, github_token=github_token)
        if not update_info.has_update or not update_info.release:
            raise ValueError("已经是最新版本，无需升级")

        await self._ensure_module_idle(module.name)

        release = update_info.release
        archive_path = await self._download_release_asset(release, github_token=github_token)
        manifest, warnings = self._validate_archive(archive_path)
        self._validate_upgrade_package(module, manifest, release)

        return ModulePackagePreview(
            install_kind="module_upgrade",
            manifest=manifest,
            warnings=warnings,
            archive_path=archive_path,
            source_label="GitHub Release",
            release=release,
        )

    async def apply_module_upgrade(
        self,
        module: ModuleInfo,
        preview: ModulePackagePreview,
    ) -> ModuleInfo:
        if module.source != ModuleSource.EXTERNAL:
            raise ValueError("只有正式安装的模块才支持在线升级")
        if preview.install_kind != "module_upgrade":
            raise ValueError("升级预览无效，请重新检查升级")
        if not preview.archive_path:
            raise ValueError("升级包不存在，请重新检查升级")
        if not preview.release:
            raise ValueError("升级预览缺少 Release 信息，请重新检查升级")

        async with self.hold_module_upgrade_lock(module.name):
            registry = get_module_registry()
            current_module = registry.get_module(module.name)
            if not current_module:
                raise ValueError(f"模块不存在: {module.name}")
            if current_module.source != ModuleSource.EXTERNAL:
                raise ValueError("只有正式安装的模块才支持在线升级")
            if current_module.manifest.version != module.manifest.version:
                raise ValueError(
                    f"模块 {module.name} 在确认升级后已发生变化，请重新检查升级"
                )

            self._validate_upgrade_package(current_module, preview.manifest, preview.release)
            await self._ensure_module_idle(current_module.name)
            return registry.install(preview.archive_path)

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

    def _validate_upgrade_package(
        self,
        module: ModuleInfo,
        manifest: ModuleManifest,
        release: ModuleReleaseInfo,
    ) -> None:
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

        self._ensure_manifest_matches_release(manifest, release)

        if self._compare_versions(manifest.version, module.manifest.version) <= 0:
            raise ValueError("下载到的升级包版本没有高于当前版本")

    def _ensure_manifest_matches_release(
        self,
        manifest: ModuleManifest,
        release: ModuleReleaseInfo,
    ) -> None:
        manifest_version = str(manifest.version or "").strip()
        release_version = str(release.version or "").strip()
        if manifest_version != release_version:
            raise ValueError(
                f"安装包声明的版本与 Release 不一致: 期望 {release_version}，实际 {manifest_version}。"
            )

    @asynccontextmanager
    async def hold_module_upgrade_lock(self, module_name: str):
        module_name = str(module_name or "").strip()
        if not module_name:
            raise ValueError("模块名不能为空")

        process_lock = _module_upgrade_process_locks.get(module_name)
        if process_lock is None:
            process_lock = asyncio.Lock()
            _module_upgrade_process_locks[module_name] = process_lock

        async with process_lock:
            kv = get_kv_store()
            lock_key = self._upgrade_lock_key(module_name)
            existing = kv.get(lock_key)
            if existing is not None:
                raise ValueError(f"模块 {module_name} 正在执行升级维护，请稍后再试")

            token = uuid.uuid4().hex
            kv.set(
                lock_key,
                {
                    "module_name": module_name,
                    "lock_type": "module_upgrade",
                    "token": token,
                    "owner": "module_release_service",
                    "claimed_at": int(time.time()),
                },
                ttl=MODULE_UPGRADE_LOCK_TTL,
            )
            try:
                yield
            finally:
                current = kv.get(lock_key)
                if isinstance(current, dict) and current.get("token") == token:
                    kv.delete(lock_key)

    @staticmethod
    def _upgrade_lock_key(module_name: str) -> str:
        return f"module:{module_name}:lock:maintenance:module_upgrade"

    def _resolve_github_token(
        self,
        repo: str | None = None,
        github_token: str | None = None,
    ) -> str | None:
        explicit = str(github_token or "").strip()
        if explicit:
            return explicit
        normalized_repo = str(repo or "").strip()
        if normalized_repo:
            return get_github_credential_store().get_token(normalized_repo)
        return None

    def _build_github_headers(
        self,
        *,
        accept: str,
        repo: str | None = None,
        github_token: str | None = None,
        user_agent: str = "crawler4j-module-updater",
    ) -> dict[str, str]:
        headers = {
            "Accept": accept,
            "User-Agent": user_agent,
        }
        token = self._resolve_github_token(repo=repo, github_token=github_token)
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    async def _fetch_repo_metadata(
        self,
        repo: str,
        *,
        github_token: str | None = None,
    ) -> dict[str, Any]:
        return await self._request_json(
            f"{self.GITHUB_API_BASE}/repos/{repo}",
            repo=repo,
            github_token=github_token,
        )

    async def _fetch_latest_release(
        self,
        repo: str,
        *,
        allow_prerelease: bool = False,
        github_token: str | None = None,
    ) -> ModuleReleaseInfo:
        payload = await self._request_json(
            f"{self.GITHUB_API_BASE}/repos/{repo}/releases",
            repo=repo,
            github_token=github_token,
        )
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

    async def _download_release_asset(
        self,
        release: ModuleReleaseInfo,
        *,
        github_token: str | None = None,
    ) -> Path:
        target_dir = get_app_data_dir() / "downloads" / "modules" / release.repo.replace("/", "__")
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / release.asset_name

        headers = self._build_github_headers(
            accept="application/octet-stream",
            repo=release.repo,
            github_token=github_token,
        )
        session = await AsyncHttpClient.get_session()
        proxy = AsyncHttpClient._get_proxy()
        request_kwargs: dict[str, Any] = {"headers": headers}
        if proxy:
            request_kwargs["proxy"] = proxy

        download_url = str(release.asset_api_url or "").strip() or release.asset_download_url
        async with session.get(download_url, **request_kwargs) as response:
            if response.status >= 400:
                message = await response.text()
                raise ValueError(
                    f"下载模块安装包失败 ({response.status}): {message or download_url}"
                )

            with target_path.open("wb") as fh:
                async for chunk in response.content.iter_chunked(65536):
                    fh.write(chunk)

        return target_path

    def _validate_archive(self, path: Path) -> tuple[ModuleManifest, list[str]]:
        registry = get_module_registry()
        return registry.validate_source(path)

    async def _request_json(
        self,
        url: str,
        *,
        repo: str | None = None,
        github_token: str | None = None,
    ) -> Any:
        headers = self._build_github_headers(
            accept="application/vnd.github+json",
            repo=repo,
            github_token=github_token,
        )
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
                logger.warning(
                    f"[MMS] GitHub API request failed: {response.status} {url} {message}"
                )
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
            asset_api_url=str(asset.get("url", "") or "").strip(),
            prerelease=bool(payload.get("prerelease", False)),
        )

    def _extract_release_version(self, payload: dict[str, Any]) -> str:
        candidates = [
            str(payload.get("tag_name", "") or "").strip(),
            str(payload.get("name", "") or "").strip(),
        ]
        for candidate in candidates:
            version = candidate.lstrip("v")
            if is_valid_semver(candidate) or is_valid_semver(version):
                return version
        raise ValueError(f"Release 版本号无效: {candidates[0] or candidates[1] or '<empty>'}")

    def _compare_versions(self, left: str, right: str) -> int:
        return compare_semver(left, right)


_release_service: ModuleReleaseService | None = None


def get_module_release_service() -> ModuleReleaseService:
    global _release_service
    if _release_service is None:
        _release_service = ModuleReleaseService()
    return _release_service


def is_module_upgrade_locked(module_name: str) -> bool:
    return get_kv_store().exists(ModuleReleaseService._upgrade_lock_key(module_name))


def assert_module_upgrade_unlocked(module_name: str) -> None:
    payload = get_kv_store().get(ModuleReleaseService._upgrade_lock_key(module_name))
    if payload is None:
        return
    raise ValueError(f"模块 {module_name} 正在执行升级维护，请稍后再试")

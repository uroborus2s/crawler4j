"""OTA 升级服务。

提供应用自动更新能力：
- 检查更新
- 下载更新包
- 校验文件完整性
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal


class UpdateChannel(str, Enum):
    """更新通道。"""

    STABLE = "stable"
    BETA = "beta"
    NIGHTLY = "nightly"


@dataclass
class UpdateInfo:
    """更新信息。

    Attributes:
        version: 新版本号
        channel: 更新通道
        release_notes: 发布说明
        download_url: 下载地址
        file_size: 文件大小 (bytes)
        sha256: 文件哈希
        is_critical: 是否为关键安全更新
    """

    version: str
    channel: UpdateChannel
    release_notes: str
    download_url: str
    file_size: int
    sha256: str
    is_critical: bool = False


class UpdateService(QObject):
    """OTA 升级服务。

    Signals:
        update_available: 发现新版本时发出
        progress_updated: 下载进度更新 (downloaded_bytes, total_bytes)
        download_completed: 下载完成 (file_path)
        download_failed: 下载失败 (error_message)
        verification_failed: 校验失败
    """

    update_available = pyqtSignal(object)  # UpdateInfo
    progress_updated = pyqtSignal(int, int)  # downloaded, total
    download_completed = pyqtSignal(str)  # file_path
    download_failed = pyqtSignal(str)  # error_message
    verification_failed = pyqtSignal()

    # 更新服务器地址 (占位)
    UPDATE_SERVER = "https://update.crawler4j.example.com/api/v1"

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._channel = UpdateChannel.STABLE
        self._is_downloading = False
        self._download_cancelled = False

    @property
    def channel(self) -> UpdateChannel:
        """当前更新通道。"""
        return self._channel

    @channel.setter
    def channel(self, value: UpdateChannel) -> None:
        """设置更新通道。"""
        self._channel = value

    async def check_for_updates(self) -> Optional[UpdateInfo]:
        """检查是否有新版本。

        Returns:
            UpdateInfo 如果有新版本，否则 None
        """
        # TODO: 实现实际的更新检查逻辑
        # 1. 请求 UPDATE_SERVER/check?version=<current>&channel=<channel>
        # 2. 解析响应 JSON
        # 3. 比较版本号
        return None

    async def download_update(self, update_info: UpdateInfo) -> Optional[str]:
        """下载更新包。

        Args:
            update_info: 更新信息

        Returns:
            下载文件的本地路径，失败返回 None
        """
        self._is_downloading = True
        self._download_cancelled = False

        try:
            # TODO: 实现实际的下载逻辑
            # 1. 创建临时目录
            # 2. 分块下载，发出 progress_updated
            # 3. 校验哈希
            # 4. 返回文件路径
            pass
        except Exception as e:
            self.download_failed.emit(str(e))
            return None
        finally:
            self._is_downloading = False

        return None

    def cancel_download(self) -> None:
        """取消下载。"""
        self._download_cancelled = True

    @property
    def is_downloading(self) -> bool:
        """是否正在下载。"""
        return self._is_downloading

    @staticmethod
    def verify_file(file_path: Path, expected_sha256: str) -> bool:
        """校验文件哈希。

        Args:
            file_path: 文件路径
            expected_sha256: 预期的 SHA256 哈希

        Returns:
            True 如果校验通过
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest().lower() == expected_sha256.lower()


# 单例
_update_service: Optional[UpdateService] = None


def get_update_service() -> UpdateService:
    """获取 UpdateService 单例。"""
    global _update_service
    if _update_service is None:
        _update_service = UpdateService()
    return _update_service

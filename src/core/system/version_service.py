"""版本管理服务。

提供版本查询与兼容性校验能力：
- 语义化版本解析 (SemVer)
- 版本约束校验
- 构建信息获取
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

from src.__version__ import VERSION


@dataclass(frozen=True)
class BuildInfo:
    """构建信息。

    Attributes:
        version: 语义化版本号 (e.g., "1.0.0")
        commit_hash: Git 提交哈希 (短)
        build_time: 构建时间 (ISO 8601 格式，可选)
    """

    version: str
    commit_hash: Optional[str] = None
    build_time: Optional[str] = None

    def __str__(self) -> str:
        """格式化为显示字符串。"""
        if self.commit_hash:
            return f"v{self.version} (Build {self.commit_hash[:7]})"
        return f"v{self.version}"


class VersionService:
    """版本管理服务。

    职责：
    - 提供当前版本信息
    - 校验版本兼容性约束
    """

    # SemVer 正则：Major.Minor.Patch(-prerelease)?(+build)?
    SEMVER_PATTERN = re.compile(
        r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
        r"(?:-(?P<prerelease>[\da-zA-Z\-]+(?:\.[\da-zA-Z\-]+)*))?"
        r"(?:\+(?P<build>[\da-zA-Z\-]+(?:\.[\da-zA-Z\-]+)*))?$"
    )

    def get_current_version(self) -> str:
        """获取当前版本号。

        Returns:
            语义化版本字符串，如 "0.2.0"
        """
        return VERSION

    def get_build_info(self) -> BuildInfo:
        """获取完整构建信息。

        Returns:
            BuildInfo 对象，包含版本、commit hash 等
        """
        commit_hash = self._get_git_commit()
        return BuildInfo(version=VERSION, commit_hash=commit_hash)

    def check_compatibility(self, requirement: str) -> bool:
        """校验当前版本是否满足约束。

        支持的约束格式：
        - ">=1.0.0": 大于等于
        - "^1.0.0": 兼容性约束 (同一 major 版本)
        - "~1.0.0": 近似约束 (同一 minor 版本)

        Args:
            requirement: 版本约束字符串

        Returns:
            True 如果当前版本满足约束
        """
        current = self._parse_version(VERSION)
        if current is None:
            return False

        # 解析约束
        if requirement.startswith(">="):
            required = self._parse_version(requirement[2:])
            if required is None:
                return False
            return self._compare_tuples(current, required) >= 0

        if requirement.startswith("^"):
            required = self._parse_version(requirement[1:])
            if required is None:
                return False
            # 兼容性：major 版本相同，且 >= required
            return current[0] == required[0] and self._compare_tuples(current, required) >= 0

        if requirement.startswith("~"):
            required = self._parse_version(requirement[1:])
            if required is None:
                return False
            # 近似：major.minor 相同，且 >= required
            return (
                current[0] == required[0]
                and current[1] == required[1]
                and self._compare_tuples(current, required) >= 0
            )

        # 精确匹配
        required = self._parse_version(requirement)
        if required is None:
            return False
        return current == required

    def _parse_version(self, version_str: str) -> Optional[tuple[int, int, int]]:
        """解析版本字符串为元组。"""
        match = self.SEMVER_PATTERN.match(version_str.strip())
        if not match:
            return None
        return (
            int(match.group("major")),
            int(match.group("minor")),
            int(match.group("patch")),
        )

    @staticmethod
    def _compare_tuples(
        a: tuple[int, int, int], b: tuple[int, int, int]
    ) -> int:
        """比较版本元组。返回 -1, 0, 1。"""
        if a < b:
            return -1
        if a > b:
            return 1
        return 0

    @staticmethod
    def _get_git_commit() -> Optional[str]:
        """获取 Git 提交哈希。"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None


# 单例
_version_service: Optional[VersionService] = None


def get_version_service() -> VersionService:
    """获取 VersionService 单例。"""
    global _version_service
    if _version_service is None:
        _version_service = VersionService()
    return _version_service


@lru_cache(maxsize=1)
def get_current_version() -> str:
    """便捷函数：获取当前版本。"""
    return get_version_service().get_current_version()

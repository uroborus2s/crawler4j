"""VersionService 单元测试。"""

import pytest

from src.core.system.version_service import (
    BuildInfo,
    VersionService,
    get_current_version,
    get_version_service,
)


class TestBuildInfo:
    """BuildInfo 数据类测试。"""

    def test_str_with_commit(self):
        """测试带 commit hash 的字符串格式化。"""
        info = BuildInfo(version="1.0.0", commit_hash="abc123def456")
        assert str(info) == "v1.0.0 (Build abc123d)"

    def test_str_without_commit(self):
        """测试不带 commit hash 的字符串格式化。"""
        info = BuildInfo(version="1.0.0")
        assert str(info) == "v1.0.0"


class TestVersionService:
    """VersionService 测试。"""

    @pytest.fixture
    def service(self) -> VersionService:
        return VersionService()

    def test_get_current_version(self, service: VersionService):
        """测试获取当前版本。"""
        version = service.get_current_version()
        assert version is not None
        assert len(version.split(".")) == 3  # Major.Minor.Patch

    def test_get_build_info(self, service: VersionService):
        """测试获取构建信息。"""
        info = service.get_build_info()
        assert isinstance(info, BuildInfo)
        assert info.version == service.get_current_version()

    # 版本兼容性校验测试

    def test_check_compatibility_exact_match(self, service: VersionService):
        """测试精确版本匹配。"""
        current = service.get_current_version()
        assert service.check_compatibility(current) is True
        assert service.check_compatibility("999.999.999") is False

    def test_check_compatibility_gte(self, service: VersionService):
        """测试 >= 约束。"""
        assert service.check_compatibility(">=0.0.1") is True
        assert service.check_compatibility(">=0.1.0") is True
        assert service.check_compatibility(">=999.0.0") is False

    def test_check_compatibility_caret(self, service: VersionService):
        """测试 ^ 兼容性约束。"""
        # ^0.2.0 表示 major=0，且 >= 0.2.0
        current = service.get_current_version()
        major = int(current.split(".")[0])
        
        assert service.check_compatibility(f"^{major}.0.0") is True
        assert service.check_compatibility("^999.0.0") is False

    def test_check_compatibility_tilde(self, service: VersionService):
        """测试 ~ 近似约束。"""
        current = service.get_current_version()
        parts = current.split(".")
        major, minor = int(parts[0]), int(parts[1])
        
        assert service.check_compatibility(f"~{major}.{minor}.0") is True
        assert service.check_compatibility("~999.999.0") is False

    def test_check_compatibility_invalid(self, service: VersionService):
        """测试无效版本约束。"""
        assert service.check_compatibility("invalid") is False
        assert service.check_compatibility("") is False
        assert service.check_compatibility("1.2") is False


class TestSingleton:
    """单例测试。"""

    def test_get_version_service_singleton(self):
        """测试 VersionService 单例。"""
        svc1 = get_version_service()
        svc2 = get_version_service()
        assert svc1 is svc2

    def test_get_current_version_cached(self):
        """测试 get_current_version 缓存。"""
        v1 = get_current_version()
        v2 = get_current_version()
        assert v1 == v2

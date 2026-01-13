"""模块扫描器与解析器。

规格参考: docs/srs/05-framework-core/05-1-module-management.md (5.1.4.1, 5.1.4.2)

负责：
    - 模块发现：扫描受控目录发现候选模块
    - Manifest 解析：解析 module.yaml
    - 校验：命名、唯一性、SDK 兼容性
"""

from pathlib import Path
from typing import Any

import yaml

from src.core.foundation.logging import logger
from src.core.mms.models import (
    ModuleInfo,
    ModuleManifest,
    ModuleParseError,
    ModuleSource,
    ModuleStatus,
    ModuleValidationError,
)
from src.utils.paths import get_builtin_modules_path, get_user_modules_path

# SDK 版本（用于兼容性校验）
CURRENT_SDK_VERSION = "1.0.0"

# 忽略的目录
IGNORED_DIRS = {"__pycache__", ".git", ".venv", "node_modules"}


class ModuleScanner:
    """模块扫描器。
    
    规格 5.1.4.1: 在扫描域中发现候选模块包。
    """
    
    def __init__(self, scan_paths: list[Path] | None = None):
        """初始化扫描器。
        
        Args:
            scan_paths: 自定义扫描路径，默认使用内置+用户目录
        """
        if scan_paths:
            self.scan_paths = scan_paths
        else:
            self.scan_paths = [
                get_builtin_modules_path(),
                get_user_modules_path(),
            ]
    
    def discover(self) -> list[tuple[Path, ModuleSource]]:
        """发现所有模块包。
        
        规格 5.1.4.1:
            - 输出稳定的候选列表（路径 + 来源标识）
            - 忽略 __pycache__ 等无关条目
        
        Returns:
            模块路径和来源的列表
        """
        candidates: list[tuple[Path, ModuleSource]] = []
        
        for scan_path in self.scan_paths:
            if not scan_path.exists():
                continue
            
            # 确定来源类型
            source = (
                ModuleSource.BUILTIN
                if scan_path == get_builtin_modules_path()
                else ModuleSource.EXTERNAL
            )
            
            # 扫描子目录
            for item in sorted(scan_path.iterdir()):
                if not item.is_dir():
                    continue
                if item.name in IGNORED_DIRS or item.name.startswith("."):
                    continue
                
                # 检查是否有 module.yaml
                manifest_path = item / "module.yaml"
                if manifest_path.exists():
                    candidates.append((item, source))
        
        logger.info(f"[MMS] 发现 {len(candidates)} 个候选模块")
        return candidates
    
    def parse_manifest(self, module_path: Path) -> ModuleManifest:
        """解析模块清单。
        
        规格 5.1.4.2: 解析 module.yaml
        
        Args:
            module_path: 模块目录路径
        
        Returns:
            解析后的模块清单
        
        Raises:
            ModuleParseError: 解析失败
        """
        manifest_path = module_path / "module.yaml"
        
        if not manifest_path.exists():
            raise ModuleParseError(
                f"找不到 module.yaml: {module_path}",
                stage="PARSE",
                hint="请确保模块目录包含 module.yaml 文件"
            )
        
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if not data:
                raise ModuleParseError(
                    f"module.yaml 为空: {module_path}",
                    stage="PARSE",
                    hint="请填写模块清单内容"
                )
            
            return ModuleManifest.from_dict(data)
            
        except yaml.YAMLError as e:
            raise ModuleParseError(
                f"YAML 解析错误: {e}",
                stage="PARSE",
                hint="请检查 YAML 语法是否正确"
            )
    
    def validate(self, manifest: ModuleManifest, module_path: Path) -> list[str]:
        """校验模块清单。
        
        规格 5.1.4.2:
            - 命名与唯一性校验
            - SDK 版本兼容性校验
        
        Args:
            manifest: 模块清单
            module_path: 模块路径
        
        Returns:
            警告信息列表
        
        Raises:
            ModuleValidationError: 校验失败
        """
        warnings: list[str] = []
        
        # 必填字段校验
        if not manifest.name:
            raise ModuleValidationError(
                "缺少必填字段: name",
                stage="VALIDATE",
                hint="请在 module.yaml 中添加 name 字段"
            )
        
        # 命名规范校验（小写字母、数字、下划线）
        if not manifest.name.replace("_", "").isalnum() or not manifest.name.islower():
            warnings.append(f"模块名 '{manifest.name}' 不符合命名规范（应为小写字母、数字、下划线）")
        
        # SDK 兼容性校验
        if not self._check_sdk_compatibility(manifest.sdk_version_range):
            raise ModuleValidationError(
                f"SDK 版本不兼容: 需要 {manifest.sdk_version_range}，当前 {CURRENT_SDK_VERSION}",
                stage="VALIDATE",
                hint="请更新模块或升级 SDK"
            )
        
        # 工作流名称唯一性
        workflow_names = [w.name for w in manifest.workflows]
        if len(workflow_names) != len(set(workflow_names)):
            raise ModuleValidationError(
                "工作流名称重复",
                stage="VALIDATE",
                hint="请确保每个工作流有唯一的 name"
            )
        
        return warnings
    
    def _check_sdk_compatibility(self, version_range: str) -> bool:
        """检查 SDK 版本兼容性。
        
        简化实现：目前只支持 >=x.y.z 格式
        """
        if not version_range:
            return True
        
        if version_range.startswith(">="):
            required = version_range[2:].strip()
            return self._compare_versions(CURRENT_SDK_VERSION, required) >= 0
        
        return True
    
    def _compare_versions(self, v1: str, v2: str) -> int:
        """比较版本号。返回 1, 0, -1"""
        parts1 = [int(x) for x in v1.split(".")]
        parts2 = [int(x) for x in v2.split(".")]
        
        for p1, p2 in zip(parts1, parts2):
            if p1 > p2:
                return 1
            if p1 < p2:
                return -1
        
        return 0
    
    def load_module(self, module_path: Path, source: ModuleSource) -> ModuleInfo:
        """加载单个模块。
        
        Args:
            module_path: 模块目录路径
            source: 模块来源
        
        Returns:
            模块信息
        """
        try:
            manifest = self.parse_manifest(module_path)
            warnings = self.validate(manifest, module_path)
            
            for warning in warnings:
                logger.warning(f"[MMS] {module_path.name}: {warning}")
            
            return ModuleInfo(
                name=manifest.name,
                manifest=manifest,
                source=source,
                status=ModuleStatus.ENABLED,
                path=module_path,
            )
            
        except (ModuleParseError, ModuleValidationError) as e:
            logger.error(f"[MMS] 加载失败 {module_path.name}: {e}")
            
            # 创建无效模块条目
            return ModuleInfo(
                name=module_path.name,
                manifest=ModuleManifest(name=module_path.name),
                source=source,
                status=ModuleStatus.INVALID,
                path=module_path,
                error=str(e),
                hint=e.hint,
            )


# 全局单例
_scanner: ModuleScanner | None = None


def get_module_scanner() -> ModuleScanner:
    """获取全局 ModuleScanner 实例。"""
    global _scanner
    if _scanner is None:
        _scanner = ModuleScanner()
    return _scanner

"""模块扫描器与解析器。

规格参考: docs/02-requirements/reference-srs/05-framework-core/05-1-module-management.md (5.1.4.1, 5.1.4.2)

负责：
    - 模块发现：扫描受控目录发现候选模块
    - Manifest 解析：解析 module.yaml
    - 校验：命名、唯一性、受控字段约束
"""

from pathlib import Path
import re
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
from src.core.mms.semver import is_valid_semver
from src.utils.paths import get_builtin_modules_path, get_user_modules_path

# 忽略的目录
IGNORED_DIRS = {"__pycache__", ".git", ".venv", "node_modules"}
MANAGED_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ALWAYS_REMOVED_MANIFEST_FIELDS = (
    "sdk_version_range",
)
V2_REMOVED_MANIFEST_FIELDS = (
    "default_workflow",
    "workflows",
    "data",
    "interfaces",
    "objects",
    "tasks",
    "ui_extension",
)
REQUIRED_RUNTIME_API = "core-native-v2"


class _UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def _construct_mapping_without_duplicate_keys(loader, node, deep=False):
    loader.flatten_mapping(node)
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            mark = getattr(key_node, "start_mark", None)
            location = f"（第 {mark.line + 1} 行，第 {mark.column + 1} 列）" if mark is not None else ""
            raise ModuleParseError(
                f"module.yaml 包含重复键: {key}{location}",
                stage="PARSE",
                hint="请删除重复 YAML 键，避免审核内容与实际生效值不一致",
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_mapping_without_duplicate_keys,
)


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
                get_user_modules_path(),
                get_builtin_modules_path(),
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
            source = ModuleSource.BUILTIN if scan_path == get_builtin_modules_path() else ModuleSource.EXTERNAL

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
                f"找不到 module.yaml: {module_path}", stage="PARSE", hint="请确保模块目录包含 module.yaml 文件"
            )

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = yaml.load(f, Loader=_UniqueKeySafeLoader)

            if not data:
                raise ModuleParseError(f"module.yaml 为空: {module_path}", stage="PARSE", hint="请填写模块清单内容")

            removed_fields = [field for field in ALWAYS_REMOVED_MANIFEST_FIELDS if field in data]
            if str(data.get("runtime_api", "")).strip() == REQUIRED_RUNTIME_API:
                removed_fields.extend(field for field in V2_REMOVED_MANIFEST_FIELDS if field in data)
            if removed_fields:
                raise ModuleParseError(
                    f"module.yaml 包含已移除字段: {', '.join(removed_fields)}",
                    stage="PARSE",
                    hint="core-native-v2 使用装饰器声明运行时对象，请删除 0.3 时代的 manifest 字段",
                )

            return ModuleManifest.from_dict(data)
        except ValueError as e:
            raise ModuleParseError(
                str(e),
                stage="PARSE",
                hint="请检查 module.yaml 字段结构是否符合 core-native-v2 协议",
            )
        except yaml.YAMLError as e:
            raise ModuleParseError(f"YAML 解析错误: {e}", stage="PARSE", hint="请检查 YAML 语法是否正确")

    def validate(self, manifest: ModuleManifest, module_path: Path) -> list[str]:
        """校验模块清单。

        规格 5.1.4.2:
            - 命名与唯一性校验
            - 受控模块契约校验

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
                "缺少必填字段: name", stage="VALIDATE", hint="请在 module.yaml 中添加 name 字段"
            )

        runtime_api = str(manifest.runtime_api or "").strip()
        if runtime_api != REQUIRED_RUNTIME_API:
            raise ModuleValidationError(
                f"module.yaml.runtime_api 必须是 {REQUIRED_RUNTIME_API}",
                stage="VALIDATE",
                hint="旧模块不再兼容，请迁移到 core-native-v2 装饰器协议后再加载",
            )

        # 命名规范校验（小写字母、数字、下划线）
        if not MANAGED_NAME_RE.match(manifest.name):
            raise ModuleValidationError(
                f"模块名不符合命名规范: {manifest.name}",
                stage="VALIDATE",
                hint="module.yaml.name 必须以小写字母开头，且只包含小写字母、数字和下划线",
            )

        version = str(manifest.version or "").strip()
        if not is_valid_semver(version):
            raise ModuleValidationError(
                f"无效的 version: {version or '<empty>'}（必须是语义化版本）",
                stage="VALIDATE",
                hint="module.yaml.version 必须是合法语义化版本，如 1.2.3 或 1.2.3-rc.1",
            )

        self._validate_upgrade_source(manifest)
        self._validate_config_defaults(manifest)

        return warnings

    def _validate_upgrade_source(self, manifest: ModuleManifest) -> None:
        upgrade_source = manifest.upgrade_source
        source_type = str(upgrade_source.type or "").strip()
        if not source_type:
            raise ModuleValidationError(
                "缺少必填字段: upgrade_source.type",
                stage="VALIDATE",
                hint="模块必须声明升级源，当前只支持 github_release",
            )
        if source_type != "github_release":
            raise ModuleValidationError(
                f"不支持的 upgrade_source.type: {source_type}",
                stage="VALIDATE",
                hint="第一版模块升级只支持 GitHub Release",
            )

        repo = str(upgrade_source.repo or "").strip()
        if not repo:
            raise ModuleValidationError(
                "缺少必填字段: upgrade_source.repo",
                stage="VALIDATE",
                hint="请在 module.yaml 中声明 owner/repo 形式的 GitHub 仓库",
            )
        if not GITHUB_REPO_RE.match(repo):
            raise ModuleValidationError(
                f"无效的 upgrade_source.repo: {repo}（必须是 owner/repo 形式）",
                stage="VALIDATE",
                hint="upgrade_source.repo 必须是 owner/repo 形式，不能填写完整 URL",
            )

    def _validate_config_defaults(self, manifest: ModuleManifest) -> None:
        for workflow_name in manifest.config_defaults.workflows:
            raise ModuleValidationError(
                f"core-native-v2 不支持 config_defaults.workflows: {workflow_name}",
                stage="VALIDATE",
                hint="对象参数应保存在运行模板，不再通过 module.yaml 绑定到 workflow",
            )

    def load_module(
        self,
        module_path: Path,
        source: ModuleSource,
        *,
        name_hint: str = "",
    ) -> ModuleInfo:
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
                name=name_hint or module_path.name,
                manifest=ModuleManifest(name=name_hint or module_path.name),
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

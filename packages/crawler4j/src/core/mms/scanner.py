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
REMOVED_MANIFEST_FIELDS = ("sdk_version_range",)
REQUIRED_RUNTIME_API = "core-native-v1"


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

            removed_fields = [field for field in REMOVED_MANIFEST_FIELDS if field in data]
            if removed_fields:
                raise ModuleParseError(
                    f"module.yaml 包含已移除字段: {', '.join(removed_fields)}",
                    stage="PARSE",
                    hint="模块必须与当前宿主一起升级，请删除这些兼容范围声明后再继续"
                )

            return ModuleManifest.from_dict(data)
        except ValueError as e:
            raise ModuleParseError(
                str(e),
                stage="PARSE",
                hint="请检查 module.yaml 中 config_defaults 的 YAML 结构是否正确",
            )
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
                "缺少必填字段: name",
                stage="VALIDATE",
                hint="请在 module.yaml 中添加 name 字段"
            )

        runtime_api = str(manifest.runtime_api or "").strip()
        if runtime_api != REQUIRED_RUNTIME_API:
            raise ModuleValidationError(
                f"module.yaml.runtime_api 必须是 {REQUIRED_RUNTIME_API}",
                stage="VALIDATE",
                hint="旧模块不再兼容，请迁移到 core-native-v1 协议后再加载",
            )

        # 命名规范校验（小写字母、数字、下划线）
        if not manifest.name.replace("_", "").isalnum() or not manifest.name.islower():
            warnings.append(f"模块名 '{manifest.name}' 不符合命名规范（应为小写字母、数字、下划线）")

        version = str(manifest.version or "").strip()
        if not is_valid_semver(version):
            raise ModuleValidationError(
                f"无效的 version: {version or '<empty>'}（必须是语义化版本）",
                stage="VALIDATE",
                hint="module.yaml.version 必须是合法语义化版本，如 1.2.3 或 1.2.3-rc.1",
            )

        # 工作流名称唯一性
        workflow_names = [w.name for w in manifest.workflows]
        if len(workflow_names) != len(set(workflow_names)):
            raise ModuleValidationError(
                "工作流名称重复",
                stage="VALIDATE",
                hint="请确保每个工作流有唯一的 name"
            )

        if not workflow_names:
            raise ModuleValidationError(
                "module.yaml.workflows 不能为空",
                stage="VALIDATE",
                hint="至少声明一个 workflow，并让 default_workflow 指向其中之一",
            )

        default_workflow = str(manifest.default_workflow or "").strip()
        if not default_workflow:
            raise ModuleValidationError(
                "缺少必填字段: default_workflow",
                stage="VALIDATE",
                hint="请在 module.yaml 中声明 default_workflow",
            )
        if default_workflow not in workflow_names:
            raise ModuleValidationError(
                f"default_workflow 未在 module.yaml.workflows 中声明: {default_workflow}",
                stage="VALIDATE",
                hint="default_workflow 必须指向已声明的 workflow 名称",
            )

        self._validate_upgrade_source(manifest)
        self._validate_config_defaults(manifest)
        self._validate_ui_extension(manifest)

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
        declared_workflows = {workflow.name for workflow in manifest.workflows}
        for workflow_name in manifest.config_defaults.workflows:
            if workflow_name not in declared_workflows:
                raise ModuleValidationError(
                    f"config_defaults.workflows 包含未声明的 workflow: {workflow_name}",
                    stage="VALIDATE",
                    hint="请先在 module.yaml.workflows 中声明该 workflow，再为其配置默认值",
                )

    def _validate_ui_extension(self, manifest: ModuleManifest) -> None:
        ui_ext = manifest.ui_extension
        seen_page_ids: set[str] = set()
        for item in ui_ext.pages:
            page_id = str(item.id or "").strip()
            if not MANAGED_NAME_RE.match(page_id):
                raise ModuleValidationError(
                    f"无效的 ui_extension.pages[].id: {page_id or '<empty>'}",
                    stage="VALIDATE",
                    hint="页面 ID 只能使用小写字母、数字和下划线，且必须以字母开头",
                )
            if page_id in seen_page_ids:
                raise ModuleValidationError(
                    f"ui_extension.pages[].id 重复: {page_id}",
                    stage="VALIDATE",
                    hint="请确保每个宿主页入口有唯一的 ID",
                )
            seen_page_ids.add(page_id)

            if not str(item.label or "").strip():
                raise ModuleValidationError(
                    f"ui_extension.pages[{page_id}].label 不能为空",
                    stage="VALIDATE",
                    hint="模块详情页导航标签必须显式声明",
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

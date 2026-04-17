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
from src.utils.paths import get_builtin_modules_path, get_user_modules_path

# 忽略的目录
IGNORED_DIRS = {"__pycache__", ".git", ".venv", "node_modules"}
LEGACY_MODULE_FILES = ("config_schema.json", "strategy.yaml")
MANAGED_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
UI_ENTRY_RE = re.compile(r"^ui:[A-Z][A-Za-z0-9_]*$")
GITHUB_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REMOVED_MANIFEST_FIELDS = ("sdk_version_range",)


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

        for legacy_file in LEGACY_MODULE_FILES:
            if (module_path / legacy_file).exists():
                raise ModuleValidationError(
                    f"检测到已废弃的模块声明文件: {legacy_file}",
                    stage="VALIDATE",
                    hint="模块配置与数据表入口已改为宿主集中管理，请删除旧声明式文件并改用 SDK CLI"
                )
        
        # 命名规范校验（小写字母、数字、下划线）
        if not manifest.name.replace("_", "").isalnum() or not manifest.name.islower():
            warnings.append(f"模块名 '{manifest.name}' 不符合命名规范（应为小写字母、数字、下划线）")
        
        # 工作流名称唯一性
        workflow_names = [w.name for w in manifest.workflows]
        if len(workflow_names) != len(set(workflow_names)):
            raise ModuleValidationError(
                "工作流名称重复",
                stage="VALIDATE",
                hint="请确保每个工作流有唯一的 name"
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
        ui_type = str(ui_ext.type or "none").strip() or "none"
        if ui_type not in {"none", "micro_app"}:
            raise ModuleValidationError(
                f"不支持的 ui_extension.type: {ui_type}",
                stage="VALIDATE",
                hint="当前只允许 `none` 或 `micro_app`"
            )

        entry = str(ui_ext.entry or "").strip()
        if entry:
            if ui_type != "micro_app":
                raise ModuleValidationError(
                    "声明 ui_extension.entry 时必须同时设置 ui_extension.type = micro_app",
                    stage="VALIDATE",
                    hint="代码型页面只能通过 SDK `add-ui` 维护"
                )
            if not UI_ENTRY_RE.match(entry):
                raise ModuleValidationError(
                    f"无效的 ui_extension.entry: {entry}",
                    stage="VALIDATE",
                    hint="代码型页面入口必须是 `ui:PageClass` 形式"
                )
        elif ui_type == "micro_app":
            raise ModuleValidationError(
                "ui_extension.type = micro_app 时必须提供 ui_extension.entry",
                stage="VALIDATE",
                hint="请使用 SDK CLI `add-ui <name>` 生成并维护代码型页面入口"
            )

        seen_menu_ids: set[str] = set()
        for item in ui_ext.detail_menu:
            menu_id = str(item.id or "").strip()
            if not MANAGED_NAME_RE.match(menu_id):
                raise ModuleValidationError(
                    f"无效的 detail_menu.id: {menu_id or '<empty>'}",
                    stage="VALIDATE",
                    hint="详情页数据表入口 ID 只能使用小写字母、数字和下划线，且必须以字母开头"
                )
            if menu_id in seen_menu_ids:
                raise ModuleValidationError(
                    f"detail_menu.id 重复: {menu_id}",
                    stage="VALIDATE",
                    hint="请确保每个详情页数据表入口有唯一的 ID"
                )
            seen_menu_ids.add(menu_id)

            expected_entry = f"core:data_table:{menu_id}"
            actual_entry = str(item.entry or "").strip()
            if actual_entry != expected_entry:
                raise ModuleValidationError(
                    f"detail_menu.entry 不受支持: {actual_entry or '<empty>'}",
                    stage="VALIDATE",
                    hint="详情页扩展入口现在只允许 Core 托管的数据表，且 entry 必须与 id 对齐为 `core:data_table:<id>`"
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

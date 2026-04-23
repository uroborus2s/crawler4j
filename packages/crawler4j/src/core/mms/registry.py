"""模块注册表。

规格参考: docs/02-requirements/reference-srs/05-framework-core/05-1-module-management.md (5.1.3.3)

负责：
    - 维护模块注册表
    - 支持查询/列表/刷新
    - 模块安装/卸载/启用/禁用
"""

import importlib
import importlib.util
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from src.core.mms.dev_links import DevModuleLinkStore, get_dev_module_link_store
from src.core.foundation.event_bus import Event, EventType, get_event_bus
from src.core.foundation.logging import logger
from src.core.mms.models import (
    ModuleInfo,
    ModuleInstallError,
    ModuleManifest,
    ModuleSource,
    ModuleStatus,
    WorkflowInfo,
)
from src.core.mms.scanner import ModuleScanner
from src.core.mms.settings_store import ModuleSettingsStore, get_module_settings_store
from src.core.persistence import get_module_data_store
from src.utils.paths import get_app_data_dir

class ModuleRegistry:
    """模块注册表。
    
    规格 5.1.3.3: 维护模块注册表，支持查询/列表/刷新。
    规格 5.1.4.4: 支持安装/卸载/刷新。
    """
    
    def __init__(
        self,
        scanner: ModuleScanner | None = None,
        dev_link_store: DevModuleLinkStore | None = None,
        settings_store: ModuleSettingsStore | None = None,
    ):
        """初始化注册表。
        
        Args:
            scanner: 模块扫描器（可选，用于测试注入）
        """
        self._scanner = scanner or ModuleScanner()
        self._dev_link_store = dev_link_store or get_dev_module_link_store()
        self._settings_store = settings_store or get_module_settings_store()
        self._modules: dict[str, ModuleInfo] = {}
        self._loaded = False
        self._install_dir = get_app_data_dir() / "modules"
    
    def load(self, force: bool = False) -> None:
        """加载所有模块。
        
        Args:
            force: 是否强制重新加载
        """
        if self._loaded and not force:
            return
        
        import sys
        
        # 注入用户模块父目录到 Python 搜索路径，确保 modules 包可被 import
        user_data_path = str(get_app_data_dir())
        if user_data_path not in sys.path:
            sys.path.insert(0, user_data_path)
            logger.info(f"[MMS] 已注入模块搜索路径: {user_data_path}")

        self._modules.clear()
        
        # 发现并加载模块
        candidates = self._scanner.discover()
        
        for module_path, source in candidates:
            module_info = self._scanner.load_module(module_path, source)
            self._merge_loaded_module(module_info)

        for link in self._dev_link_store.list_links():
            module_info = self._scanner.load_module(
                Path(link.source_path),
                ModuleSource.DEV_LINK,
                name_hint=link.module_name,
            )
            self._merge_loaded_module(module_info)

        self._initialize_loaded_module_configs()
        self._sync_loaded_module_data()
        
        self._loaded = True
        logger.info(f"[MMS] 注册表加载完成: {len(self._modules)} 个模块")

    def _merge_loaded_module(self, module_info: ModuleInfo) -> None:
        self._apply_persisted_module_status(module_info)
        existing = self._modules.get(module_info.name)
        if not existing:
            self._modules[module_info.name] = module_info
            return

        if self._source_priority(module_info.source) > self._source_priority(existing.source):
            logger.warning(
                f"[MMS] 模块名称冲突，优先使用 {module_info.source.value}: {module_info.name} "
                f"({existing.path} -> {module_info.path})"
            )
            self._modules[module_info.name] = module_info
            return

        logger.warning(
            f"[MMS] 模块名称冲突，忽略 {module_info.source.value}: {module_info.name} "
            f"({existing.path} vs {module_info.path})"
        )

    def _source_priority(self, source: ModuleSource) -> int:
        priorities = {
            ModuleSource.BUILTIN: 1,
            ModuleSource.EXTERNAL: 2,
            ModuleSource.DEV_LINK: 3,
        }
        return priorities.get(source, 0)

    def _apply_persisted_module_status(self, module_info: ModuleInfo) -> ModuleInfo:
        if module_info.status not in {ModuleStatus.ENABLED, ModuleStatus.DISABLED}:
            return module_info

        persisted = self._settings_store.get_module_status(module_info.name)
        if persisted is not None:
            module_info.status = persisted
        return module_info

    def _initialize_loaded_module_configs(self) -> None:
        for module_info in self._modules.values():
            if module_info.status not in {ModuleStatus.ENABLED, ModuleStatus.DISABLED}:
                continue
            defaults = module_info.manifest.config_defaults
            self._settings_store.ensure_config_defaults_initialized(
                module_info.name,
                defaults.module,
                defaults.workflows,
            )

    def _sync_loaded_module_data(self) -> None:
        for module_info in self._modules.values():
            if module_info.status not in {ModuleStatus.ENABLED, ModuleStatus.DISABLED}:
                continue
            if not module_info.path:
                continue
            try:
                get_module_data_store().sync_manifest_data(
                    module_info.name,
                    Path(module_info.path),
                    module_info.manifest.data,
                )
            except Exception as exc:
                logger.error(f"[MMS] 模块数据契约同步失败 {module_info.name}: {exc}")
                module_info.status = ModuleStatus.INVALID
                module_info.error = str(exc)
                module_info.hint = "请检查 module.yaml.data、data/sql 与 data/seeds 是否符合当前协议"
    
    def refresh(self) -> dict[str, list[str] | int]:
        """刷新注册表。
        
        规格 5.1.4.4: 重新扫描并更新注册表，输出变更摘要。
        
        Returns:
            变更摘要 {"added": [...], "removed": [...], "total": int}
        """
        old_modules = set(self._modules.keys())
        
        self.load(force=True)
        
        new_modules = set(self._modules.keys())
        
        added = new_modules - old_modules
        removed = old_modules - new_modules
        
        summary = {
            "added": list(added),
            "removed": list(removed),
            "total": len(self._modules),
        }
        
        logger.info(f"[MMS] 刷新完成: +{len(added)} -{len(removed)}")
        return summary
    
    # === 安装预览 ===
    
    def validate_source(self, source: str | Path) -> tuple[ModuleManifest, list[str]]:
        """校验模块源并返回预览信息（不执行安装）。
        
        用于安装前预览模块信息，供用户确认后再安装。
        
        Args:
            source: 模块源路径（目录或 .zip 文件）
        
        Returns:
            (manifest, warnings) - 模块清单和警告列表
        
        Raises:
            ModuleInstallError: 校验失败
        """
        import tempfile
        
        source_path = Path(source)
        
        if not source_path.exists():
            raise ModuleInstallError(f"源路径不存在: {source}")
        
        temp_dir = None
        try:
            if source_path.suffix == ".zip":
                # 解压到临时目录进行校验
                temp_dir = tempfile.mkdtemp(prefix="mms_validate_")
                temp_path = Path(temp_dir)
                
                with zipfile.ZipFile(source_path, 'r') as zf:
                    # 安全检查
                    for member in zf.namelist():
                        if member.startswith('/') or '..' in member:
                            raise ModuleInstallError(f"检测到路径穿越攻击: {member}")
                    
                    # 获取根目录
                    root_dirs = {name.split('/')[0] for name in zf.namelist() if '/' in name}
                    if len(root_dirs) != 1:
                        raise ModuleInstallError("ZIP 包结构无效，应仅包含一个根目录")
                    
                    module_name = root_dirs.pop()
                    zf.extractall(temp_path)
                    module_path = temp_path / module_name
            else:
                module_path = source_path
            
            # 解析并校验 manifest
            manifest = self._scanner.parse_manifest(module_path)
            warnings = self._scanner.validate(manifest, module_path)
            
            # 检查是否已安装同名模块
            existing = self.get_module(manifest.name)
            if existing:
                warnings.append(f"将覆盖已安装的模块 '{manifest.name}' (v{existing.manifest.version})")
            
            return manifest, warnings
            
        finally:
            # 清理临时目录
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
    
    # === 安装/卸载 ===
    
    def install(self, source: str | Path) -> ModuleInfo:
        """安装模块。
        
        规格 5.1.4.4: 将模块包复制/解压到受控目录并更新注册表。
        
        Args:
            source: 模块源路径（目录或 .zip 文件）
        
        Returns:
            安装后的模块信息
        
        Raises:
            ModuleInstallError: 安装失败
        """
        source_path = Path(source)
        
        if not source_path.exists():
            raise ModuleInstallError(f"源路径不存在: {source}")
        
        # 确保安装目录存在
        self._install_dir.mkdir(parents=True, exist_ok=True)
        previous_module = None
        
        try:
            if source_path.suffix == ".zip":
                # 解压 ZIP 包
                module_info = self._install_from_zip(source_path)
            elif source_path.is_dir():
                # 复制目录
                module_info = self._install_from_dir(source_path)
            else:
                raise ModuleInstallError(f"不支持的源类型: {source}")

            previous_module = self._modules.get(module_info.name)

            # 安装正式模块时，移除同名开发链接，避免运行时继续优先落到源码目录。
            if self._dev_link_store.delete_link(module_info.name):
                logger.info(f"[MMS] 已移除同名开发链接，切换到安装模块: {module_info.name}")
            
            # 更新注册表
            self._apply_persisted_module_status(module_info)
            self._modules[module_info.name] = module_info
            self._initialize_loaded_module_configs()
            self._sync_loaded_module_data()
            synced_module = self._modules.get(module_info.name)
            if synced_module and synced_module.status == ModuleStatus.INVALID:
                raise ModuleInstallError(synced_module.error or f"模块数据契约同步失败: {module_info.name}")
            logger.info(f"[MMS] 已安装: {module_info.name} v{module_info.manifest.version}")

            event_type = EventType.MODULE_UPGRADED if previous_module and previous_module.source == ModuleSource.EXTERNAL else EventType.MODULE_INSTALLED
            get_event_bus().publish(Event(
                type=event_type,
                module_name=module_info.name,
                data={
                    "module_name": module_info.name,
                    "version": module_info.manifest.version,
                    "source": module_info.source.value,
                },
            ))
            
            return module_info
            
        except Exception as e:
            logger.error(f"[MMS] 安装失败: {e}")
            raise ModuleInstallError(f"安装失败: {e}") from e

    def register_dev_link(self, source_path: str | Path) -> ModuleInfo:
        """注册本地开发模块目录。"""
        module_dir = Path(source_path).expanduser().resolve()
        if not module_dir.exists() or not module_dir.is_dir():
            raise ModuleInstallError(f"开发模块目录不存在: {module_dir}")

        manifest = self._scanner.parse_manifest(module_dir)
        self._scanner.validate(manifest, module_dir)
        self._dev_link_store.upsert_link(manifest.name, module_dir)
        self.load(force=True)

        module = self._modules.get(manifest.name)
        if not module:
            raise ModuleInstallError(f"开发模块注册失败: {manifest.name}")
        return module

    def remove_dev_link(self, module_name: str) -> bool:
        """移除开发模块链接。"""
        removed = self._dev_link_store.delete_link(module_name)
        if removed:
            self.load(force=True)
        return removed

    def list_dev_links(self):
        return self._dev_link_store.list_links()
    
    def _install_from_zip(self, zip_path: Path) -> ModuleInfo:
        """从 ZIP 安装。"""
        temp_dir = Path(tempfile.mkdtemp(prefix="mms_install_", dir=str(self._install_dir)))
        extracted_module_dir: Path | None = None

        try:
            # 防御 zip slip 攻击
            with zipfile.ZipFile(zip_path, 'r') as zf:
                for member in zf.namelist():
                    if member.startswith('/') or '..' in member:
                        raise ModuleInstallError(f"检测到路径穿越攻击: {member}")

                # 提取模块目录（假设 ZIP 根目录是模块目录）
                root_dirs = {name.split('/')[0] for name in zf.namelist() if '/' in name}
                if len(root_dirs) != 1:
                    raise ModuleInstallError("ZIP 包结构无效，应仅包含一个根目录")

                module_dir_name = root_dirs.pop()
                extracted_module_dir = temp_dir / module_dir_name
                zf.extractall(temp_dir)

            if not extracted_module_dir or not extracted_module_dir.exists():
                raise ModuleInstallError("ZIP 安装失败：未找到解压后的模块目录")

            manifest = self._preflight_installable_module(extracted_module_dir)
            return self._activate_staged_module(extracted_module_dir, manifest)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _install_from_dir(self, dir_path: Path) -> ModuleInfo:
        """从目录安装。"""
        temp_dir = Path(tempfile.mkdtemp(prefix="mms_install_dir_", dir=str(self._install_dir)))
        staged_dir = temp_dir / dir_path.name

        try:
            shutil.copytree(dir_path, staged_dir)
            manifest = self._preflight_installable_module(staged_dir)
            return self._activate_staged_module(staged_dir, manifest)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _preflight_installable_module(self, module_dir: Path) -> ModuleManifest:
        manifest = self._scanner.parse_manifest(module_dir)
        warnings = self._scanner.validate(manifest, module_dir)
        for warning in warnings:
            logger.warning(f"[MMS] {module_dir.name}: {warning}")
        self._probe_module_import(manifest.name, module_dir)
        return manifest

    def _resolve_install_target_dir(self, manifest: ModuleManifest) -> Path:
        return self._install_dir / manifest.name

    def _collect_existing_install_dirs(self, manifest: ModuleManifest, target_dir: Path) -> list[Path]:
        install_dirs: list[Path] = []
        existing = self.get_module(manifest.name)
        if existing and existing.source == ModuleSource.EXTERNAL and existing.path:
            install_dirs.append(existing.path)
        if target_dir not in install_dirs and target_dir.exists():
            install_dirs.append(target_dir)
        return [path for path in install_dirs if path.exists()]

    def _activate_staged_module(self, staged_dir: Path, manifest: ModuleManifest) -> ModuleInfo:
        target_dir = self._resolve_install_target_dir(manifest)
        replaced_dirs = self._collect_existing_install_dirs(manifest, target_dir)
        backup_dirs: list[tuple[Path, Path]] = []

        try:
            for replaced_dir in replaced_dirs:
                backup_dir = self._reserve_install_slot(f".{replaced_dir.name}.bak.")
                shutil.move(str(replaced_dir), str(backup_dir))
                backup_dirs.append((replaced_dir, backup_dir))

            shutil.move(str(staged_dir), str(target_dir))
            self._probe_module_import(manifest.name, target_dir)

            return ModuleInfo(
                name=manifest.name,
                manifest=manifest,
                source=ModuleSource.EXTERNAL,
                status=ModuleStatus.ENABLED,
                path=target_dir,
            )
        except Exception:
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            for replaced_dir, backup_dir in reversed(backup_dirs):
                if target_dir.exists():
                    shutil.rmtree(target_dir, ignore_errors=True)
                if backup_dir.exists():
                    shutil.move(str(backup_dir), str(replaced_dir))
            raise
        finally:
            for _, backup_dir in backup_dirs:
                if backup_dir.exists():
                    shutil.rmtree(backup_dir, ignore_errors=True)

    def _reserve_install_slot(self, prefix: str) -> Path:
        reserved_dir = Path(tempfile.mkdtemp(prefix=prefix, dir=str(self._install_dir)))
        shutil.rmtree(reserved_dir, ignore_errors=True)
        return reserved_dir

    def _probe_module_import(self, module_name: str, module_dir: Path) -> None:
        package_root = module_dir.resolve()
        package_init = package_root / "__init__.py"
        if not package_init.exists():
            raise ModuleInstallError(f"模块目录缺少 __init__.py: {package_root}")

        prefix = f"{module_name}."
        previous_modules = {
            loaded_name: loaded_module
            for loaded_name, loaded_module in list(sys.modules.items())
            if loaded_name == module_name or loaded_name.startswith(prefix)
        }

        for loaded_name in previous_modules:
            sys.modules.pop(loaded_name, None)

        importlib.invalidate_caches()
        spec = importlib.util.spec_from_file_location(
            module_name,
            package_init,
            submodule_search_locations=[str(package_root)],
        )
        if spec is None or spec.loader is None:
            raise ModuleInstallError(f"模块导入预检失败，无法加载: {package_root}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:
            raise ModuleInstallError(f"模块导入预检失败: {exc}") from exc
        finally:
            for loaded_name in list(sys.modules):
                if loaded_name == module_name or loaded_name.startswith(prefix):
                    sys.modules.pop(loaded_name, None)
            sys.modules.update(previous_modules)
    
    def uninstall(self, module_name: str, keep_settings: bool = False) -> bool:
        """卸载模块。
        
        规格 5.1.4.4: 移除模块目录与注册表条目。
        
        Args:
            module_name: 模块名
            keep_settings: 是否保留配置
        
        Returns:
            是否卸载成功
        """
        module = self.get_module(module_name)
        if not module:
            logger.warning(f"[MMS] 模块不存在: {module_name}")
            return False
        
        # 内置模块不可卸载
        if module.source == ModuleSource.BUILTIN:
            logger.warning(f"[MMS] 无法卸载内置模块: {module_name}")
            return False
        
        try:
            # 删除目录
            if module.path and module.path.exists():
                shutil.rmtree(module.path)

            self._settings_store.clear_module_records(module_name, keep_settings=keep_settings)
            get_module_data_store().clear_module_data(module_name)
            
            # 从注册表移除
            del self._modules[module_name]

            get_event_bus().publish(Event(
                type=EventType.MODULE_UNINSTALLED,
                module_name=module_name,
                data={"module_name": module_name},
            ))
            
            logger.info(f"[MMS] 已卸载: {module_name}")
            return True
            
        except Exception as e:
            logger.error(f"[MMS] 卸载失败: {e}")
            return False
    
    # === 查询接口 ===
    
    def list_modules(self) -> list[ModuleInfo]:
        """列出所有模块。"""
        self.load()
        return list(self._modules.values())
    
    def get_module(self, module_name: str) -> ModuleInfo | None:
        """获取指定模块。"""
        cached = self._modules.get(module_name)
        if cached:
            return cached
        self.load()
        return self._modules.get(module_name)
    
    def get_workflows(self, module_name: str) -> list[WorkflowInfo]:
        """获取模块的工作流列表。"""
        module = self.get_module(module_name)
        if module and module.status == ModuleStatus.ENABLED:
            return module.manifest.workflows
        return []
    
    def get_enabled_modules(self) -> list[ModuleInfo]:
        """获取所有启用的模块。"""
        self.load()
        return [m for m in self._modules.values() if m.status == ModuleStatus.ENABLED]
    
    # === 状态管理 ===
    
    def enable_module(self, module_name: str) -> bool:
        """启用模块。"""
        module = self.get_module(module_name)
        if not module:
            return False
        
        if module.status == ModuleStatus.INVALID:
            logger.warning(f"[MMS] 无法启用无效模块: {module_name}")
            return False
        
        module.status = ModuleStatus.ENABLED
        self._settings_store.set_module_status(module_name, ModuleStatus.ENABLED)
        logger.info(f"[MMS] 已启用: {module_name}")
        
        # 发布事件
        get_event_bus().publish(Event(
            type=EventType.MODULE_ENABLED,
            module_name=module_name,
            data={"module_name": module_name}
        ))
        
        return True
    
    def disable_module(self, module_name: str) -> bool:
        """禁用模块。"""
        module = self.get_module(module_name)
        if not module:
            return False
        
        module.status = ModuleStatus.DISABLED
        self._settings_store.set_module_status(module_name, ModuleStatus.DISABLED)
        logger.info(f"[MMS] 已禁用: {module_name}")
        
        # 发布事件，通知 ATM 挂起相关任务
        get_event_bus().publish(Event(
            type=EventType.MODULE_DISABLED,
            module_name=module_name,
            data={"module_name": module_name}
        ))
        
        return True


# 全局单例
_registry: ModuleRegistry | None = None


def get_module_registry() -> ModuleRegistry:
    """获取全局 ModuleRegistry 实例。"""
    global _registry
    if _registry is None:
        _registry = ModuleRegistry()
    return _registry

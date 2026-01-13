"""模块注册表。

规格参考: docs/srs/05-framework-core/05-1-module-management.md (5.1.3.3)

负责：
    - 维护模块注册表
    - 支持查询/列表/刷新
    - 模块安装/卸载/启用/禁用
"""

import shutil
import zipfile
from pathlib import Path

from src.core.foundation.event_bus import Event, EventType, get_event_bus
from src.core.foundation.logging import logger
from src.core.mms.models import (
    ModuleInfo,
    ModuleManifest,
    ModuleSource,
    ModuleStatus,
    WorkflowInfo,
)
from src.core.mms.scanner import ModuleScanner, get_module_scanner
from src.utils.paths import get_app_data_dir


class ModuleInstallError(Exception):
    """模块安装错误。"""
    pass


class ModuleRegistry:
    """模块注册表。
    
    规格 5.1.3.3: 维护模块注册表，支持查询/列表/刷新。
    规格 5.1.4.4: 支持安装/卸载/刷新。
    """
    
    def __init__(self, scanner: ModuleScanner | None = None):
        """初始化注册表。
        
        Args:
            scanner: 模块扫描器（可选，用于测试注入）
        """
        self._scanner = scanner or get_module_scanner()
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
        
        self._modules.clear()
        
        # 发现并加载模块
        candidates = self._scanner.discover()
        
        for module_path, source in candidates:
            module_info = self._scanner.load_module(module_path, source)
            
            # 检查名称冲突
            if module_info.name in self._modules:
                existing = self._modules[module_info.name]
                logger.warning(
                    f"[MMS] 模块名称冲突: {module_info.name} "
                    f"({existing.path} vs {module_info.path})"
                )
                continue
            
            self._modules[module_info.name] = module_info
        
        self._loaded = True
        logger.info(f"[MMS] 注册表加载完成: {len(self._modules)} 个模块")
    
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
        
        try:
            if source_path.suffix == ".zip":
                # 解压 ZIP 包
                module_info = self._install_from_zip(source_path)
            elif source_path.is_dir():
                # 复制目录
                module_info = self._install_from_dir(source_path)
            else:
                raise ModuleInstallError(f"不支持的源类型: {source}")
            
            # 更新注册表
            self._modules[module_info.name] = module_info
            logger.info(f"[MMS] 已安装: {module_info.name} v{module_info.manifest.version}")
            
            return module_info
            
        except Exception as e:
            logger.error(f"[MMS] 安装失败: {e}")
            raise ModuleInstallError(f"安装失败: {e}") from e
    
    def _install_from_zip(self, zip_path: Path) -> ModuleInfo:
        """从 ZIP 安装。"""
        # 防御 zip slip 攻击
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.namelist():
                if member.startswith('/') or '..' in member:
                    raise ModuleInstallError(f"检测到路径穿越攻击: {member}")
            
            # 提取模块名（假设 ZIP 根目录是模块名）
            root_dirs = {name.split('/')[0] for name in zf.namelist() if '/' in name}
            if len(root_dirs) != 1:
                raise ModuleInstallError("ZIP 包结构无效，应仅包含一个根目录")
            
            module_name = root_dirs.pop()
            target_dir = self._install_dir / module_name
            
            # 解压
            zf.extractall(self._install_dir)
        
        # 加载模块信息
        return self._scanner.load_module(target_dir, ModuleSource.EXTERNAL)
    
    def _install_from_dir(self, dir_path: Path) -> ModuleInfo:
        """从目录安装。"""
        module_name = dir_path.name
        target_dir = self._install_dir / module_name
        
        # 复制目录
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(dir_path, target_dir)
        
        # 加载模块信息
        return self._scanner.load_module(target_dir, ModuleSource.EXTERNAL)
    
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
            
            # 从注册表移除
            del self._modules[module_name]
            
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

"""模块加载器

负责扫描、加载和管理任务模块。
"""

import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from src.plugins.module_models import Module, ModuleInfo, WorkflowInfo
from src.plugins.script_executor import ScriptExecutor
from src.utils.logger import logger

if TYPE_CHECKING:
    from crawler4j_sdk import TaskFlow, TaskScript


class ModuleLoader:
    """模块加载器
    
    职责：
    1. 扫描 modules/ 目录下的所有模块
    2. 验证模块结构完整性
    3. 加载模块元信息和配置
    4. 安装外部模块（zip/git）
    """
    
    _instance: "ModuleLoader | None" = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._modules: dict[str, Module] = {}
        self._base_path: Path | None = None
        self._executor = ScriptExecutor()
        self._initialized = True
    
    def set_base_path(self, path: str | Path) -> None:
        """设置模块根目录"""
        self._base_path = Path(path)
        self._base_path.mkdir(parents=True, exist_ok=True)
    
    def scan_modules(self, base_path: str | Path | None = None) -> list[ModuleInfo]:
        """扫描并加载所有模块
        
        Args:
            base_path: 模块根目录，默认使用已设置的路径
            
        Returns:
            模块信息列表
        """
        if base_path:
            self.set_base_path(base_path)
        
        if not self._base_path or not self._base_path.exists():
            logger.warning("模块目录不存在")
            return []
        
        self._modules.clear()
        loaded = []
        
        for module_dir in self._base_path.iterdir():
            if not module_dir.is_dir():
                continue
            
            # 跳过以下划线或点开头的目录
            if module_dir.name.startswith(("_", ".")):
                continue
            
            try:
                module = self._load_module_from_dir(module_dir)
                if module:
                    self._modules[module.info.name] = module
                    loaded.append(module.info)
                    logger.info(f"✅ 加载模块: {module.info.display_name} ({module.info.name})")
            except Exception as e:
                logger.error(f"❌ 加载模块失败 [{module_dir.name}]: {e}")
        
        logger.info(f"📦 共加载 {len(loaded)} 个模块")
        return loaded
    
    def _load_module_from_dir(self, module_dir: Path) -> Module | None:
        """从目录加载模块"""
        # 检查 module.yaml
        yaml_path = module_dir / "module.yaml"
        if not yaml_path.exists():
            logger.warning(f"模块缺少 module.yaml: {module_dir.name}")
            return None
        
        # 解析元信息
        info = self._parse_module_yaml(yaml_path)
        info.path = module_dir
        
        # 加载任务链
        workflows: dict[str, type] = {}
        workflows_dir = module_dir / "workflows"
        if workflows_dir.exists():
            for wf_file in workflows_dir.glob("*.py"):
                if wf_file.name.startswith("_"):
                    continue
                try:
                    wf_class = self._executor.load_script(wf_file)
                    name = wf_class.name or wf_file.stem
                    workflows[name] = wf_class
                except Exception as e:
                    logger.warning(f"加载任务链失败 [{wf_file.name}]: {e}")
        
        # 加载子任务
        tasks: dict[str, type] = {}
        tasks_dir = module_dir / "tasks"
        if tasks_dir.exists():
            for task_file in tasks_dir.glob("*.py"):
                if task_file.name.startswith("_"):
                    continue
                try:
                    task_class = self._executor.load_script(task_file)
                    name = task_class.name or task_file.stem
                    tasks[name] = task_class
                    info.tasks.append(name)
                except Exception as e:
                    logger.warning(f"加载子任务失败 [{task_file.name}]: {e}")
        
        return Module(info=info, workflows=workflows, tasks=tasks)
    
    def _parse_module_yaml(self, yaml_path: Path) -> ModuleInfo:
        """解析 module.yaml"""
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        
        # 解析任务链信息
        workflows = []
        for wf in data.get("workflows", []):
            if isinstance(wf, dict):
                workflows.append(WorkflowInfo(
                    name=wf.get("name", ""),
                    display_name=wf.get("display_name", ""),
                    description=wf.get("description", ""),
                    config=wf.get("config", {}),
                ))
        
        return ModuleInfo(
            name=data.get("name", yaml_path.parent.name),
            display_name=data.get("display_name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            config=data.get("config", {}),
            workflows=workflows,
        )
    
    def get_module(self, name: str) -> Module | None:
        """获取已加载的模块"""
        return self._modules.get(name)
    
    def list_modules(self) -> list[ModuleInfo]:
        """列出所有已加载模块"""
        return [m.info for m in self._modules.values()]
    
    def get_workflow(self, module_name: str, workflow_name: str) -> type | None:
        """获取指定模块的任务链类
        
        Args:
            module_name: 模块名
            workflow_name: 任务链名
            
        Returns:
            TaskFlow 子类或 None
        """
        module = self.get_module(module_name)
        if module:
            return module.get_workflow(workflow_name)
        return None
    
    def get_task(self, module_name: str, task_name: str) -> type | None:
        """获取指定模块的子任务类"""
        module = self.get_module(module_name)
        if module:
            return module.get_task(task_name)
        return None
    
    # === 模块安装 ===
    
    def install_module(self, source: str) -> bool:
        """安装外部模块
        
        Args:
            source: 模块来源（本地zip路径或Git URL）
            
        Returns:
            是否成功
        """
        if not self._base_path:
            logger.error("未设置模块目录")
            return False
        
        if source.endswith(".zip"):
            return self._install_from_zip(Path(source))
        elif source.startswith(("http://", "https://", "git@")):
            return self._install_from_git(source)
        elif Path(source).is_dir():
            return self._install_from_dir(Path(source))
        else:
            logger.error(f"不支持的模块来源: {source}")
            return False
    
    def _install_from_zip(self, zip_path: Path) -> bool:
        """从 zip 文件安装"""
        if not zip_path.exists():
            logger.error(f"文件不存在: {zip_path}")
            return False
        
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # 解压
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(tmpdir)
                
                # 查找 module.yaml
                tmp_path = Path(tmpdir)
                yaml_files = list(tmp_path.rglob("module.yaml"))
                if not yaml_files:
                    logger.error("zip 中未找到 module.yaml")
                    return False
                
                module_root = yaml_files[0].parent
                info = self._parse_module_yaml(yaml_files[0])
                
                # 复制到模块目录
                target = self._base_path / info.name
                if target.exists():
                    shutil.rmtree(target)
                shutil.copytree(module_root, target)
                
                logger.info(f"✅ 已安装模块: {info.name}")
                return True
                
        except Exception as e:
            logger.error(f"安装模块失败: {e}")
            return False
    
    def _install_from_git(self, url: str) -> bool:
        """从 Git 仓库安装"""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                # Clone
                result = subprocess.run(
                    ["git", "clone", "--depth", "1", url, tmpdir],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    logger.error(f"git clone 失败: {result.stderr}")
                    return False
                
                # 查找模块
                tmp_path = Path(tmpdir)
                yaml_path = tmp_path / "module.yaml"
                if not yaml_path.exists():
                    logger.error("仓库中未找到 module.yaml")
                    return False
                
                info = self._parse_module_yaml(yaml_path)
                
                # 复制到模块目录
                target = self._base_path / info.name
                if target.exists():
                    shutil.rmtree(target)
                
                # 排除 .git 目录
                shutil.copytree(
                    tmp_path, target,
                    ignore=shutil.ignore_patterns(".git", "__pycache__")
                )
                
                logger.info(f"✅ 已从 Git 安装模块: {info.name}")
                return True
                
        except Exception as e:
            logger.error(f"从 Git 安装失败: {e}")
            return False
    
    def _install_from_dir(self, source_dir: Path) -> bool:
        """从目录安装（复制）"""
        yaml_path = source_dir / "module.yaml"
        if not yaml_path.exists():
            logger.error(f"目录中未找到 module.yaml: {source_dir}")
            return False
        
        try:
            info = self._parse_module_yaml(yaml_path)
            target = self._base_path / info.name
            
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source_dir, target)
            
            logger.info(f"✅ 已安装模块: {info.name}")
            return True
        except Exception as e:
            logger.error(f"安装失败: {e}")
            return False
    
    def uninstall_module(self, name: str) -> bool:
        """卸载模块"""
        if name not in self._modules:
            logger.warning(f"模块未加载: {name}")
            return False
        
        module = self._modules[name]
        module_path = module.info.path
        
        try:
            if module_path.exists():
                shutil.rmtree(module_path)
            del self._modules[name]
            logger.info(f"✅ 已卸载模块: {name}")
            return True
        except Exception as e:
            logger.error(f"卸载失败: {e}")
            return False
    
    def validate_module(self, path: str | Path) -> tuple[bool, list[str]]:
        """验证模块结构
        
        Returns:
            (是否有效, 错误列表)
        """
        path = Path(path)
        errors = []
        
        # 检查 module.yaml
        yaml_path = path / "module.yaml"
        if not yaml_path.exists():
            errors.append("缺少 module.yaml")
            return False, errors
        
        try:
            info = self._parse_module_yaml(yaml_path)
            if not info.name:
                errors.append("module.yaml 中缺少 name 字段")
        except Exception as e:
            errors.append(f"解析 module.yaml 失败: {e}")
            return False, errors
        
        # 检查目录结构
        if not (path / "workflows").exists() and not (path / "tasks").exists():
            errors.append("缺少 workflows/ 或 tasks/ 目录")
        
        return len(errors) == 0, errors


# 全局单例
_module_loader: ModuleLoader | None = None


def get_module_loader() -> ModuleLoader:
    """获取全局 ModuleLoader 实例"""
    global _module_loader
    if _module_loader is None:
        _module_loader = ModuleLoader()
    return _module_loader

"""脚本管理器 - 管理任务脚本的加载和重载。"""

from pathlib import Path
from typing import Type

from crawler4j_sdk import TaskScript
from src.plugins.script_executor import ScriptExecutor
from src.utils.logger import logger


class ScriptManager:
    """脚本管理器
    
    职责：
    1. 管理脚本目录
    2. 加载所有脚本
    3. 提供重载功能
    """
    
    _instance: "ScriptManager | None" = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._executor = ScriptExecutor()
        self._scripts: dict[str, Type[TaskScript]] = {}
        self._script_paths: dict[str, Path] = {}  # name -> path 映射
        self._directories: list[Path] = []
        self._initialized = True
    
    def add_directory(self, path: str | Path) -> bool:
        """添加脚本目录
        
        Args:
            path: 目录路径
            
        Returns:
            是否成功
        """
        path = Path(path)
        if not path.exists():
            logger.warning(f"脚本目录不存在: {path}")
            return False
        
        if not path.is_dir():
            logger.warning(f"路径不是目录: {path}")
            return False
        
        if path not in self._directories:
            self._directories.append(path)
            logger.info(f"✅ 添加脚本目录: {path}")
            return True
        
        return False
    
    def remove_directory(self, path: str | Path) -> bool:
        """移除脚本目录"""
        path = Path(path)
        if path in self._directories:
            self._directories.remove(path)
            logger.info(f"🗑️ 移除脚本目录: {path}")
            return True
        return False
    
    def get_directories(self) -> list[Path]:
        """获取所有脚本目录"""
        return self._directories.copy()

    def load_all(self) -> int:
        """加载所有目录的脚本
        
        Returns:
            成功加载的脚本数量
        """
        count = 0
        self._scripts.clear()
        self._script_paths.clear()
        
        for directory in self._directories:
            count += self._load_directory(directory)
        
        logger.info(f"📦 共加载 {count} 个脚本")
        return count
    
    def _load_directory(self, directory: Path) -> int:
        """加载单个目录的脚本"""
        count = 0
        
        for script_file in directory.glob("*.py"):
            # 跳过以下划线开头的文件
            if script_file.name.startswith("_"):
                continue
            
            try:
                script_class = self._executor.load_script(script_file)
                name = script_class.name or script_file.stem
                
                self._scripts[name] = script_class
                self._script_paths[name] = script_file
                count += 1
                
            except Exception as e:
                logger.error(f"❌ 加载脚本失败 [{script_file.name}]: {e}")
        
        return count

    def reload_all(self) -> int:
        """重载所有脚本
        
        Returns:
            成功重载的脚本数量
        """
        logger.info("🔄 开始重载所有脚本...")
        return self.load_all()
    
    def reload_script(self, name: str) -> bool:
        """重载单个脚本
        
        Args:
            name: 脚本名称
            
        Returns:
            是否成功
        """
        if name not in self._script_paths:
            logger.warning(f"脚本不存在: {name}")
            return False
        
        script_path = self._script_paths[name]
        
        try:
            script_class = self._executor.load_script(script_path)
            self._scripts[name] = script_class
            logger.info(f"🔄 重载脚本: {name}")
            return True
        except Exception as e:
            logger.error(f"重载脚本失败 [{name}]: {e}")
            return False

    def get_script(self, name: str) -> Type[TaskScript] | None:
        """获取脚本类
        
        Args:
            name: 脚本名称
            
        Returns:
            TaskScript子类或None
        """
        return self._scripts.get(name)
    
    def get_all_scripts(self) -> dict[str, Type[TaskScript]]:
        """获取所有已加载的脚本"""
        return self._scripts.copy()
    
    def list_scripts(self) -> list[dict]:
        """列出所有脚本信息
        
        Returns:
            脚本信息列表
        """
        result = []
        for name, script_class in self._scripts.items():
            result.append({
                "name": name,
                "display_name": script_class.display_name or name,
                "description": script_class.description or "",
                "path": str(self._script_paths.get(name, "")),
            })
        return result


# 全局单例
_script_manager: ScriptManager | None = None


def get_script_manager() -> ScriptManager:
    """获取全局ScriptManager实例"""
    global _script_manager
    if _script_manager is None:
        _script_manager = ScriptManager()
    return _script_manager

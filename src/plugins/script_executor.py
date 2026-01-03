"""脚本执行器 - 安全沙箱执行任务脚本。"""

import ast
import importlib.util
from pathlib import Path
from typing import Type

from crawler4j_sdk import TaskContext, TaskResult, TaskScript
from src.utils.logger import logger


class SecurityError(Exception):
    """安全检查异常"""
    pass


# 禁止导入的模块
BLOCKED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "socket",
    "importlib",
    "builtins",
    "ctypes",
    "multiprocessing",
    "threading",
    "signal",
    "resource",
}

# 禁止调用的函数
BLOCKED_FUNCTIONS = {
    "eval",
    "exec",
    "compile",
    "open",
    "__import__",
    "globals",
    "locals",
    "vars",
    "dir",
    "getattr",
    "setattr",
    "delattr",
}


class ScriptExecutor:
    """脚本执行器
    
    职责：
    1. 加载脚本文件
    2. 安全检查
    3. 执行脚本
    """

    def load_script(self, script_path: Path) -> Type[TaskScript]:
        """加载脚本类
        
        Args:
            script_path: 脚本文件路径
            
        Returns:
            TaskScript子类
            
        Raises:
            FileNotFoundError: 脚本不存在
            SecurityError: 安全检查失败
            ValueError: 未找到TaskScript子类
        """
        if not script_path.exists():
            raise FileNotFoundError(f"脚本不存在: {script_path}")
        
        # 读取脚本内容
        code = script_path.read_text(encoding="utf-8")
        
        # 安全检查
        self._security_check(code, script_path.name)
        
        # 动态导入
        spec = importlib.util.spec_from_file_location(
            script_path.stem, str(script_path)
        )
        if not spec or not spec.loader:
            raise ValueError(f"无法加载脚本: {script_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        # 查找TaskScript子类
        for name in dir(module):
            obj = getattr(module, name)
            if (isinstance(obj, type) and 
                issubclass(obj, TaskScript) and 
                obj is not TaskScript):
                logger.info(f"✅ 加载脚本: {obj.name or script_path.stem}")
                return obj
        
        raise ValueError(f"脚本中未找到TaskScript子类: {script_path}")

    def _security_check(self, code: str, filename: str) -> None:
        """静态安全检查
        
        使用AST分析代码，检查是否有危险导入或调用。
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            raise SecurityError(f"语法错误: {e}")
        
        for node in ast.walk(tree):
            # 检查禁止的import
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_root = alias.name.split(".")[0]
                    if module_root in BLOCKED_MODULES:
                        raise SecurityError(
                            f"[{filename}] 禁止导入模块: {alias.name}"
                        )
            
            # 检查禁止的from import
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    module_root = node.module.split(".")[0]
                    if module_root in BLOCKED_MODULES:
                        raise SecurityError(
                            f"[{filename}] 禁止导入模块: {node.module}"
                        )
            
            # 检查危险函数调用
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in BLOCKED_FUNCTIONS:
                        raise SecurityError(
                            f"[{filename}] 禁止调用函数: {node.func.id}"
                        )

    async def execute(
        self, 
        script_class: Type[TaskScript], 
        ctx: TaskContext
    ) -> TaskResult:
        """执行脚本
        
        Args:
            script_class: TaskScript子类
            ctx: 执行上下文
            
        Returns:
            TaskResult
        """
        instance = script_class()
        
        try:
            # 初始化钩子
            await instance.on_init(ctx)
            
            # 执行主方法
            result = await instance.execute(ctx)
            
            return result
            
        except Exception as e:
            ctx.logger.error(f"脚本执行异常: {e}")
            
            # 错误钩子
            try:
                await instance.on_error(ctx, e)
            except Exception as hook_error:
                ctx.logger.error(f"错误钩子执行失败: {hook_error}")
            
            return TaskResult.fail(str(e), error=str(e))
            
        finally:
            # 清理钩子
            try:
                await instance.on_cleanup(ctx)
            except Exception as cleanup_error:
                ctx.logger.warning(f"清理钩子执行失败: {cleanup_error}")

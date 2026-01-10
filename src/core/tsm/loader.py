"""策略加载器。

规格参考: docs/srs/05-framework-core/05-3-task-strategy-management.md

负责：
    - 从 YAML 文件加载策略
    - 策略合并（Global -> Module -> Task）
    - 策略缓存与热更新
"""

from pathlib import Path

import yaml

from src.core.tsm.models import DEFAULT_STRATEGY, StrategyProfile
from src.utils.logger import logger


class StrategyLoader:
    """策略加载器。
    
    规格 5.3.2 策略生效范围:
        1. Task Level: 最高优先
        2. Module Level: 其次
        3. Global Level: 最低
    """
    
    def __init__(self, strategies_dir: Path | None = None):
        """初始化策略加载器。
        
        Args:
            strategies_dir: 策略文件目录
        """
        self.strategies_dir = strategies_dir
        self._cache: dict[str, StrategyProfile] = {}
        self._global_strategy: StrategyProfile = DEFAULT_STRATEGY
    
    def load_global(self, name: str = "default") -> StrategyProfile:
        """加载全局策略。
        
        Args:
            name: 策略名称
        
        Returns:
            全局策略
        """
        # 尝试从缓存获取
        cache_key = f"global:{name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 尝试从文件加载
        if self.strategies_dir:
            yaml_path = self.strategies_dir / f"{name}.yaml"
            if yaml_path.exists():
                strategy = self._load_from_yaml(yaml_path)
                self._cache[cache_key] = strategy
                return strategy
        
        # 返回默认策略
        return DEFAULT_STRATEGY
    
    def load_module_strategy(self, module_name: str) -> StrategyProfile | None:
        """加载模块策略。"""
        cache_key = f"module:{module_name}"
        return self._cache.get(cache_key)
    
    def set_module_strategy(self, module_name: str, strategy: StrategyProfile) -> None:
        """设置模块策略。"""
        cache_key = f"module:{module_name}"
        self._cache[cache_key] = strategy
    
    def resolve(
        self,
        module_name: str | None = None,
        task_override: StrategyProfile | None = None,
    ) -> StrategyProfile:
        """解析最终生效的策略。
        
        规格 5.3.2: Task > Module > Global
        
        Args:
            module_name: 模块名（用于加载模块级策略）
            task_override: 任务级策略覆盖
        
        Returns:
            合并后的最终策略
        """
        # 1. 从全局策略开始
        result = self._global_strategy
        
        # 2. 合并模块策略
        if module_name:
            module_strategy = self.load_module_strategy(module_name)
            if module_strategy:
                result = result.merge(module_strategy)
        
        # 3. 合并任务策略
        if task_override:
            result = result.merge(task_override)
        
        return result
    
    def reload(self) -> None:
        """重新加载所有策略（热更新）。"""
        self._cache.clear()
        self._global_strategy = self.load_global()
        logger.info("[TSM] 策略已重新加载")
    
    def _load_from_yaml(self, path: Path) -> StrategyProfile:
        """从 YAML 文件加载策略。"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            
            if not data:
                return DEFAULT_STRATEGY
            
            return StrategyProfile.from_dict(data)
        except Exception as e:
            logger.error(f"[TSM] 加载策略失败: {path} - {e}")
            return DEFAULT_STRATEGY


# 全局单例
_strategy_loader: StrategyLoader | None = None


def get_strategy_loader() -> StrategyLoader:
    """获取全局 StrategyLoader 实例。"""
    global _strategy_loader
    if _strategy_loader is None:
        _strategy_loader = StrategyLoader()
    return _strategy_loader

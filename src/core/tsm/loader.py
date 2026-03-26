"""策略加载器。

负责加载、保存和管理 TaskStrategy 对象。
支持从 YAML 文件加载。
"""

import os
from pathlib import Path
from typing import Dict, List, Optional

from src.core.foundation.logging import logger
from src.core.tsm.models import TaskStrategy
from src.utils.paths import get_config_dir


class StrategyLoader:
    """策略加载与管理。"""

    def __init__(self, config_dir: Optional[Path] = None):
        self._config_dir = config_dir or (get_config_dir() / "strategies")
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._strategies: Dict[str, TaskStrategy] = {}
        self._load_all()

    def _load_all(self):
        """加载加载所有策略文件。"""
        self._strategies.clear()
        if not self._config_dir.exists():
            return

        for f in self._config_dir.glob("*.yaml"):
            try:
                content = f.read_text(encoding="utf-8")
                strategy = TaskStrategy.from_yaml(content)
                self._strategies[strategy.id] = strategy
            except Exception as e:
                logger.error(f"[TSM] 加载策略失败 {f.name}: {e}")

    def get(self, strategy_id: str) -> Optional[TaskStrategy]:
        """获取策略。"""
        return self._strategies.get(strategy_id)

    def list_all(self) -> List[TaskStrategy]:
        """列出所有策略。"""
        return list(self._strategies.values())

    def save(self, strategy: TaskStrategy) -> None:
        """保存策略。"""
        file_path = self._config_dir / f"{strategy.id}.yaml"
        try:
            file_path.write_text(strategy.to_yaml(), encoding="utf-8")
            self._strategies[strategy.id] = strategy
            logger.info(f"[TSM] 策略已保存: {strategy.id}")
        except Exception as e:
            logger.error(f"[TSM] 保存策略失败: {e}")
            raise

    def delete(self, strategy_id: str) -> None:
        """删除策略。"""
        if strategy_id in self._strategies:
            file_path = self._config_dir / f"{strategy_id}.yaml"
            if file_path.exists():
                os.remove(file_path)
            del self._strategies[strategy_id]
            logger.info(f"[TSM] 策略已删除: {strategy_id}")


# 全局单例
_loader: Optional[StrategyLoader] = None


def get_strategy_loader() -> StrategyLoader:
    """获取全局 StrategyLoader。"""
    global _loader
    if _loader is None:
        _loader = StrategyLoader()
    return _loader


def init_strategy_loader(config_dir: Path) -> None:
    """初始化全局 StrategyLoader。"""
    global _loader
    _loader = StrategyLoader(config_dir)

"""TSM UI 模块。

导出:
    - StrategyListWidget: 策略列表页面
    - StrategyDetailDialog: 策略详情编辑弹窗
"""

from src.core.tsm.ui.strategy_detail_dialog import StrategyDetailDialog
from src.core.tsm.ui.strategy_list_widget import StrategyListWidget

__all__ = [
    "StrategyListWidget",
    "StrategyDetailDialog",
]

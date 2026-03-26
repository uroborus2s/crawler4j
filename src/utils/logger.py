"""旧 logger 导入路径兼容层。"""

from __future__ import annotations

import logging

try:
    from src.core.foundation.logging import logger as logger
except Exception:  # pragma: no cover - 仅在 Qt 运行时不可用时兜底
    logger = logging.getLogger("crawler4j.compat")


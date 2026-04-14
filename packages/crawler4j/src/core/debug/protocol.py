"""Debug worker and service event protocol."""

from __future__ import annotations

import json
from typing import Any


DEBUG_EVENT_PREFIX = "__CRAWLER4J_DEBUG__"


def encode_debug_event(payload: dict[str, Any]) -> str:
    return DEBUG_EVENT_PREFIX + json.dumps(payload, ensure_ascii=False)


def decode_debug_event(line: str) -> dict[str, Any] | None:
    if not line.startswith(DEBUG_EVENT_PREFIX):
        return None

    raw = line[len(DEBUG_EVENT_PREFIX):].strip()
    if not raw:
        return None
    return json.loads(raw)

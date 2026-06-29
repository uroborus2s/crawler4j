"""Environment fingerprint validation metadata helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

FINGERPRINT_VALIDATION_NAMESPACE = "fingerprint.validation"
FINGERPRINT_VALIDATION_STATUS = "status"
FINGERPRINT_VALIDATION_REASON = "reason"
FINGERPRINT_VALIDATION_DETAIL = "detail"
FINGERPRINT_VALIDATION_LAST_CHECKED_AT = "last_checked_at"

FINGERPRINT_VALIDATION_PASSED = "passed"
FINGERPRINT_VALIDATION_RISK = "risk"


@dataclass(frozen=True, slots=True)
class FingerprintValidationSummary:
    status: str
    reason: str
    detail: str
    last_checked_at: int | None = None

    @property
    def is_risk(self) -> bool:
        return self.status == FINGERPRINT_VALIDATION_RISK


def fingerprint_validation_from_metadata(metadata: Any) -> FingerprintValidationSummary:
    data = metadata if isinstance(metadata, dict) else {}
    return FingerprintValidationSummary(
        status=str(data.get(FINGERPRINT_VALIDATION_STATUS) or "").strip(),
        reason=str(data.get(FINGERPRINT_VALIDATION_REASON) or "").strip(),
        detail=str(data.get(FINGERPRINT_VALIDATION_DETAIL) or "").strip(),
        last_checked_at=_as_int(data.get(FINGERPRINT_VALIDATION_LAST_CHECKED_AT)),
    )


def is_fingerprint_validation_risk(metadata: Any) -> bool:
    return fingerprint_validation_from_metadata(metadata).is_risk


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

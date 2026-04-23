"""crawler4j-contracts 根导出面稳定回归测试。"""

from __future__ import annotations

import crawler4j_contracts


def test_contracts_root_exports_stable_surface():
    expected_exports = {
        "BBox",
        "ClickCaptchaDebugInfo",
        "ClickCaptchaMatchResult",
        "ClickCaptchaOrderedTarget",
        "EnvAction",
        "EnvCandidate",
        "EnvSelectorSpec",
        "HttpClient",
        "ImageInput",
        "PageSpec",
        "Point",
        "SliderCaptchaDebugInfo",
        "SliderCaptchaMatchResult",
        "TaskContext",
        "TaskResult",
        "TaskSpec",
        "TaskSignal",
        "TaskSignalAction",
        "ToolSpec",
        "ToolsCapability",
        "WorkflowSpec",
    }

    assert set(crawler4j_contracts.__all__) == expected_exports
    assert not hasattr(crawler4j_contracts, "DefaultHttpClient")
    assert crawler4j_contracts.TaskContext is not None
    assert crawler4j_contracts.TaskResult is not None
    assert crawler4j_contracts.EnvAction is not None

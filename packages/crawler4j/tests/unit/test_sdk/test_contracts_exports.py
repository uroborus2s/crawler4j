"""crawler4j-contracts 根导出面稳定回归测试。"""

from __future__ import annotations

import crawler4j_contracts


def test_contracts_root_exports_stable_surface():
    expected_exports = {
        "BBox",
        "ClickCaptchaDebugInfo",
        "ClickCaptchaMatchResult",
        "ClickCaptchaOrderedTarget",
        "DatabaseClient",
        "DatabaseExecutor",
        "EnvAction",
        "EnvCandidate",
        "EnvCandidates",
        "CRAWLER4J_META_ATTR",
        "Crawler4jMeta",
        "DataTableIndexSpec",
        "HOST_RESERVED_DATA_FIELDS",
        "HttpClient",
        "ImageInput",
        "InjectSpec",
        "MANAGED_DATASET_RESERVED_DATA_FIELDS",
        "ObjectInjectAnnotation",
        "ObjectParamAnnotation",
        "ParameterOptionSpec",
        "ParameterSpec",
        "Point",
        "SliderCaptchaDebugInfo",
        "SliderCaptchaMatchResult",
        "TaskContext",
        "TaskResult",
        "TaskSignal",
        "TaskSignalAction",
        "ToolSpec",
        "ToolsCapability",
        "component",
        "data_query",
        "data_table",
        "env_cleanup_candidates",
        "env_candidates",
        "interface",
        "object_inject",
        "object_param",
        "page",
        "page_action",
        "workflow",
    }

    assert set(crawler4j_contracts.__all__) == expected_exports
    assert not hasattr(crawler4j_contracts, "DefaultHttpClient")
    assert not hasattr(crawler4j_contracts, "TaskSpec")
    assert not hasattr(crawler4j_contracts, "WorkflowSpec")
    assert not hasattr(crawler4j_contracts, "EnvSelectorSpec")
    assert not hasattr(crawler4j_contracts, "PageSpec")
    assert crawler4j_contracts.DatabaseClient is not None
    assert crawler4j_contracts.DatabaseExecutor is not None
    assert crawler4j_contracts.TaskContext is not None
    assert crawler4j_contracts.TaskResult is not None
    assert crawler4j_contracts.EnvAction is not None

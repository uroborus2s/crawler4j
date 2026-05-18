"""crawler4j-contracts 根导出面稳定回归测试。"""

from __future__ import annotations

import importlib

import pytest

import crawler4j_contracts


def test_contracts_root_exports_stable_surface():
    expected_exports = {
        "BBox",
        "ClickCaptchaDebugInfo",
        "ClickCaptchaMatchResult",
        "ClickCaptchaOrderedTarget",
        "DatabaseClient",
        "DatabaseExecutor",
        "EnvCandidate",
        "EnvCandidates",
        "CRAWLER4J_META_ATTR",
        "Crawler4jMeta",
        "DataTableIndexSpec",
        "HOST_RESERVED_DATA_FIELDS",
        "ActionBindingParamSpec",
        "ActionParamSpec",
        "ActionParamsSchema",
        "ActionValueParamSpec",
        "BindingDataSourceSchema",
        "ButtonActionSchema",
        "ButtonSchema",
        "CardSchema",
        "DataTableColumnSchema",
        "DataTableCrudCreatePayload",
        "DataTableCrudFormSchema",
        "DataTableCrudResult",
        "DataTableCrudSchema",
        "DataTableCrudToolbarSchema",
        "DataTableCrudUpdatePayload",
        "DataTableDataSourceSchema",
        "DataTableFeaturesSchema",
        "DataTablePaginationFeatureSchema",
        "DataTableSchema",
        "DataTableSearchFeatureSchema",
        "DataTableSortFeatureSchema",
        "DataTableSortSpecSchema",
        "HostedDataTableQuery",
        "HostedDataTableQueryResult",
        "HostedDataTableSortSpec",
        "ManagedResourceDataSourceSchema",
        "OpenPageActionSchema",
        "PageComponentSchema",
        "PageLayoutSchema",
        "PageSchema",
        "PageScrollSchema",
        "QueryCallback",
        "QueryHandlerDataSourceSchema",
        "ReloadActionSchema",
        "RowActionSchema",
        "RowsDataSourceSchema",
        "SectionSchema",
        "TextSchema",
        "UiActionSchema",
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
        "TaskOutcome",
        "TaskOutcomeStatus",
        "TaskResult",
        "ToolSpec",
        "ToolsCapability",
        "WorkflowLifecycleInfo",
        "component",
        "data_table",
        "data_view",
        "env_cleanup_candidates",
        "env_candidates",
        "interface",
        "object_inject",
        "object_param",
        "page",
        "page_action",
        "ui_action",
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
    assert crawler4j_contracts.TaskOutcome is not None
    assert crawler4j_contracts.TaskOutcomeStatus is not None
    assert crawler4j_contracts.TaskResult is not None
    assert crawler4j_contracts.WorkflowLifecycleInfo is not None
    assert not hasattr(crawler4j_contracts, "TaskSignal")
    assert not hasattr(crawler4j_contracts, "TaskSignalAction")
    assert not hasattr(crawler4j_contracts, "EnvAction")
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("crawler4j_contracts.signal")

"""core-native-v2 SDK scanner and diagnostic tests."""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import yaml

from crawler4j_sdk import v2_scanner
from crawler4j_sdk.cli import commands


def _write_manifest(module_root: Path, manifest: dict) -> None:
    (module_root / "module.yaml").write_text(
        yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _read_manifest(module_root: Path) -> dict:
    return yaml.safe_load((module_root / "module.yaml").read_text(encoding="utf-8"))


def _init_v2_module(tmp_path: Path, *, module_name: str = "demo_v2") -> Path:
    module_root = tmp_path / module_name
    module_root.mkdir()
    (module_root / "__init__.py").write_text('"""Demo v2 module."""\n', encoding="utf-8")
    for directory_name in ("interfaces", "objects", "workflows", "tasks", "data", "pages", "candidates"):
        directory = module_root / directory_name
        directory.mkdir()
        (directory / "__init__.py").write_text("", encoding="utf-8")
    _write_manifest(
        module_root,
        {
            "name": module_name,
            "runtime_api": "core-native-v2",
            "version": "0.1.0",
            "display_name": "Demo V2",
            "description": "Demo V2 module",
            "author": "crawler4j",
            "upgrade_source": {
                "type": "github_release",
                "repo": "demo/demo_v2",
                "allow_prerelease": False,
            },
        },
    )
    return module_root


def _diagnostic_codes(result: v2_scanner.V2ScanResult) -> list[str]:
    return [diagnostic.code for diagnostic in result.diagnostics]


def test_scan_v2_module_discovers_decorator_metadata(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "objects" / "runtime.py").write_text(
        """
from crawler4j_contracts import component, data_table, data_view, interface, page, page_action, ui_action, workflow


@interface(name="labor", label="Labor")
class Labor:
    pass


@component(name="api_labor", implements="labor")
class ApiLabor:
    pass


@workflow(name="main_workflow", inject=[{"name": "labor", "type": "interface", "target": "labor"}])
class MainWorkflow:
    pass


@page_action(name="open_login_page", label="Open login page")
async def open_login_page(ctx, url: str):
    return {"url": url}


@ui_action(name="create_account_from_ui", label="Create account")
def create_account_from_ui(ctx, payload: dict):
    return {"payload": payload}


@page(
    name="dashboard",
    label="Dashboard",
    icon="chart",
    schema={"type": "Page", "title": "Dashboard", "children": []},
)
def load_dashboard_page(ctx, page_id: str, params=None):
    return {"page_id": page_id}


@data_table(name="accounts", schema=[{"name": "account_id", "type": "string"}])
class Accounts:
    pass


@data_view(
    name="account_overview",
    sources=["accounts"],
    sql="SELECT account_id FROM {{resource:accounts}}",
    schema=[{"name": "account_id", "type": "string"}],
)
def account_overview():
    return []

""",
        encoding="utf-8",
    )
    (module_root / "candidates" / "accounts.py").write_text(
        """
from crawler4j_contracts import env_candidates


@env_candidates(name="ctrip_gold_old_account", label="携程高等级老账号")
def ctrip_gold_old_account(params):
    return None
""",
        encoding="utf-8",
    )
    (module_root / "cleanups").mkdir(exist_ok=True)
    (module_root / "cleanups" / "unused_accounts.py").write_text(
        """
from crawler4j_contracts import env_cleanup_candidates


@env_cleanup_candidates(name="unused_accounts", label="长期未用账号环境")
def unused_accounts(ctx, params=None):
    return []
""",
        encoding="utf-8",
    )
    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    assert result.diagnostics == ()
    assert {(declaration.kind, declaration.name, declaration.symbol) for declaration in result.declarations} == {
        ("interface", "labor", "objects.runtime.Labor"),
        ("component", "api_labor", "objects.runtime.ApiLabor"),
        ("workflow", "main_workflow", "objects.runtime.MainWorkflow"),
        ("page", "dashboard", "objects.runtime.load_dashboard_page"),
        ("page_action", "open_login_page", "objects.runtime.open_login_page"),
        ("ui_action", "create_account_from_ui", "objects.runtime.create_account_from_ui"),
        ("data_table", "accounts", "objects.runtime.Accounts"),
        ("data_view", "account_overview", "objects.runtime.account_overview"),
        ("env_candidates", "ctrip_gold_old_account", "candidates.accounts.ctrip_gold_old_account"),
        ("env_cleanup_candidates", "unused_accounts", "cleanups.unused_accounts.unused_accounts"),
    }
    accounts = next(item for item in result.declarations if item.kind == "data_table")
    assert accounts.meta.storage_mode == "custom_table"


def test_scan_v2_module_rejects_module_flow_control_imports(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "workflows" / "main.py").write_text(
        """
from crawler4j_contracts import EnvAction, TaskResult, TaskSignal, workflow
from crawler4j_contracts.signal import TaskSignalAction


@workflow(name="main_workflow")
class MainWorkflow:
    def run(self, ctx):
        return TaskResult.ok(
            signal=TaskSignal.succeed(message="ok", env_action=EnvAction.DESTROY),
        )
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))
    blocked = [diagnostic for diagnostic in result.diagnostics if diagnostic.code == "V2_HOST_FLOW_CONTROL_IMPORT"]

    assert {diagnostic.message for diagnostic in blocked} == {
        "EnvAction is host-owned and cannot be imported by module runtime code",
        "TaskSignal is host-owned and cannot be imported by module runtime code",
        "TaskSignalAction is host-owned and cannot be imported by module runtime code",
    }


def test_scan_v2_module_rejects_removed_object_lifecycle_methods(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "interfaces" / "labor.py").write_text(
        """
from crawler4j_contracts import interface


@interface(name="labor")
class Labor:
    pass
""",
        encoding="utf-8",
    )
    (module_root / "objects" / "api_labor.py").write_text(
        """
from crawler4j_contracts import component


@component(name="api_labor", implements="labor")
class ApiLabor:
    async def aclose(self):
        pass
""",
        encoding="utf-8",
    )
    (module_root / "workflows" / "main.py").write_text(
        """
from crawler4j_contracts import workflow


@workflow(name="main_workflow")
class MainWorkflow:
    def __init__(self, labor):
        self.labor = labor

    def close(self):
        pass
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))
    diagnostics = [
        diagnostic for diagnostic in result.diagnostics
        if diagnostic.code == "V2_OBJECT_LIFECYCLE_METHOD_UNSUPPORTED"
    ]

    assert {(diagnostic.location, diagnostic.message) for diagnostic in diagnostics} == {
        (
            "objects.api_labor.ApiLabor.aclose",
            "object lifecycle only supports cleanup(ctx, outcome); aclose/close are not called",
        ),
        (
            "workflows.main.MainWorkflow.close",
            "object lifecycle only supports cleanup(ctx, outcome); aclose/close are not called",
        ),
    }


def test_scan_v2_module_validates_object_lifecycle_signatures(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "interfaces" / "labor.py").write_text(
        """
from crawler4j_contracts import interface


@interface(name="labor")
class Labor:
    pass
""",
        encoding="utf-8",
    )
    (module_root / "objects" / "api_labor.py").write_text(
        """
from crawler4j_contracts import component


@component(name="api_labor", implements="labor")
class ApiLabor:
    def setup(self, ctx):
        pass

    def cleanup(self, ctx):
        pass
""",
        encoding="utf-8",
    )
    (module_root / "workflows" / "main.py").write_text(
        """
from crawler4j_contracts import workflow


@workflow(name="main_workflow")
class MainWorkflow:
    def setup(self, ctx, workflow, extra):
        pass

    def cleanup(self, ctx, outcome, extra):
        pass
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))
    diagnostics = [
        diagnostic for diagnostic in result.diagnostics
        if diagnostic.code == "V2_OBJECT_LIFECYCLE_METHOD_SIGNATURE_INVALID"
    ]

    assert {(diagnostic.location, diagnostic.message) for diagnostic in diagnostics} == {
        (
            "objects.api_labor.ApiLabor.setup",
            "setup lifecycle method must accept (self, ctx, workflow)",
        ),
        (
            "objects.api_labor.ApiLabor.cleanup",
            "cleanup lifecycle method must accept (self, ctx, outcome)",
        ),
        (
            "workflows.main.MainWorkflow.setup",
            "setup lifecycle method must accept (self, ctx, workflow)",
        ),
        (
            "workflows.main.MainWorkflow.cleanup",
            "cleanup lifecycle method must accept (self, ctx, outcome)",
        ),
    }


def test_scan_v2_module_merges_class_and_init_annotation_metadata(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "objects" / "annotation_runtime.py").write_text(
        """
from typing import Annotated

from crawler4j_contracts import component, interface, object_inject, object_param, workflow


@interface(name="http")
class Http:
    pass


@interface(name="labor")
class Labor:
    pass


@component(name="http_client", implements="http")
class HttpClient:
    pass


@component(name="api_labor", implements="labor")
class ApiLabor:
    client: Annotated[Http, object_inject(type="object", target="http_client")]
    base_url: Annotated[str, object_param(label="Base URL")]

    def __init__(self, client, base_url, timeout: Annotated[int, object_param(min=1, max=120)] = 30):
        self.client = client
        self.base_url = base_url
        self.timeout = timeout


@workflow(name="main_workflow")
class MainWorkflow:
    def __init__(self, labor: Annotated[Labor, object_inject(type="interface", target="labor")]):
        self.labor = labor
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    assert result.diagnostics == ()
    component_meta = next(item.meta for item in result.declarations if item.name == "api_labor")
    workflow_meta = next(item.meta for item in result.declarations if item.name == "main_workflow")
    assert [item.name for item in component_meta.inject] == ["client"]
    assert [(item.name, item.type, item.required, item.default) for item in component_meta.parameters] == [
        ("base_url", "string", True, None),
        ("timeout", "integer", False, 30),
    ]
    assert [item.name for item in workflow_meta.inject] == ["labor"]


def test_scan_v2_module_infers_extended_object_param_annotation_types(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "objects" / "typed_runtime.py").write_text(
        """
from datetime import date, datetime, time
from pathlib import Path
from typing import Annotated, Literal

from crawler4j_contracts import component, interface, object_param, workflow


@interface(name="labor")
class Labor:
    pass


@component(name="api_labor", implements="labor")
class ApiLabor:
    start_date: Annotated[date, object_param()]
    mode: Annotated[Literal["sync", "async"], object_param(default="sync")]
    tags: Annotated[list[str], object_param(default=["default"])]
    limits: Annotated[dict[str, int], object_param(default={"daily": 10})]
    download_dir: Annotated[Path, object_param()]
    optional_count: Annotated[int | None, object_param()]

    def __init__(
        self,
        deadline: Annotated[datetime, object_param()],
        run_at: Annotated[time, object_param()],
    ):
        self.deadline = deadline
        self.run_at = run_at


@workflow(name="main_workflow")
class MainWorkflow:
    pass
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    assert result.diagnostics == ()
    component_meta = next(item.meta for item in result.declarations if item.name == "api_labor")
    parameters = {item.name: item for item in component_meta.parameters}
    assert parameters["start_date"].type == "date"
    assert parameters["deadline"].type == "datetime"
    assert parameters["run_at"].type == "time"
    assert parameters["download_dir"].type == "path"
    assert parameters["tags"].type == "array"
    assert parameters["tags"].item_schema == {"type": "string"}
    assert parameters["limits"].type == "object"
    assert parameters["limits"].schema == {"additional_type": "integer"}
    assert parameters["optional_count"].type == "integer"
    assert parameters["optional_count"].required is False
    assert parameters["mode"].type == "enum"
    assert [(item.label, item.value) for item in parameters["mode"].options] == [
        ("sync", "sync"),
        ("async", "async"),
    ]


def test_scan_v2_module_reports_duplicate_names_missing_injection_cycles_and_invalid_parameters(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "objects" / "invalid_runtime.py").write_text(
        """
from crawler4j_contracts import component, interface, workflow


@interface(name="labor")
class Labor:
    pass


@component(name="api_labor", implements="labor", parameters=[{"name": "Bad Name", "type": "string"}])
class ApiLabor:
    pass


@component(name="api_labor", implements="labor")
class DuplicateApiLabor:
    pass


@component(name="cycle_a", implements="labor", inject=[{"name": "b", "type": "object", "target": "cycle_b"}])
class CycleA:
    pass


@component(name="cycle_b", implements="labor", inject=[{"name": "a", "type": "object", "target": "cycle_a"}])
class CycleB:
    pass


@workflow(name="main_workflow", inject=[{"name": "missing", "type": "interface", "target": "ghost"}])
class MainWorkflow:
    pass
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    codes = _diagnostic_codes(result)
    assert "V2_DUPLICATE_NAME" in codes
    assert "V2_INJECT_TARGET_MISSING" in codes
    assert "V2_DEPENDENCY_CYCLE" in codes
    assert "V2_INVALID_PARAMETER" in codes
    assert any(
        diagnostic.location == "objects.invalid_runtime.ApiLabor.parameters[Bad Name]"
        for diagnostic in result.diagnostics
    )


def test_scan_v2_module_reports_cycles_through_interface_injections(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "objects" / "interface_cycle.py").write_text(
        """
from crawler4j_contracts import component, interface


@interface(name="a")
class A:
    pass


@interface(name="b")
class B:
    pass


@component(name="a_component", implements="a", inject=[{"name": "b", "type": "interface", "target": "b"}])
class AComponent:
    pass


@component(name="b_component", implements="b", inject=[{"name": "a", "type": "object", "target": "a_component"}])
class BComponent:
    pass
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    assert any(
        diagnostic.code == "V2_DEPENDENCY_CYCLE"
        and "a_component" in diagnostic.message
        and "b_component" in diagnostic.message
        for diagnostic in result.diagnostics
    )


def test_scan_v2_module_reports_interfaces_without_component_implementations(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "interfaces" / "interfaces.py").write_text(
        """
from crawler4j_contracts import interface


@interface(name="labor")
class Labor:
    pass
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    assert any(
        diagnostic.code == "V2_INTERFACE_IMPLEMENTATION_MISSING" and diagnostic.location == "interface.labor"
        for diagnostic in result.diagnostics
    )


def test_scan_v2_module_reports_page_action_classes_and_runtime_sdk_imports(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "tasks" / "actions.py").write_text(
        """
import crawler4j_sdk
from crawler4j_contracts import page_action


@page_action(name="legacy_stateful_action")
class LegacyStatefulAction:
    pass
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    codes = _diagnostic_codes(result)
    assert "V2_PAGE_ACTION_INVALID_TARGET" in codes
    assert "V2_RUNTIME_SDK_IMPORT" in codes


def test_scan_v2_module_accepts_typed_inline_query_handler(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "workflows" / "main.py").write_text(
        """
from crawler4j_contracts import workflow


@workflow(name="main_workflow")
class MainWorkflow:
    pass
""",
        encoding="utf-8",
    )
    (module_root / "pages" / "dashboard.py").write_text(
        """
from crawler4j_contracts import (
    HostedDataTableQuery,
    HostedDataTableQueryResult,
    HostedPageParams,
    TaskContext,
    page,
)


@page(
    name="dashboard",
    label="Dashboard",
    schema={
        "type": "Page",
        "title": "Dashboard",
        "children": [
            {
                "type": "DataTable",
                "table_id": "stats",
                "columns": [{"key": "name", "label": "Name"}],
                "data_source": {"type": "query_handler", "handler": "query_stats_table"},
            }
        ],
    },
)
def load_dashboard_page(context: TaskContext, page_id: str, params: HostedPageParams | None = None) -> dict:
    return {"page_id": page_id, "params": params}


def query_stats_table(
    context: TaskContext,
    table_id: str,
    query: HostedDataTableQuery,
    params: HostedPageParams | None = None,
) -> HostedDataTableQueryResult:
    del context, table_id, query, params
    return {"rows": [], "total": 0, "page": 1, "page_size": 20}
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    assert result.diagnostics == ()


def test_scan_v2_module_accepts_generic_inline_query_result_row_type(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "workflows" / "main.py").write_text(
        """
from crawler4j_contracts import workflow


@workflow(name="main_workflow")
class MainWorkflow:
    pass
""",
        encoding="utf-8",
    )
    (module_root / "pages" / "dashboard.py").write_text(
        """
from typing import TypedDict

from crawler4j_contracts import (
    HostedDataTableQuery,
    HostedDataTableQueryResult,
    HostedPageParams,
    TaskContext,
    page,
)


class AccountRow(TypedDict):
    id: int
    account_id: str
    status: str


@page(
    name="dashboard",
    label="Dashboard",
    schema={
        "type": "Page",
        "title": "Dashboard",
        "children": [
            {
                "type": "DataTable",
                "table_id": "accounts",
                "columns": [
                    {"key": "id", "label": "ID", "visible": False},
                    {"key": "account_id", "label": "Account"},
                    {"key": "status", "label": "Status"},
                ],
                "data_source": {"type": "query_handler", "handler": "query_accounts_table"},
            }
        ],
    },
)
def load_dashboard_page(context: TaskContext, page_id: str, params: HostedPageParams | None = None) -> dict:
    return {"page_id": page_id, "params": params}


def query_accounts_table(
    context: TaskContext,
    table_id: str,
    query: HostedDataTableQuery,
    params: HostedPageParams | None = None,
) -> HostedDataTableQueryResult[AccountRow]:
    del context, table_id, query, params
    return {"rows": [{"id": 1, "account_id": "A001", "status": "active"}], "total": 1}
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    assert result.diagnostics == ()


def test_scan_v2_module_rejects_untyped_inline_query_handler(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "workflows" / "main.py").write_text(
        """
from crawler4j_contracts import workflow


@workflow(name="main_workflow")
class MainWorkflow:
    pass
""",
        encoding="utf-8",
    )
    (module_root / "pages" / "dashboard.py").write_text(
        """
from crawler4j_contracts import TaskContext, page


@page(
    name="dashboard",
    label="Dashboard",
    schema={
        "type": "Page",
        "title": "Dashboard",
        "children": [
            {
                "type": "DataTable",
                "table_id": "stats",
                "columns": [{"key": "name", "label": "Name"}],
                "data_source": {"type": "query_handler", "handler": "query_stats_table"},
            }
        ],
    },
)
def load_dashboard_page(context: TaskContext, page_id: str, params=None) -> dict:
    return {"page_id": page_id}


def query_stats_table(ctx, table, query, params=None):
    return {"rows": []}
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    query_handler_errors = [
        diagnostic for diagnostic in result.diagnostics if diagnostic.code == "V2_PAGE_QUERY_HANDLER_SIGNATURE_INVALID"
    ]
    assert len(query_handler_errors) == 1
    assert query_handler_errors[0].location == "pages.dashboard.query_stats_table"
    assert "HostedDataTableQuery" in query_handler_errors[0].message


def test_scan_v2_module_reports_host_reserved_data_fields(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "data" / "data_contracts.py").write_text(
        """
from crawler4j_contracts import data_table, data_view


@data_table(
    name="accounts",
    schema=[{"name": "account_id", "type": "string"}, {"name": "created_at", "type": "string"}],
    indexes=[{"fields": ["updated_at"]}],
)
class Accounts:
    update_at: str
    pass


@data_view(
    name="recent_accounts",
    sources=["accounts"],
    sql="SELECT account_id, update_at FROM {{resource:accounts}}",
    schema=[{"name": "update_at", "type": "string"}],
)
def recent_accounts():
    return []
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    reserved_errors = [diagnostic for diagnostic in result.diagnostics if diagnostic.code == "V2_RESERVED_DATA_FIELD"]
    assert {diagnostic.location for diagnostic in reserved_errors} == {
        "data.data_contracts.Accounts.schema[created_at]",
        "data.data_contracts.Accounts.indexes[updated_at]",
        "data.data_contracts.Accounts.annotations[update_at]",
        "data.data_contracts.recent_accounts.schema[update_at]",
    }


def test_scan_v2_module_reports_managed_dataset_system_fields(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "data" / "data_contracts.py").write_text(
        """
from crawler4j_contracts import data_table


@data_table(
    name="accounts",
    storage_mode="managed_dataset",
    schema=[
        {"name": "account_id", "type": "string"},
        {"name": "record_index", "type": "integer"},
        {"name": "run_status", "type": "string"},
    ],
    indexes=[{"fields": ["record_status"]}],
)
class Accounts:
    record_key: str
    pass
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    reserved_errors = [diagnostic for diagnostic in result.diagnostics if diagnostic.code == "V2_RESERVED_DATA_FIELD"]
    assert {diagnostic.location for diagnostic in reserved_errors} == {
        "data.data_contracts.Accounts.schema[record_index]",
        "data.data_contracts.Accounts.schema[run_status]",
        "data.data_contracts.Accounts.indexes[record_status]",
        "data.data_contracts.Accounts.annotations[record_key]",
    }


def test_scan_v2_module_allows_custom_table_fields_matching_managed_dataset_system_names(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "data" / "data_contracts.py").write_text(
        """
from crawler4j_contracts import data_table


@data_table(
    name="accounts",
    storage_mode="custom_table",
    schema=[
        {"name": "record_key", "type": "string"},
        {"name": "run_status", "type": "string"},
    ],
    indexes=[{"fields": ["record_status"]}],
)
class Accounts:
    record_status: str
    pass
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    assert [diagnostic for diagnostic in result.diagnostics if diagnostic.code == "V2_RESERVED_DATA_FIELD"] == []


def test_scan_v2_module_warns_for_managed_dataset_derived_display_fields(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "data" / "data_contracts.py").write_text(
        """
from crawler4j_contracts import data_table


@data_table(
    name="accounts",
    storage_mode="managed_dataset",
    schema=[
        {"name": "phone", "type": "string"},
        {"name": "phone_masked", "type": "string"},
        {"name": "status_label", "type": "string"},
        {"name": "updated_at_display", "type": "string"},
    ],
)
class Accounts:
    status_display: str
    pass
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    derived_warnings = [
        diagnostic for diagnostic in result.diagnostics if diagnostic.code == "V2_DERIVED_DATA_FIELD"
    ]
    assert {diagnostic.location for diagnostic in derived_warnings} == {
        "data.data_contracts.Accounts.schema[phone_masked]",
        "data.data_contracts.Accounts.schema[status_label]",
        "data.data_contracts.Accounts.schema[updated_at_display]",
        "data.data_contracts.Accounts.annotations[status_display]",
    }
    assert {diagnostic.severity for diagnostic in derived_warnings} == {"warning"}
    assert not any("V2_DERIVED_DATA_FIELD" in error for error in result.error_messages())


def test_scan_v2_module_rejects_data_view_over_managed_dataset(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "data" / "data_contracts.py").write_text(
        """
from crawler4j_contracts import data_table, data_view


@data_table(
    name="accounts",
    storage_mode="managed_dataset",
    schema=[{"name": "account_id", "type": "string"}],
)
class Accounts:
    pass


@data_view(
    name="account_overview",
    sources=["accounts"],
    sql="SELECT account_id FROM {{resource:accounts}}",
    schema=[{"name": "account_id", "type": "string"}],
)
def account_overview():
    return []
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    assert any(
        diagnostic.code == "V2_VIEW_SOURCE_NOT_RELATION"
        and diagnostic.location == "data.data_contracts.account_overview.sources[accounts]"
        for diagnostic in result.diagnostics
    )


def test_scan_v2_module_ignores_decorators_outside_standard_v2_directories(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "workflows" / "main.py").write_text(
        """
from crawler4j_contracts import workflow


@workflow(name="main_workflow")
class MainWorkflow:
    pass
""",
        encoding="utf-8",
    )
    (module_root / "runtime.py").write_text(
        """
from crawler4j_contracts import interface


@interface(name="legacy_root")
class LegacyRoot:
    pass
""",
        encoding="utf-8",
    )

    result = v2_scanner.scan_v2_module(module_root, _read_manifest(module_root))

    assert result.diagnostics == ()
    assert [(item.kind, item.name) for item in result.declarations] == [("workflow", "main_workflow")]


def test_check_full_uses_v2_scanner_and_rejects_legacy_manifest_sections(
    tmp_path: Path,
    monkeypatch,
    capsys,
):
    module_root = _init_v2_module(tmp_path)
    monkeypatch.chdir(module_root)
    (module_root / "workflows" / "runtime.py").write_text(
        """
from crawler4j_contracts import component, interface, workflow


@interface(name="labor")
class Labor:
    pass


@component(name="api_labor", implements="labor")
class ApiLabor:
    pass


@workflow(name="main_workflow", inject=[{"name": "labor", "type": "interface", "target": "labor"}])
class MainWorkflow:
    pass
""",
        encoding="utf-8",
    )
    manifest = _read_manifest(module_root)
    manifest["workflows"] = [{"name": "main_workflow", "parameters": [{"name": "legacy_param"}]}]
    manifest["data"] = {"resources": []}
    manifest["objects"] = []
    manifest["interfaces"] = []
    manifest["default_workflow"] = "main_workflow"
    _write_manifest(module_root, manifest)

    errors = commands.collect_full_errors(module_root, _read_manifest(module_root))

    assert any("V2_MANIFEST_LEGACY_WORKFLOWS" in error for error in errors)
    assert any("V2_MANIFEST_LEGACY_WORKFLOW_PARAMETERS" in error for error in errors)
    assert any("V2_MANIFEST_LEGACY_DATA" in error for error in errors)
    assert any("V2_MANIFEST_LEGACY_OBJECTS" in error for error in errors)
    assert any("V2_MANIFEST_LEGACY_INTERFACES" in error for error in errors)
    assert any("V2_MANIFEST_LEGACY_DEFAULT_WORKFLOW" in error for error in errors)

    assert commands.cmd_check_full(Namespace()) == 1
    output = capsys.readouterr().out
    assert "full 校验失败" in output
    assert "V2_MANIFEST_LEGACY_WORKFLOW_PARAMETERS" in output


def test_check_full_accepts_valid_v2_module_without_legacy_v1_layout(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "workflows" / "runtime.py").write_text(
        """
from crawler4j_contracts import component, interface, workflow


@interface(name="labor")
class Labor:
    pass


@component(name="api_labor", implements="labor")
class ApiLabor:
    pass


@workflow(name="main_workflow", inject=[{"name": "labor", "type": "interface", "target": "labor"}])
class MainWorkflow:
    pass
""",
        encoding="utf-8",
    )

    assert commands.collect_full_errors(module_root, _read_manifest(module_root)) == []


def test_check_full_v2_removed_api_checks_ignore_tests_and_auxiliary_files(tmp_path: Path):
    module_root = _init_v2_module(tmp_path)
    (module_root / "workflows" / "runtime.py").write_text(
        """
from crawler4j_contracts import component, interface, workflow


@interface(name="labor")
class Labor:
    pass


@component(name="api_labor", implements="labor")
class ApiLabor:
    pass


@workflow(name="main_workflow", inject=[{"name": "labor", "type": "interface", "target": "labor"}])
class MainWorkflow:
    pass
""",
        encoding="utf-8",
    )
    (module_root / "tests").mkdir()
    (module_root / "tests" / "test_legacy_examples.py").write_text(
        """
def test_old_examples(ctx):
    ctx.captured_data.append({"id": 1})
    ctx.tools.call("db.insert", {})
""",
        encoding="utf-8",
    )
    (module_root / "runtime.py").write_text(
        """
def old_helper(ctx):
    return ctx.captured_data
""",
        encoding="utf-8",
    )

    assert commands.collect_full_errors(module_root, _read_manifest(module_root)) == []

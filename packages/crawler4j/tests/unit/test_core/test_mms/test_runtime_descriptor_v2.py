from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent

import pytest

from crawler4j_contracts import Crawler4jMeta, InjectSpec
from src.core.mms.models import ModuleManifest, UpgradeSourceInfo
from src.core.mms.module_loader import purge_module_namespace
from src.core.mms.runtime_descriptor import ModuleRuntimeDescriptorV2, load_runtime_descriptor_v2


def _manifest(module_name: str) -> ModuleManifest:
    return ModuleManifest(
        name=module_name,
        runtime_api="core-native-v2",
        upgrade_source=UpgradeSourceInfo(repo=f"example/{module_name}"),
        data={
            "resources": [{"name": "legacy_manifest_table"}],
            "views": [{"name": "legacy_manifest_view"}],
            "seeds": [],
        },
    )


def _write_v2_module(base_dir: Path, module_name: str, files: dict[str, str]) -> Path:
    module_dir = base_dir / module_name
    for package_dir in (
        module_dir,
        module_dir / "interfaces",
        module_dir / "objects",
        module_dir / "workflows",
        module_dir / "tasks",
        module_dir / "data",
        module_dir / "pages",
        module_dir / "candidates",
        module_dir / "cleanups",
    ):
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

    for relative_path, content in files.items():
        file_path = module_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(dedent(content).strip() + "\n", encoding="utf-8")
    return module_dir


def test_load_runtime_descriptor_v2_scans_decorators_without_instantiating(tmp_path):
    module_name = "decorator_module"
    module_dir = _write_v2_module(
        tmp_path,
        module_name,
        {
            "interfaces/labor.py": """
                from crawler4j_contracts import interface

                @interface(name="labor", label="Labor")
                class Labor:
                    pass
            """,
            "interfaces/orchestrator.py": """
                from crawler4j_contracts import interface

                @interface(name="orchestrator", label="Orchestrator")
                class Orchestrator:
                    pass
            """,
            "objects/api_labor.py": """
                from crawler4j_contracts import component

                created = 0

                @component(name="api_labor", implements="labor")
                class ApiLabor:
                    def __init__(self):
                        global created
                        created += 1
            """,
            "objects/quiz_orchestrator.py": """
                from crawler4j_contracts import component

                created = 0

                @component(
                    name="quiz_orchestrator",
                    implements="orchestrator",
                    inject=[{"name": "labor", "type": "interface", "target": "labor"}],
                )
                class QuizOrchestrator:
                    def __init__(self, labor):
                        global created
                        created += 1
                        self.labor = labor
            """,
            "workflows/quiz.py": """
                from crawler4j_contracts import workflow

                WORKFLOW = object()
                created = 0

                @workflow(
                    name="quiz_workflow",
                    label="Quiz",
                    inject=[{"name": "orchestrator", "type": "interface", "target": "orchestrator"}],
                )
                class QuizWorkflow:
                    def __init__(self, orchestrator):
                        global created
                        created += 1
                        self.orchestrator = orchestrator
            """,
            "tasks/open_login.py": """
                from crawler4j_contracts import page_action

                TASK = object()
                PAGE = object()

                @page_action(name="open_login_page", label="Open login")
                async def open_login_page(ctx, url: str):
                    return {"url": url}
            """,
            "pages/actions.py": """
                from crawler4j_contracts import ui_action

                @ui_action(name="create_account_from_ui", label="Create account")
                def create_account_from_ui(ctx, payload: dict):
                    return {"payload": payload}
            """,
            "pages/dashboard.py": """
                from crawler4j_contracts import page

                @page(
                    name="dashboard",
                    label="Dashboard",
                    icon="chart",
                    schema={"type": "Page", "title": "Dashboard", "children": []},
                )
                def load_dashboard_page(ctx, page_id: str, params=None):
                    return {"page_id": page_id}
            """,
            "data/accounts.py": """
                from crawler4j_contracts import data_table, data_view

                @data_table(
                    name="accounts",
                    schema=[{"name": "account_id", "type": "string", "required": True}],
                    indexes=[{"fields": ["account_id"], "unique": True}],
                )
                class AccountsTable:
                    pass

                @data_view(
                    name="account_overview",
                    sources=["accounts"],
                    sql="SELECT account_id FROM {{resource:accounts}}",
                    schema=[{"name": "account_id", "type": "string"}],
                )
                def account_overview():
                    raise AssertionError("data view function must not be called during descriptor scan")
            """,
            "cleanups/unused_accounts.py": """
                from crawler4j_contracts import env_cleanup_candidates

                @env_cleanup_candidates(name="unused_accounts", label="长期未用账号环境")
                def unused_accounts(ctx, params=None):
                    return []
            """,
        },
    )

    try:
        descriptor = load_runtime_descriptor_v2(module_name, module_dir, _manifest(module_name))

        assert isinstance(descriptor, ModuleRuntimeDescriptorV2)
        assert descriptor.interfaces["labor"].meta == Crawler4jMeta(kind="interface", name="labor", label="Labor")
        assert descriptor.components["quiz_orchestrator"].meta.inject == (
            InjectSpec(name="labor", type="interface", target="labor"),
        )
        assert descriptor.workflows["quiz_workflow"].target.__name__ == "QuizWorkflow"
        assert descriptor.pages["dashboard"].spec.label == "Dashboard"
        assert descriptor.pages["dashboard"].spec.menu is True
        assert descriptor.page_actions["open_login_page"].target.__name__ == "open_login_page"
        assert descriptor.ui_actions["create_account_from_ui"].target.__name__ == "create_account_from_ui"
        assert descriptor.data_tables["accounts"].meta.kind == "data_table"
        assert descriptor.data_views["account_overview"].meta.sources == ("accounts",)
        assert descriptor.env_cleanup_candidates["unused_accounts"].meta.kind == "env_cleanup_candidates"
        assert descriptor.implementations == {
            "labor": ("api_labor",),
            "orchestrator": ("quiz_orchestrator",),
        }
        assert "legacy_task" not in descriptor.page_actions
        assert "legacy_workflow" not in descriptor.workflows
        assert "legacy_manifest_table" not in descriptor.data_tables
        assert "legacy_manifest_view" not in descriptor.data_views
        assert sys.modules[f"{module_name}.objects.api_labor"].created == 0
        assert sys.modules[f"{module_name}.objects.quiz_orchestrator"].created == 0
        assert sys.modules[f"{module_name}.workflows.quiz"].created == 0
    finally:
        purge_module_namespace(module_name)


def test_load_runtime_descriptor_v2_rejects_duplicate_names(tmp_path):
    module_name = "duplicate_module"
    module_dir = _write_v2_module(
        tmp_path,
        module_name,
        {
            "interfaces/labor.py": """
                from crawler4j_contracts import interface

                @interface(name="labor")
                class Labor:
                    pass
            """,
            "objects/a.py": """
                from crawler4j_contracts import component

                @component(name="api_labor", implements="labor")
                class ApiLaborA:
                    pass
            """,
            "objects/b.py": """
                from crawler4j_contracts import component

                @component(name="api_labor", implements="labor")
                class ApiLaborB:
                    pass
            """,
        },
    )

    try:
        with pytest.raises(RuntimeError, match="重复.*api_labor"):
            load_runtime_descriptor_v2(module_name, module_dir, _manifest(module_name))
    finally:
        purge_module_namespace(module_name)


def test_load_runtime_descriptor_v2_requires_explicit_v2_runtime_api(tmp_path):
    module_name = "missing_runtime_api_module"
    module_dir = _write_v2_module(tmp_path, module_name, {})
    manifest = _manifest(module_name)
    manifest.runtime_api = ""

    try:
        with pytest.raises(RuntimeError, match="runtime_api 必须是 core-native-v2"):
            load_runtime_descriptor_v2(module_name, module_dir, manifest)
    finally:
        purge_module_namespace(module_name)


def test_load_runtime_descriptor_v2_rejects_missing_inject_target(tmp_path):
    module_name = "missing_inject_module"
    module_dir = _write_v2_module(
        tmp_path,
        module_name,
        {
            "workflows/quiz.py": """
                from crawler4j_contracts import workflow

                @workflow(name="quiz_workflow", inject=[{"name": "labor", "type": "interface", "target": "labor"}])
                class QuizWorkflow:
                    pass
            """,
        },
    )

    try:
        with pytest.raises(RuntimeError, match="注入目标不存在.*quiz_workflow.*labor"):
            load_runtime_descriptor_v2(module_name, module_dir, _manifest(module_name))
    finally:
        purge_module_namespace(module_name)


def test_load_runtime_descriptor_v2_rejects_dependency_cycles(tmp_path):
    module_name = "cycle_module"
    module_dir = _write_v2_module(
        tmp_path,
        module_name,
        {
            "interfaces/a.py": """
                from crawler4j_contracts import interface

                @interface(name="a")
                class A:
                    pass
            """,
            "interfaces/b.py": """
                from crawler4j_contracts import interface

                @interface(name="b")
                class B:
                    pass
            """,
            "objects/a_component.py": """
                from crawler4j_contracts import component

                @component(name="a_component", implements="a", inject=[{"name": "b", "type": "object", "target": "b_component"}])
                class AComponent:
                    pass
            """,
            "objects/b_component.py": """
                from crawler4j_contracts import component

                @component(name="b_component", implements="b", inject=[{"name": "a", "type": "object", "target": "a_component"}])
                class BComponent:
                    pass
            """,
        },
    )

    try:
        with pytest.raises(RuntimeError, match="循环依赖.*a_component.*b_component.*a_component"):
            load_runtime_descriptor_v2(module_name, module_dir, _manifest(module_name))
    finally:
        purge_module_namespace(module_name)

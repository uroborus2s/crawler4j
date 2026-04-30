from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from src.core.mms.models import ModuleManifest, UpgradeSourceInfo
from src.core.mms.module_loader import purge_module_namespace
from src.core.mms.object_container_v2 import ObjectContainerV2
from src.core.mms.runtime_descriptor import load_runtime_descriptor_v2


def _manifest(module_name: str) -> ModuleManifest:
    return ModuleManifest(
        name=module_name,
        runtime_api="core-native-v2",
        upgrade_source=UpgradeSourceInfo(repo=f"example/{module_name}"),
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
    ):
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

    for relative_path, content in files.items():
        file_path = module_dir / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(dedent(content).strip() + "\n", encoding="utf-8")
    return module_dir


def _write_quiz_module(tmp_path: Path, module_name: str, *, constructor_body: str = "") -> Path:
    return _write_v2_module(
        tmp_path,
        module_name,
        {
            "interfaces/labor.py": """
                from crawler4j_contracts import interface

                @interface(name="labor")
                class Labor:
                    pass
            """,
            "interfaces/orchestrator.py": """
                from crawler4j_contracts import interface

                @interface(name="orchestrator")
                class Orchestrator:
                    pass
            """,
            "objects/api_labor.py": f"""
                from crawler4j_contracts import component

                @component(
                    name="api_labor",
                    implements="labor",
                    parameters=[
                        {{"name": "base_url", "type": "string", "required": True}},
                        {{"name": "timeout", "type": "integer", "default": 30}},
                    ],
                )
                class ApiLabor:
                    def __init__(self, base_url, timeout):
                        {constructor_body or "pass"}
                        self.base_url = base_url
                        self.timeout = timeout
            """,
            "objects/quiz_orchestrator.py": """
                from crawler4j_contracts import component

                @component(
                    name="quiz_orchestrator",
                    implements="orchestrator",
                    inject=[{"name": "labor", "type": "interface", "target": "labor"}],
                )
                class QuizOrchestrator:
                    def __init__(self, labor):
                        self.labor = labor
            """,
            "workflows/quiz.py": """
                from crawler4j_contracts import workflow

                @workflow(
                    name="quiz_workflow",
                    inject=[{"name": "orchestrator", "type": "interface", "target": "orchestrator"}],
                )
                class QuizWorkflow:
                    def __init__(self, orchestrator, **kwargs):
                        self.orchestrator = orchestrator
                        self.kwargs = kwargs
            """,
        },
    )


def test_object_container_builds_workflow_with_selected_components_and_params(tmp_path: Path):
    module_name = "container_build_module"
    module_dir = _write_quiz_module(tmp_path, module_name)

    try:
        descriptor = load_runtime_descriptor_v2(module_name, module_dir, _manifest(module_name))
        container = ObjectContainerV2(
            descriptor,
            "quiz_workflow",
            object_bindings={
                "orchestrator": "quiz_orchestrator",
                "orchestrator.labor": "api_labor",
            },
            object_params={
                "api_labor": {
                    "base_url": "https://labor.example.com",
                    "timeout": 10,
                },
                "quiz_workflow": {"must_not_leak": True},
            },
        )

        workflow = container.build_workflow()

        assert workflow.orchestrator.labor.base_url == "https://labor.example.com"
        assert workflow.orchestrator.labor.timeout == 10
        assert workflow.kwargs == {}
    finally:
        purge_module_namespace(module_name)


def test_object_container_shares_instances_in_one_graph_and_isolates_graphs(tmp_path: Path):
    module_name = "container_scope_module"
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
            "interfaces/orchestrator.py": """
                from crawler4j_contracts import interface

                @interface(name="orchestrator")
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
                        self.sequence = created
            """,
            "objects/quiz_orchestrator.py": """
                from crawler4j_contracts import component

                @component(
                    name="quiz_orchestrator",
                    implements="orchestrator",
                    inject=[
                        {"name": "primary_labor", "type": "interface", "target": "labor"},
                        {"name": "backup_labor", "type": "interface", "target": "labor"},
                    ],
                )
                class QuizOrchestrator:
                    def __init__(self, primary_labor, backup_labor):
                        self.primary_labor = primary_labor
                        self.backup_labor = backup_labor
            """,
            "workflows/quiz.py": """
                from crawler4j_contracts import workflow

                @workflow(
                    name="quiz_workflow",
                    inject=[{"name": "orchestrator", "type": "interface", "target": "orchestrator"}],
                )
                class QuizWorkflow:
                    def __init__(self, orchestrator):
                        self.orchestrator = orchestrator
            """,
        },
    )

    try:
        descriptor = load_runtime_descriptor_v2(module_name, module_dir, _manifest(module_name))
        bindings = {
            "orchestrator": "quiz_orchestrator",
            "orchestrator.primary_labor": "api_labor",
            "orchestrator.backup_labor": "api_labor",
        }

        first = ObjectContainerV2(descriptor, "quiz_workflow", object_bindings=bindings).build_workflow()
        second = ObjectContainerV2(descriptor, "quiz_workflow", object_bindings=bindings).build_workflow()

        assert first.orchestrator.primary_labor is first.orchestrator.backup_labor
        assert first.orchestrator.primary_labor is not second.orchestrator.primary_labor
        assert first.orchestrator.primary_labor.sequence == 1
        assert second.orchestrator.primary_labor.sequence == 2
    finally:
        purge_module_namespace(module_name)


def test_object_container_requires_explicit_interface_selection(tmp_path: Path):
    module_name = "container_missing_binding_module"
    module_dir = _write_quiz_module(tmp_path, module_name)

    try:
        descriptor = load_runtime_descriptor_v2(module_name, module_dir, _manifest(module_name))
        container = ObjectContainerV2(
            descriptor,
            "quiz_workflow",
            object_bindings={"orchestrator": "quiz_orchestrator"},
            object_params={"api_labor": {"base_url": "https://labor.example.com"}},
        )

        with pytest.raises(RuntimeError, match="缺少实现选择.*orchestrator\\.labor.*labor"):
            container.build_workflow()
    finally:
        purge_module_namespace(module_name)


def test_object_container_reports_missing_required_component_parameter(tmp_path: Path):
    module_name = "container_missing_param_module"
    module_dir = _write_quiz_module(tmp_path, module_name)

    try:
        descriptor = load_runtime_descriptor_v2(module_name, module_dir, _manifest(module_name))
        container = ObjectContainerV2(
            descriptor,
            "quiz_workflow",
            object_bindings={
                "orchestrator": "quiz_orchestrator",
                "orchestrator.labor": "api_labor",
            },
        )

        with pytest.raises(RuntimeError, match="api_labor.*base_url"):
            container.build_workflow()
    finally:
        purge_module_namespace(module_name)


def test_object_container_wraps_component_constructor_failure(tmp_path: Path):
    module_name = "container_constructor_failure_module"
    module_dir = _write_quiz_module(
        tmp_path,
        module_name,
        constructor_body='raise ValueError("bad token")',
    )

    try:
        descriptor = load_runtime_descriptor_v2(module_name, module_dir, _manifest(module_name))
        container = ObjectContainerV2(
            descriptor,
            "quiz_workflow",
            object_bindings={
                "orchestrator": "quiz_orchestrator",
                "orchestrator.labor": "api_labor",
            },
            object_params={"api_labor": {"base_url": "https://labor.example.com"}},
        )

        with pytest.raises(RuntimeError, match="api_labor 构造失败.*ValueError.*bad token"):
            container.build_workflow()
    finally:
        purge_module_namespace(module_name)


def test_object_container_rejects_component_selection_for_wrong_interface(tmp_path: Path):
    module_name = "container_invalid_selection_module"
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
            "interfaces/orchestrator.py": """
                from crawler4j_contracts import interface

                @interface(name="orchestrator")
                class Orchestrator:
                    pass
            """,
            "interfaces/storage.py": """
                from crawler4j_contracts import interface

                @interface(name="storage")
                class Storage:
                    pass
            """,
            "objects/storage_client.py": """
                from crawler4j_contracts import component

                @component(name="storage_client", implements="storage")
                class StorageClient:
                    pass
            """,
            "objects/quiz_orchestrator.py": """
                from crawler4j_contracts import component

                @component(name="quiz_orchestrator", implements="orchestrator")
                class QuizOrchestrator:
                    pass
            """,
            "workflows/quiz.py": """
                from crawler4j_contracts import workflow

                @workflow(
                    name="quiz_workflow",
                    inject=[{"name": "labor", "type": "interface", "target": "labor"}],
                )
                class QuizWorkflow:
                    def __init__(self, labor):
                        self.labor = labor
            """,
        },
    )

    try:
        descriptor = load_runtime_descriptor_v2(module_name, module_dir, _manifest(module_name))
        container = ObjectContainerV2(
            descriptor,
            "quiz_workflow",
            object_bindings={"labor": "storage_client"},
        )

        with pytest.raises(RuntimeError, match="storage_client.*不实现 interface labor"):
            container.build_workflow()
    finally:
        purge_module_namespace(module_name)

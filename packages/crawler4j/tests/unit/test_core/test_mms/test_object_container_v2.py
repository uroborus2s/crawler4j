from __future__ import annotations

from datetime import date, datetime, time
from pathlib import Path
from textwrap import dedent

import pytest

from crawler4j_contracts import Crawler4jMeta, InjectSpec, TaskContext, TaskOutcome, WorkflowLifecycleInfo
from src.core.mms.models import ModuleManifest, UpgradeSourceInfo
from src.core.mms.module_loader import purge_module_namespace
from src.core.mms.object_container_v2 import ObjectContainerV2
from src.core.mms.runtime_descriptor import ModuleRuntimeDescriptorV2, V2RuntimeEntry, load_runtime_descriptor_v2


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
                        {{"name": "timeout", "type": "integer", "default": 30, "min": 1, "max": 120}},
                        {{
                            "name": "mode",
                            "type": "enum",
                            "default": "sync",
                            "options": [
                                {{"label": "Sync", "value": "sync"}},
                                {{"label": "Async", "value": "async"}},
                            ],
                        }},
                        {{"name": "enabled", "type": "boolean", "default": True}},
                    ],
                )
                class ApiLabor:
                    def __init__(self, base_url, timeout, mode, enabled):
                        {constructor_body or "pass"}
                        self.base_url = base_url
                        self.timeout = timeout
                        self.mode = mode
                        self.enabled = enabled
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
            },
        )

        workflow = container.build_workflow()

        assert workflow.orchestrator.labor.base_url == "https://labor.example.com"
        assert workflow.orchestrator.labor.timeout == 10
        assert workflow.orchestrator.labor.mode == "sync"
        assert workflow.orchestrator.labor.enabled is True
        assert workflow.kwargs == {}
    finally:
        purge_module_namespace(module_name)


@pytest.mark.asyncio
async def test_object_container_runs_setup_and_cleanup_in_lifecycle_order():
    events: list[str] = []

    class Labor:
        def setup(self, ctx, workflow):
            events.append(f"labor.setup:{ctx.task_name}:{workflow.workflow_name}")

        def close(self):
            events.append("labor.close should not run")

        def cleanup(self, ctx, outcome):
            events.append(f"labor.cleanup:{ctx.task_name}:{outcome.status}")

    class Orchestrator:
        def __init__(self, labor):
            self.labor = labor

        async def aclose(self):
            events.append("orchestrator.aclose should not run")

        async def setup(self, ctx, workflow):
            events.append(f"orchestrator.setup:{ctx.task_name}:{workflow.workflow_label}")

        async def cleanup(self, ctx, outcome):
            events.append(f"orchestrator.cleanup:{ctx.task_name}:{outcome.status}")

    class QuizWorkflow:
        def __init__(self, orchestrator):
            self.orchestrator = orchestrator

        def setup(self, ctx, workflow):
            events.append(f"workflow.setup:{ctx.task_name}:{workflow.workflow_symbol}")

        def cleanup(self, ctx, outcome):
            events.append(f"workflow.cleanup:{ctx.task_name}:{outcome.status}")

    descriptor = ModuleRuntimeDescriptorV2(
        interfaces={
            "labor": V2RuntimeEntry(
                meta=Crawler4jMeta(kind="interface", name="labor"),
                target=object,
                module_name="cleanup_module.interfaces.labor",
                attr_name="Labor",
                owner="interfaces/labor.py",
            ),
            "orchestrator": V2RuntimeEntry(
                meta=Crawler4jMeta(kind="interface", name="orchestrator"),
                target=object,
                module_name="cleanup_module.interfaces.orchestrator",
                attr_name="Orchestrator",
                owner="interfaces/orchestrator.py",
            ),
        },
        components={
            "api_labor": V2RuntimeEntry(
                meta=Crawler4jMeta(kind="component", name="api_labor", implements="labor"),
                target=Labor,
                module_name="cleanup_module.objects.api_labor",
                attr_name="Labor",
                owner="objects/api_labor.py",
            ),
            "quiz_orchestrator": V2RuntimeEntry(
                meta=Crawler4jMeta(
                    kind="component",
                    name="quiz_orchestrator",
                    implements="orchestrator",
                    inject=(InjectSpec(name="labor", type="interface", target="labor"),),
                ),
                target=Orchestrator,
                module_name="cleanup_module.objects.quiz_orchestrator",
                attr_name="Orchestrator",
                owner="objects/quiz_orchestrator.py",
            ),
        },
        workflows={
            "quiz_workflow": V2RuntimeEntry(
                meta=Crawler4jMeta(
                    kind="workflow",
                    name="quiz_workflow",
                    label="Quiz workflow",
                    description="Run quiz workflow",
                    inject=(InjectSpec(name="orchestrator", type="interface", target="orchestrator"),),
                ),
                target=QuizWorkflow,
                module_name="cleanup_module.workflows.quiz",
                attr_name="QuizWorkflow",
                owner="workflows/quiz.py",
            ),
        },
        implementations={
            "labor": ("api_labor",),
            "orchestrator": ("quiz_orchestrator",),
        },
    )
    container = ObjectContainerV2(descriptor, "quiz_workflow")
    context = TaskContext(env_id=1, task_name="cleanup_module")
    workflow = WorkflowLifecycleInfo(
        module_name="cleanup_module",
        workflow_name="quiz_workflow",
        workflow_label="Quiz workflow",
        workflow_description="Run quiz workflow",
        workflow_module_name="cleanup_module.workflows.quiz",
        workflow_symbol="QuizWorkflow",
    )
    outcome = TaskOutcome(status="succeeded", workflow=workflow)

    container.build_workflow()
    await container.setup(context, workflow)
    await container.setup(context, workflow)
    await container.cleanup(context, outcome)
    await container.cleanup(context, outcome)

    assert events == [
        "labor.setup:cleanup_module:quiz_workflow",
        "orchestrator.setup:cleanup_module:Quiz workflow",
        "workflow.setup:cleanup_module:QuizWorkflow",
        "orchestrator.cleanup:cleanup_module:succeeded",
        "labor.cleanup:cleanup_module:succeeded",
        "workflow.cleanup:cleanup_module:succeeded",
    ]


@pytest.mark.asyncio
async def test_object_container_continues_cleanup_when_one_cleanup_fails():
    events: list[str] = []

    class Labor:
        def cleanup(self, ctx, outcome):
            events.append(f"labor.cleanup:{outcome.status}")
            raise RuntimeError("cleanup failed")

    class Workflow:
        def __init__(self, labor):
            self.labor = labor

        def cleanup(self, ctx, outcome):
            events.append(f"workflow.cleanup:{outcome.status}")

    descriptor = ModuleRuntimeDescriptorV2(
        interfaces={
            "labor": V2RuntimeEntry(
                meta=Crawler4jMeta(kind="interface", name="labor"),
                target=object,
                module_name="cleanup_error_module.interfaces.labor",
                attr_name="Labor",
                owner="interfaces/labor.py",
            ),
        },
        components={
            "api_labor": V2RuntimeEntry(
                meta=Crawler4jMeta(kind="component", name="api_labor", implements="labor"),
                target=Labor,
                module_name="cleanup_error_module.objects.api_labor",
                attr_name="Labor",
                owner="objects/api_labor.py",
            ),
        },
        workflows={
            "default": V2RuntimeEntry(
                meta=Crawler4jMeta(
                    kind="workflow",
                    name="default",
                    inject=(InjectSpec(name="labor", type="interface", target="labor"),),
                ),
                target=Workflow,
                module_name="cleanup_error_module.workflows.default",
                attr_name="Workflow",
                owner="workflows/default.py",
            ),
        },
        implementations={"labor": ("api_labor",)},
    )
    container = ObjectContainerV2(descriptor, "default")
    context = TaskContext(env_id=1, task_name="cleanup_error_module")
    outcome = TaskOutcome(status="failed", error="boom", error_type="RuntimeError")

    container.build_workflow()
    await container.cleanup(context, outcome)

    assert events == ["labor.cleanup:failed", "workflow.cleanup:failed"]


def test_object_container_builds_workflow_from_annotation_declared_metadata(tmp_path: Path):
    module_name = "container_annotation_module"
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
                from typing import Annotated

                from crawler4j_contracts import component, object_param

                @component(name="api_labor", implements="labor")
                class ApiLabor:
                    base_url: Annotated[str, object_param(label="Base URL")]

                    def __init__(
                        self,
                        base_url,
                        timeout: Annotated[int, object_param(min=1, max=120)] = 30,
                    ):
                        self.base_url = base_url
                        self.timeout = timeout
            """,
            "objects/quiz_orchestrator.py": """
                from typing import Annotated

                from crawler4j_contracts import component, object_inject

                from ..interfaces.labor import Labor

                @component(name="quiz_orchestrator", implements="orchestrator")
                class QuizOrchestrator:
                    labor: Annotated[Labor, object_inject(type="interface", target="labor")]

                    def __init__(self, labor):
                        self.labor = labor
            """,
            "workflows/quiz.py": """
                from typing import Annotated

                from crawler4j_contracts import object_inject, workflow

                from ..interfaces.orchestrator import Orchestrator

                @workflow(name="quiz_workflow")
                class QuizWorkflow:
                    def __init__(
                        self,
                        orchestrator: Annotated[
                            Orchestrator,
                            object_inject(type="interface", target="orchestrator"),
                        ],
                    ):
                        self.orchestrator = orchestrator
            """,
        },
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
            object_params={
                "api_labor": {
                    "base_url": "https://labor.example.com",
                },
            },
        )

        workflow = container.build_workflow()

        assert workflow.orchestrator.labor.base_url == "https://labor.example.com"
        assert workflow.orchestrator.labor.timeout == 30
    finally:
        purge_module_namespace(module_name)


def test_object_container_validates_and_coerces_extended_parameter_types(tmp_path: Path):
    module_name = "container_typed_param_module"
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
            "objects/typed_labor.py": """
                from crawler4j_contracts import component

                @component(
                    name="typed_labor",
                    implements="labor",
                    parameters=[
                        {"name": "start_date", "type": "date", "required": True},
                        {"name": "deadline", "type": "datetime", "required": True},
                        {"name": "run_at", "type": "time", "required": True},
                        {"name": "download_dir", "type": "path", "required": True},
                        {"name": "tags", "type": "array", "item_schema": {"type": "string"}, "default": ["core"]},
                        {
                            "name": "limits",
                            "type": "object",
                            "schema": {
                                "fields": [
                                    {"name": "daily", "type": "integer", "required": True},
                                    {"name": "burst", "type": "number"},
                                ]
                            },
                            "required": True,
                        },
                        {"name": "endpoint", "type": "url", "required": True},
                        {"name": "token", "type": "secret", "required": True},
                        {"name": "payload", "type": "json", "required": True},
                    ],
                )
                class TypedLabor:
                    def __init__(
                        self,
                        start_date,
                        deadline,
                        run_at,
                        download_dir,
                        tags,
                        limits,
                        endpoint,
                        token,
                        payload,
                    ):
                        self.start_date = start_date
                        self.deadline = deadline
                        self.run_at = run_at
                        self.download_dir = download_dir
                        self.tags = tags
                        self.limits = limits
                        self.endpoint = endpoint
                        self.token = token
                        self.payload = payload
            """,
            "workflows/quiz.py": """
                from crawler4j_contracts import workflow

                @workflow(name="quiz_workflow", inject=[{"name": "labor", "type": "interface", "target": "labor"}])
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
            object_params={
                "typed_labor": {
                    "start_date": "2026-05-01",
                    "deadline": "2026-05-01T12:30:00",
                    "run_at": "08:45:00",
                    "download_dir": "/tmp/downloads",
                    "tags": ("alpha", "beta"),
                    "limits": {"daily": 10, "burst": 2.5},
                    "endpoint": "https://api.example.com/v1",
                    "token": "secret-token",
                    "payload": {"enabled": True, "ids": [1, "2"]},
                }
            },
        )

        workflow = container.build_workflow()

        assert workflow.labor.start_date == date(2026, 5, 1)
        assert workflow.labor.deadline == datetime(2026, 5, 1, 12, 30)
        assert workflow.labor.run_at == time(8, 45)
        assert workflow.labor.download_dir == Path("/tmp/downloads")
        assert workflow.labor.tags == ["alpha", "beta"]
        assert workflow.labor.limits == {"daily": 10, "burst": 2.5}
        assert workflow.labor.endpoint == "https://api.example.com/v1"
        assert workflow.labor.token == "secret-token"
        assert workflow.labor.payload == {"enabled": True, "ids": [1, "2"]}
    finally:
        purge_module_namespace(module_name)


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"start_date": "2026-13-01"}, "start_date 必须是 ISO date"),
        ({"endpoint": "api.example.com"}, "endpoint 必须是 URL"),
        ({"tags": [1]}, r"tags\[0\] 必须是字符串"),
        ({"limits": {"burst": 2.5}}, "limits.daily 不能为空"),
        ({"payload": {1: "bad"}}, "payload 必须是 JSON-like 值"),
    ],
)
def test_object_container_rejects_invalid_extended_parameter_values(
    tmp_path: Path,
    params: dict[str, object],
    message: str,
):
    module_name = "container_invalid_typed_param_module"
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
            "objects/typed_labor.py": """
                from crawler4j_contracts import component

                @component(
                    name="typed_labor",
                    implements="labor",
                    parameters=[
                        {"name": "start_date", "type": "date", "required": True},
                        {"name": "endpoint", "type": "url", "required": True},
                        {"name": "tags", "type": "array", "item_schema": {"type": "string"}, "required": True},
                        {
                            "name": "limits",
                            "type": "object",
                            "schema": {"fields": [{"name": "daily", "type": "integer", "required": True}]},
                            "required": True,
                        },
                        {"name": "payload", "type": "json", "required": True},
                    ],
                )
                class TypedLabor:
                    def __init__(self, start_date, endpoint, tags, limits, payload):
                        self.start_date = start_date
                        self.endpoint = endpoint
                        self.tags = tags
                        self.limits = limits
                        self.payload = payload
            """,
            "workflows/quiz.py": """
                from crawler4j_contracts import workflow

                @workflow(name="quiz_workflow", inject=[{"name": "labor", "type": "interface", "target": "labor"}])
                class QuizWorkflow:
                    def __init__(self, labor):
                        self.labor = labor
            """,
        },
    )
    valid_params = {
        "start_date": "2026-05-01",
        "endpoint": "https://api.example.com/v1",
        "tags": ["alpha"],
        "limits": {"daily": 10},
        "payload": {"enabled": True},
    }
    valid_params.update(params)

    try:
        descriptor = load_runtime_descriptor_v2(module_name, module_dir, _manifest(module_name))
        container = ObjectContainerV2(
            descriptor,
            "quiz_workflow",
            object_params={"typed_labor": valid_params},
        )

        with pytest.raises(RuntimeError, match=message):
            container.build_workflow()
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
    (module_dir / "objects" / "browser_labor.py").write_text(
        dedent(
            """
            from crawler4j_contracts import component

            @component(name="browser_labor", implements="labor")
            class BrowserLabor:
                pass
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )

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


def test_object_container_auto_binds_single_interface_implementation(tmp_path: Path):
    module_name = "container_single_impl_module"
    module_dir = _write_quiz_module(tmp_path, module_name)

    try:
        descriptor = load_runtime_descriptor_v2(module_name, module_dir, _manifest(module_name))
        container = ObjectContainerV2(
            descriptor,
            "quiz_workflow",
            object_params={"api_labor": {"base_url": "https://labor.example.com"}},
        )

        workflow = container.build_workflow()

        assert workflow.orchestrator.labor.base_url == "https://labor.example.com"
    finally:
        purge_module_namespace(module_name)


def test_object_container_rejects_unknown_object_binding_key_even_with_single_implementation(tmp_path: Path):
    module_name = "container_unknown_binding_module"
    module_dir = _write_quiz_module(tmp_path, module_name)

    try:
        descriptor = load_runtime_descriptor_v2(module_name, module_dir, _manifest(module_name))

        with pytest.raises(RuntimeError, match=r"object_bindings 包含未知注入路径: orchestrator\.laobr"):
            ObjectContainerV2(
                descriptor,
                "quiz_workflow",
                object_bindings={"orchestrator.laobr": "api_labor"},
                object_params={"api_labor": {"base_url": "https://labor.example.com"}},
            )
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


def test_object_container_rejects_unknown_object_param_component(tmp_path: Path):
    module_name = "container_unknown_param_component_module"
    module_dir = _write_quiz_module(tmp_path, module_name)

    try:
        descriptor = load_runtime_descriptor_v2(module_name, module_dir, _manifest(module_name))

        with pytest.raises(RuntimeError, match="object_params 引用了未声明 component: ghost"):
            ObjectContainerV2(
                descriptor,
                "quiz_workflow",
                object_params={"ghost": {"base_url": "https://labor.example.com"}},
            )
    finally:
        purge_module_namespace(module_name)


def test_object_container_rejects_unknown_component_parameter(tmp_path: Path):
    module_name = "container_unknown_param_module"
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
                    "unknown": True,
                }
            },
        )

        with pytest.raises(RuntimeError, match="api_labor.*未声明对象参数: unknown"):
            container.build_workflow()
    finally:
        purge_module_namespace(module_name)


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"base_url": 123}, "base_url 必须是字符串"),
        ({"base_url": "https://labor.example.com", "timeout": "fast"}, "timeout 必须是整数"),
        ({"base_url": "https://labor.example.com", "timeout": 0}, "timeout 不能小于 1"),
        ({"base_url": "https://labor.example.com", "timeout": 121}, "timeout 不能大于 120"),
        ({"base_url": "https://labor.example.com", "mode": "batch"}, "mode 不在允许范围"),
        ({"base_url": "https://labor.example.com", "enabled": "yes"}, "enabled 必须是布尔值"),
    ],
)
def test_object_container_validates_component_parameter_values(
    tmp_path: Path,
    params: dict[str, object],
    message: str,
):
    module_name = "container_invalid_param_values_module"
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
            object_params={"api_labor": params},
        )

        with pytest.raises(RuntimeError, match=message):
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

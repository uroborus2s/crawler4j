import importlib
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

import pytest

from crawler4j_contracts import TaskContext
from src.core.mms.models import ModuleInfo, ModuleManifest, WorkflowInfo
from src.core.mms.service import ModuleService


def _assert_removed_module(module_name: str) -> None:
    with pytest.raises(ModuleNotFoundError) as exc_info:
        importlib.import_module(module_name)

    assert exc_info.value.name == module_name


def test_removed_legacy_runtime_and_ui_surface_stays_unavailable():
    workspace_root = Path(__file__).resolve().parents[6]
    removed_paths = [
        workspace_root / "packages" / "crawler4j-sdk" / "src" / "assembler.py",
        workspace_root / "packages" / "crawler4j-sdk" / "src" / "base.py",
        workspace_root / "packages" / "crawler4j-sdk" / "src" / "env_selector.py",
        workspace_root / "packages" / "crawler4j-sdk" / "src" / "result.py",
        workspace_root / "packages" / "crawler4j-sdk" / "src" / "signal.py",
        workspace_root / "packages" / "crawler4j-sdk" / "src" / "workflow.py",
        workspace_root / "packages" / "crawler4j" / "src" / "automation",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "core",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "components" / "sidebar.py",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "components" / "config_editor.py",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "components" / "log_viewer.py",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "components" / "status_bar.py",
        workspace_root / "packages" / "crawler4j" / "src" / "ui" / "utils" / "syntax_highlighter.py",
    ]
    removed_modules = [
        "crawler4j_sdk.assembler",
        "crawler4j_sdk.base",
        "crawler4j_sdk.env_selector",
        "crawler4j_sdk.result",
        "crawler4j_sdk.signal",
        "crawler4j_sdk.workflow",
        "src.ui.core",
        "src.ui.components.sidebar",
        "src.ui.components.config_editor",
        "src.ui.components.log_viewer",
        "src.ui.components.status_bar",
        "src.ui.utils.syntax_highlighter",
        "src.utils.async_utils",
        "src.utils.captcha_solver",
        "src.utils.fingerprint_generator",
        "src.utils.hotel_matcher",
        "src.utils.network_checker",
        "src.utils.sms_platform",
    ]

    for path in removed_paths:
        assert path.exists() is False

    for module_name in removed_modules:
        _assert_removed_module(module_name)

    sdk_root = importlib.import_module("crawler4j_sdk")
    assert hasattr(sdk_root, "TaskContext") is False
    assert hasattr(sdk_root, "TaskResult") is False


class _FakeLocator:
    def __init__(self, present: bool):
        self.present = present
        self.last_filled: str | None = None
        self.click_count = 0

    async def count(self) -> int:
        return 1 if self.present else 0

    @property
    def first(self) -> "_FakeLocator":
        return self

    async def click(self, timeout: int | None = None):  # noqa: ARG002
        self.click_count += 1

    async def fill(self, value: str, timeout: int | None = None):  # noqa: ARG002
        self.last_filled = value


class _FakePage:
    def __init__(self):
        self.goto_calls: list[str] = []
        self.phone_locator = _FakeLocator(present=True)
        self.empty_locator = _FakeLocator(present=False)

    async def goto(self, url: str, wait_until: str | None = None):  # noqa: ARG002
        self.goto_calls.append(url)

    async def wait_for_timeout(self, ms: int):  # noqa: ARG002
        return None

    def locator(self, selector: str):
        if "input" in selector:
            return self.phone_locator
        return self.empty_locator


def _write_demo_module(module_dir: Path) -> None:
    tasks_dir = module_dir / "tasks"
    workflows_dir = module_dir / "workflows"
    hooks_dir = module_dir / "hooks"
    for package_dir in (module_dir, tasks_dir, workflows_dir, hooks_dir):
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")

    (module_dir / "__init__.py").write_text(
        dedent(
            """
            async def run(context):
                raise AssertionError("module root run() should not be called")
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (hooks_dir / "init_env.py").write_text(
        dedent(
            """
            from types import SimpleNamespace

            from crawler4j_contracts import TaskContext


            async def handle(context: TaskContext):
                account = context.get_config("accounts", [])[0]
                context.selected_account = SimpleNamespace(
                    id=account["id"],
                    phone_number=account["phone_number"],
                    country_code=account.get("country_code", "86"),
                )
                context.state["selected_account_phone"] = context.selected_account.phone_number
                if context.page:
                    await context.page.goto(
                        context.get_config("target_url", "https://example.com/start"),
                        wait_until="domcontentloaded",
                    )
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (tasks_dir / "login_task.py").write_text(
        dedent(
            """
            from crawler4j_contracts import TaskResult, TaskSpec

            TASK = TaskSpec(name="login_task", display_name="Login Task")


            async def execute(context):
                phone = str(context.state.get("selected_account_phone") or "")
                if context.page:
                    locator = context.page.locator("input[type='tel']")
                    if await locator.count() > 0:
                        await locator.first.click(timeout=1500)
                        await locator.first.fill(phone, timeout=1500)
                return TaskResult.ok(phone=phone)
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    (workflows_dir / "login_workflow.py").write_text(
        dedent(
            """
            from crawler4j_contracts import WorkflowSpec

            WORKFLOW = WorkflowSpec(name="login_workflow", tasks=("login_task",))


            async def run(context):
                return await context.run_subtask("login_task")
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def _demo_registry(module_dir: Path):
    return SimpleNamespace(
        get_module=lambda name: ModuleInfo(
            name="demo_module",
            manifest=ModuleManifest(
                name="demo_module",
                runtime_api="core-native-v1",
                workflows=[WorkflowInfo(name="login_workflow")],
                default_workflow="login_workflow",
            ),
            path=module_dir,
        )
    )


@pytest.mark.asyncio
async def test_module_service_init_hook_prepares_account_and_opens_target_page(tmp_path):
    module_dir = tmp_path / "demo_module"
    _write_demo_module(module_dir)

    service = ModuleService()
    service.registry = _demo_registry(module_dir)

    page = _FakePage()
    ctx = TaskContext(
        env_id=3,
        task_name="demo_module",
        config={
            "accounts": [{"id": "u1", "phone_number": "13800000001", "country_code": "86"}],
            "target_url": "https://example.com/start",
        },
        page=page,
    )
    ctx.state = {"job_id": "job-1", "task_id": "task-1"}

    await service.call_hook("demo_module", "init_env", ctx)

    assert getattr(ctx, "selected_account").phone_number == "13800000001"
    assert ctx.state["selected_account_phone"] == "13800000001"
    assert page.goto_calls[-1] == "https://example.com/start"


@pytest.mark.asyncio
async def test_module_service_runs_descriptor_workflow_without_calling_module_root_run(tmp_path):
    module_dir = tmp_path / "demo_module"
    _write_demo_module(module_dir)

    service = ModuleService()
    service.registry = _demo_registry(module_dir)

    page = _FakePage()
    ctx = TaskContext(
        env_id=5,
        task_name="demo_module",
        config={
            "accounts": [{"id": "u2", "phone_number": "13900000002", "country_code": "86"}],
            "target_url": "https://example.com/start",
        },
        page=page,
    )
    ctx.state = {"job_id": "job-2", "task_id": "task-2"}

    await service.call_hook("demo_module", "init_env", ctx)
    result = await service.run_module("demo_module", ctx)

    assert result.success is True
    assert result.data["phone"] == "13900000002"
    assert page.phone_locator.last_filled == "13900000002"

import importlib
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

import pytest

from crawler4j_sdk import TaskContext
from src.core.mms.models import ModuleInfo, ModuleManifest
from src.core.mms.service import ModuleService


def test_removed_runtime_packages_stay_unavailable():
    app_root = Path(__file__).resolve().parents[4]
    workspace_root = app_root.parents[1]
    removed_paths = [
        app_root / "src" / "automation",
        app_root / "src" / "core" / "models",
        workspace_root / "packages" / "crawler4j-sdk" / "crawler4j_sdk" / "extensions.py",
    ]
    removed_modules = [
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
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(module_name)


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
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "__init__.py").write_text(
        dedent(
            """
            from types import SimpleNamespace

            from crawler4j_sdk import TaskResult


            async def init_env(context):
                account = context.get_config("accounts", [])[0]
                context.selected_account = SimpleNamespace(
                    id=account["id"],
                    phone_number=account["phone_number"],
                    country_code=account.get("country_code", "86"),
                )
                context.state["selected_account_phone"] = context.selected_account.phone_number
                if context.page:
                    await context.page.goto(
                        context.get_config("login_url", "https://example.com/login"),
                        wait_until="domcontentloaded",
                    )


            async def run(context):
                phone = context.selected_account.phone_number
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


def _demo_registry(module_dir: Path):
    return SimpleNamespace(
        get_module=lambda name: ModuleInfo(
            name="demo_module",
            manifest=ModuleManifest(name="demo_module"),
            path=module_dir,
        )
    )


@pytest.mark.asyncio
async def test_module_init_hook_injects_account_and_opens_login_page(tmp_path):
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
            "login_url": "https://example.com/login",
        },
        page=page,
    )
    ctx.state = {"job_id": "job-1", "task_id": "task-1"}

    await service.call_hook("demo_module", "init_env", ctx)

    assert getattr(ctx, "selected_account").phone_number == "13800000001"
    assert ctx.state["selected_account_phone"] == "13800000001"
    assert page.goto_calls[-1] == "https://example.com/login"


@pytest.mark.asyncio
async def test_module_login_workflow_executes_login_script(tmp_path):
    module_dir = tmp_path / "demo_module"
    _write_demo_module(module_dir)

    service = ModuleService()
    service.registry = _demo_registry(module_dir)

    page = _FakePage()
    ctx = TaskContext(
        env_id=5,
        task_name="demo_module",
        config={
            "workflow": "login_workflow",
            "accounts": [{"id": "u2", "phone_number": "13900000002", "country_code": "86"}],
            "login_url": "https://example.com/login",
        },
        page=page,
    )
    ctx.state = {"job_id": "job-2", "task_id": "task-2"}

    await service.call_hook("demo_module", "init_env", ctx)
    result = await service.run_module("demo_module", ctx)

    assert result.success is True
    assert result.data["phone"] == "13900000002"
    assert page.phone_locator.last_filled == "13900000002"

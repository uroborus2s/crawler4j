import importlib
from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

import pytest

from crawler4j_sdk import TaskContext
from src.core.mms.models import ModuleInfo, ModuleManifest
from src.core.mms.service import ModuleService


def test_legacy_ctrip_runtime_imports_are_available():
    required_modules = [
        "src.automation.workflows.labor_claim_task",
        "src.automation.workflows.labor_login",
        "src.automation.workflows.ctrip_search",
        "src.automation.workflows.labor_submit",
    ]

    for module_name in required_modules:
        assert importlib.import_module(module_name) is not None


class _FakeDB:
    def __init__(self):
        self._datasets: dict[str, list[dict[str, str]]] = {}
        self._locks: set[str] = set()

    def list_records(self, dataset: str) -> list[dict[str, str]]:
        return list(self._datasets.get(dataset, []))

    def replace_records(self, dataset: str, accounts: list[dict[str, str]]) -> bool:
        self._datasets[dataset] = list(accounts)
        return True

    def acquire_lock(self, scope: str, key: str, *, ttl: int, owner=None):  # noqa: ARG002
        lock_key = f"{scope}:{key}"
        if lock_key in self._locks:
            return False
        self._locks.add(lock_key)
        return True

    def release_lock(self, scope: str, key: str):
        lock_key = f"{scope}:{key}"
        if lock_key in self._locks:
            self._locks.remove(lock_key)
            return True
        return False

    def is_locked(self, scope: str, key: str):
        return f"{scope}:{key}" in self._locks


class _FakeUI:
    def __init__(self):
        self.meta: dict[str, dict[str, object]] = {}

    def declare_data_table(self, view_id: str, schema: dict[str, object]) -> bool:
        self.meta[view_id] = schema or {}
        return True

    def get_data_table(self, view_id: str) -> dict[str, object]:
        return self.meta.get(view_id, {})


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


def _write_ctrip_module(module_dir: Path) -> None:
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "__init__.py").write_text(
        dedent(
            """
            from types import SimpleNamespace

            from crawler4j_sdk import TaskResult


            async def init_env(context):
                account = context.get_config("ctrip_accounts", [])[0]
                context.ctrip_account = SimpleNamespace(
                    id=account["id"],
                    phone_number=account["phone_number"],
                    country_code=account.get("country_code", "86"),
                )
                context.state["ctrip_account_phone"] = context.ctrip_account.phone_number
                if context.page:
                    await context.page.goto(
                        context.get_config("ctrip_login_url", "https://passport.ctrip.com/user/login"),
                        wait_until="domcontentloaded",
                    )


            async def run(context):
                phone = context.ctrip_account.phone_number
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


def _ctrip_registry(module_dir: Path):
    return SimpleNamespace(
        get_module=lambda name: ModuleInfo(
            name="ctrip",
            manifest=ModuleManifest(name="ctrip"),
            path=module_dir,
        )
    )


@pytest.mark.asyncio
async def test_ctrip_init_env_hook_injects_account_and_opens_login_page(tmp_path):
    module_dir = tmp_path / "ctrip_crawler"
    _write_ctrip_module(module_dir)

    service = ModuleService()
    service.registry = _ctrip_registry(module_dir)

    page = _FakePage()
    ctx = TaskContext(
        env_id=3,
        task_name="ctrip",
        config={
            "ctrip_accounts": [{"id": "u1", "phone_number": "13800000001", "country_code": "86"}],
            "ctrip_login_url": "https://passport.ctrip.com/user/login",
        },
        page=page,
        db=_FakeDB(),
        ui=_FakeUI(),
    )
    ctx.state = {"job_id": "job-1", "task_id": "task-1"}

    await service.call_hook("ctrip", "init_env", ctx)

    assert getattr(ctx, "ctrip_account").phone_number == "13800000001"
    assert ctx.state["ctrip_account_phone"] == "13800000001"
    assert page.goto_calls[-1] == "https://passport.ctrip.com/user/login"


@pytest.mark.asyncio
async def test_ctrip_module_login_workflow_executes_login_script(tmp_path):
    module_dir = tmp_path / "ctrip_crawler"
    _write_ctrip_module(module_dir)

    service = ModuleService()
    service.registry = _ctrip_registry(module_dir)

    page = _FakePage()
    ctx = TaskContext(
        env_id=5,
        task_name="ctrip",
        config={
            "workflow": "login_workflow",
            "ctrip_accounts": [{"id": "u2", "phone_number": "13900000002", "country_code": "86"}],
            "ctrip_login_url": "https://passport.ctrip.com/user/login",
        },
        page=page,
        db=_FakeDB(),
        ui=_FakeUI(),
    )
    ctx.state = {"job_id": "job-2", "task_id": "task-2"}

    await service.call_hook("ctrip", "init_env", ctx)
    result = await service.run_module("ctrip", ctx)

    assert result.success is True
    assert result.data["phone"] == "13900000002"
    assert page.phone_locator.last_filled == "13900000002"

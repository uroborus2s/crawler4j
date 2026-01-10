import argparse
from pathlib import Path

import pytest

from crawler4j_sdk.base import TaskScript
from crawler4j_sdk.cli import commands as cli
from crawler4j_sdk.context import TaskContext
from crawler4j_sdk.result import TaskResult
from src.plugins.script_executor import ScriptExecutor
from src.plugins.script_manager import ScriptManager


def test_taskresult_ok_fields_and_data():
    r = TaskResult.ok(tasks_completed=2, message="OK", foo=1)
    assert r.success is True
    assert r.tasks_completed == 2
    assert r.message == "OK"
    assert r.error is None
    assert r.data == {"foo": 1}


def test_taskresult_fail_supports_data():
    r = TaskResult.fail(message="NO", error="E", data={"a": 1}, b=2)
    assert r.success is False
    assert r.tasks_completed == 0
    assert r.message == "NO"
    assert r.error == "E"
    assert r.data == {"a": 1, "b": 2}


def test_taskcontext_get_config_default():
    ctx = TaskContext(env_id=1, task_name="t", config={"a": 1})
    assert ctx.get_config("a") == 1
    assert ctx.get_config("missing", 2) == 2


@pytest.mark.asyncio
async def test_taskcontext_screenshot_requires_page():
    ctx = TaskContext(env_id=1, task_name="t")
    with pytest.raises(RuntimeError):
        await ctx.screenshot("x")


class _DummyPage:
    async def screenshot(self, path: str):
        Path(path).write_bytes(b"fake-png")


@pytest.mark.asyncio
async def test_taskcontext_screenshot_creates_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ctx = TaskContext(env_id=1, task_name="t")
    ctx.page = _DummyPage()
    saved = await ctx.screenshot("hello")
    saved_path = Path(saved)
    assert saved_path.exists()
    assert saved_path.parts[0] == "screenshots"


@pytest.mark.asyncio
async def test_taskcontext_run_subtask_requires_injection():
    ctx = TaskContext(env_id=1, task_name="t")
    with pytest.raises(RuntimeError):
        await ctx.run_subtask("any")


@pytest.mark.asyncio
async def test_taskcontext_run_subtask_merges_state_and_returns_data():
    ctx = TaskContext(env_id=1, task_name="t")

    async def _exec(task_name: str, ctx_: TaskContext):
        assert task_name == "child"
        return TaskResult.ok(data={"ok": True}, got=ctx_.state.get("a"))

    ctx._subtask_executor = _exec
    out = await ctx.run_subtask("child", a=123)
    assert ctx.state["a"] == 123
    assert out == {"ok": True, "got": 123}


@pytest.mark.asyncio
async def test_runtime_lifecycle_order_via_script_executor_success():
    calls: list[str] = []

    class T(TaskScript):
        name = "t"

        async def on_init(self, ctx: TaskContext) -> None:
            calls.append("init")

        async def execute(self, ctx: TaskContext) -> TaskResult:
            calls.append("execute")
            return TaskResult.ok()

        async def on_cleanup(self, ctx: TaskContext) -> None:
            calls.append("cleanup")

    ctx = TaskContext(env_id=1, task_name="t")
    r = await ScriptExecutor().execute(T, ctx)
    assert r.success is True
    assert calls == ["init", "execute", "cleanup"]


@pytest.mark.asyncio
async def test_runtime_lifecycle_order_via_script_executor_error_path():
    calls: list[str] = []

    class T(TaskScript):
        name = "t"

        async def on_init(self, ctx: TaskContext) -> None:
            calls.append("init")

        async def execute(self, ctx: TaskContext) -> TaskResult:
            calls.append("execute")
            raise ValueError("boom")

        async def on_error(self, ctx: TaskContext, error: Exception) -> None:
            calls.append("error")

        async def on_cleanup(self, ctx: TaskContext) -> None:
            calls.append("cleanup")

    ctx = TaskContext(env_id=1, task_name="t")
    r = await ScriptExecutor().execute(T, ctx)
    assert r.success is False
    assert "boom" in (r.message or "")
    assert calls == ["init", "execute", "error", "cleanup"]


@pytest.mark.asyncio
async def test_runtime_lifecycle_order_via_script_manager_run_task():
    calls: list[str] = []

    class T(TaskScript):
        name = "t"

        async def on_init(self, ctx: TaskContext) -> None:
            calls.append("init")

        async def execute(self, ctx: TaskContext) -> TaskResult:
            calls.append("execute")
            return TaskResult.ok()

        async def on_cleanup(self, ctx: TaskContext) -> None:
            calls.append("cleanup")

    manager = ScriptManager()
    manager._scripts = {"t": T}
    manager._workflows = {}

    ctx = TaskContext(env_id=1, task_name="t")
    r = await manager.run_task("t", ctx)
    assert r.success is True
    assert calls == ["init", "execute", "cleanup"]


def test_cli_init_new_add_list(tmp_path, monkeypatch, capsys):
    # init
    out_dir = tmp_path / "proj"
    args = argparse.Namespace(name="proj", output=str(out_dir), force=False, no_install=True)
    assert cli.cmd_init(args) == 0
    assert (out_dir / "pyproject.toml").exists()
    assert (out_dir / "tasks" / "example_task.py").exists()

    # new / add / list (run inside a fake project)
    monkeypatch.chdir(out_dir)
    assert cli.cmd_new(argparse.Namespace(name="a_task", force=False)) == 0
    assert (out_dir / "tasks" / "a_task.py").exists()

    # add (interactive prompts still happen for display_name/description)
    answers = iter(["", ""])  # display_name, description
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    assert cli.cmd_add(argparse.Namespace(name="b_task", force=False)) == 0
    assert (out_dir / "tasks" / "b_task.py").exists()

    # list
    assert cli.cmd_list(argparse.Namespace()) == 0
    out = capsys.readouterr().out
    assert "a_task" in out
    assert "b_task" in out

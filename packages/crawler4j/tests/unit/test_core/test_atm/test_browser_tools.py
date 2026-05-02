from __future__ import annotations

import sys
from contextlib import ExitStack
from dataclasses import dataclass
from unittest.mock import patch

import pytest

from crawler4j_contracts import TaskContext

from src.core.atm.browser_tools import BrowserToolConfig, CoreBrowserTools
from src.core.atm.runtime_capabilities import build_runtime_capabilities


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


class FakeMouse:
    def __init__(self) -> None:
        self.moves: list[tuple[float, float]] = []
        self.clicks: list[tuple[float, float, str]] = []
        self.wheels: list[tuple[float, float]] = []
        self.events: list[str] = []
        self.down_count = 0
        self.up_count = 0

    async def move(self, x: float, y: float) -> None:
        self.moves.append((round(x, 6), round(y, 6)))
        self.events.append("move")

    async def click(self, x: float, y: float, button: str = "left") -> None:
        self.clicks.append((round(x, 6), round(y, 6), button))
        self.events.append("click")

    async def wheel(self, delta_x: float, delta_y: float) -> None:
        self.wheels.append((round(delta_x, 6), round(delta_y, 6)))
        self.events.append("wheel")

    async def down(self, button: str = "left") -> None:
        self.down_count += 1
        self.events.append(f"down:{button}")

    async def up(self, button: str = "left") -> None:
        self.up_count += 1
        self.events.append(f"up:{button}")


class FakeKeyboard:
    def __init__(self) -> None:
        self.presses: list[str] = []
        self.typed: list[str] = []
        self.downs: list[str] = []
        self.ups: list[str] = []

    async def press(self, key: str) -> None:
        self.presses.append(key)

    async def type(self, text: str) -> None:
        self.typed.append(text)

    async def down(self, key: str) -> None:
        self.downs.append(key)

    async def up(self, key: str) -> None:
        self.ups.append(key)


class FakeLocator:
    def __init__(
        self,
        *,
        bbox: dict[str, float] | None = None,
    ) -> None:
        self.first = self
        self._bbox = bbox or {"x": 100.0, "y": 200.0, "width": 120.0, "height": 48.0}
        self.scroll_calls = 0

    async def scroll_into_view_if_needed(self) -> None:
        self.scroll_calls += 1

    async def bounding_box(self) -> dict[str, float] | None:
        return dict(self._bbox)


class FakePage:
    def __init__(self, selectors: dict[str, FakeLocator] | None = None) -> None:
        self.url = ""
        self.goto_calls: list[tuple[str, str, int]] = []
        self._selectors = selectors or {}
        self.mouse = FakeMouse()
        self.keyboard = FakeKeyboard()

    async def goto(self, url: str, *, wait_until: str, timeout: int) -> None:
        self.url = url
        self.goto_calls.append((url, wait_until, timeout))

    def locator(self, selector: str) -> FakeLocator:
        return self._selectors.setdefault(selector, FakeLocator())


@dataclass(slots=True)
class CapturedSleep:
    delays: list[float]

    async def __call__(self, delay: float) -> None:
        self.delays.append(delay)


def test_browser_tools_are_hidden_until_task_context_has_page():
    caps = build_runtime_capabilities("demo_module")

    assert caps.tools.has_tool("browser.click") is False
    assert not any(spec.name.startswith("browser.") for spec in caps.tools.list_tools())

    context = TaskContext(env_id=0, task_name="demo_module", tools=caps.tools, page=None)

    assert context.tools is not None
    assert context.tools.has_tool("browser.click") is False
    with pytest.raises(RuntimeError, match="需要当前运行上下文绑定可用的浏览器 Page"):
        context.tools.call("browser.click", selector=".submit")


@pytest.mark.asyncio
async def test_browser_tools_support_goto_click_type_drag_scroll(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.core.atm.browser_tools.asyncio.sleep", CapturedSleep(delays=[]))

    page = FakePage(
        {
            ".submit": FakeLocator(bbox={"x": 20.0, "y": 30.0, "width": 140.0, "height": 60.0}),
            "input[name='phone']": FakeLocator(),
            ".slider": FakeLocator(bbox={"x": 100.0, "y": 180.0, "width": 40.0, "height": 40.0}),
        }
    )
    caps = build_runtime_capabilities("demo_module")
    context = TaskContext(env_id=1, task_name="demo_module", page=page, tools=caps.tools)

    assert context.tools is not None
    assert context.tools.has_tool("browser.goto") is True
    assert context.tools.has_tool("browser.click") is True
    assert context.tools.has_tool("browser.type") is True
    assert context.tools.has_tool("browser.drag") is True
    assert context.tools.has_tool("browser.scroll") is True

    goto_result = await context.tools.call("browser.goto", url="https://example.com/login")
    click_result = await context.tools.call("browser.click", selector=".submit")
    hover_result = await context.tools.call("browser.hover", selector=".submit")
    type_result = await context.tools.call(
        "browser.type",
        selector="input[name='phone']",
        text="13800138000",
        clear=True,
        mode="exact",
    )
    press_result = await context.tools.call("browser.press", key="Control+A")
    drag_result = await context.tools.call(
        "browser.drag",
        selector=".slider",
        delta_x=220.0,
        mode="precise",
        steps=8,
    )
    scroll_result = await context.tools.call("browser.scroll", delta_y=900.0)

    assert page.goto_calls == [("https://example.com/login", "domcontentloaded", 60000)]
    assert goto_result["url"] == "https://example.com/login"
    assert goto_result["trace"]["pre_navigation_delay"] > 0
    assert goto_result["trace"]["post_navigation_delay"] > 0
    assert click_result["button"] == "left"
    assert page.mouse.clicks == []
    assert click_result["trace"]["move"]["steps"] > 0
    assert click_result["trace"]["dwell"] > 0
    assert hover_result["trace"]["dwell"] > 0
    expected_select_all = "Meta+A" if sys.platform == "darwin" else "Control+A"
    assert page.keyboard.presses[:2] == [expected_select_all, "Backspace"]
    assert "".join(page.keyboard.typed) == "13800138000"
    assert type_result["mode"] == "exact"
    assert type_result["trace"]["clear_strategy"] == "select_all"
    assert page.keyboard.downs[-2:] == ["Control", "A"]
    assert page.keyboard.ups[-2:] == ["A", "Control"]
    assert press_result["trace"]["strategy"] == "down_up"
    assert page.mouse.down_count == page.mouse.up_count
    assert page.mouse.down_count >= 3
    assert drag_result["mode"] == "precise"
    assert drag_result["target"]["x"] > 100.0
    assert len(page.mouse.wheels) >= 3
    assert round(sum(delta_y for _, delta_y in page.mouse.wheels), 6) == pytest.approx(900.0)
    assert scroll_result["delta_y"] == 900.0
    assert scroll_result["trace"]["inertia"] is True
    assert scroll_result["trace"]["correction"] is not None
    assert all(payload["session"]["seed"] == goto_result["session"]["seed"] for payload in [click_result, type_result, drag_result, scroll_result])


@pytest.mark.asyncio
async def test_typing_correction_probability_controls_rewrite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.core.atm.browser_tools.asyncio.sleep", CapturedSleep(delays=[]))

    no_correction_page = FakePage({"input": FakeLocator()})
    no_correction_tools = CoreBrowserTools(
        seed=7,
        config=BrowserToolConfig(typing_correction_probability=0.0),
    )
    no_correction_tools.bind_task_context(
        TaskContext(env_id=1, task_name="demo_module", page=no_correction_page, tools=None)
    )

    no_correction_result = await no_correction_tools.type(
        selector="input",
        text="abcdef",
        clear=False,
        mode="natural",
        allow_correction=True,
    )

    assert no_correction_result["trace"]["correction_allowed"] is True
    assert no_correction_result["trace"]["correction_probability"] == 0.0
    assert no_correction_result["trace"]["correction_attempted"] is False
    assert no_correction_result["trace"]["corrections"] == []
    assert "Backspace" not in no_correction_page.keyboard.presses

    correction_page = FakePage({"input": FakeLocator()})
    correction_tools = CoreBrowserTools(
        seed=7,
        config=BrowserToolConfig(typing_correction_probability=1.0),
    )
    correction_tools.bind_task_context(TaskContext(env_id=1, task_name="demo_module", page=correction_page, tools=None))

    correction_result = await correction_tools.type(
        selector="input",
        text="abcdef",
        clear=False,
        mode="natural",
        allow_correction=True,
    )

    assert correction_result["trace"]["correction_probability"] == 1.0
    assert correction_result["trace"]["correction_attempted"] is True
    assert correction_result["trace"]["corrections"]
    assert "Backspace" in correction_page.keyboard.presses


@pytest.mark.asyncio
async def test_sensitive_natural_typing_skips_corrections_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.core.atm.browser_tools.asyncio.sleep", CapturedSleep(delays=[]))

    page = FakePage({"input": FakeLocator()})
    tools = CoreBrowserTools(seed=7, config=BrowserToolConfig(typing_correction_probability=1.0))
    tools.bind_task_context(TaskContext(env_id=1, task_name="demo_module", page=page, tools=None))

    result = await tools.type(selector="input", text="13800138000", clear=False, mode="natural")

    assert result["trace"]["correction_allowed"] is False
    assert result["trace"]["sensitive_input"] is True
    assert result["trace"]["correction_attempted"] is False
    assert "Backspace" not in page.keyboard.presses


@pytest.mark.asyncio
async def test_browser_tools_fail_fast_for_unknown_modes_and_invalid_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.core.atm.browser_tools.asyncio.sleep", CapturedSleep(delays=[]))

    page = FakePage({"input": FakeLocator(), ".slider": FakeLocator()})
    tools = CoreBrowserTools(seed=3)
    tools.bind_task_context(TaskContext(env_id=1, task_name="demo_module", page=page, tools=None))

    with pytest.raises(ValueError, match="browser.type mode"):
        await tools.type(selector="input", text="hello", mode="robotic")
    with pytest.raises(ValueError, match="browser.drag mode"):
        await tools.drag(selector=".slider", delta_x=20.0, mode="robotic")
    with pytest.raises(ValueError, match="clicks"):
        await tools.click(x=10.0, y=20.0, clicks=0)
    with pytest.raises(ValueError, match="steps"):
        await tools.move(x=10.0, y=20.0, steps=0)
    with pytest.raises(ValueError, match="chunks"):
        await tools.scroll(delta_y=100.0, chunks=1)


@pytest.mark.asyncio
async def test_movement_steps_scale_with_distance_and_target_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.core.atm.browser_tools.asyncio.sleep", CapturedSleep(delays=[]))

    small = FakeLocator(bbox={"x": 500.0, "y": 400.0, "width": 10.0, "height": 10.0})
    large = FakeLocator(bbox={"x": 520.0, "y": 420.0, "width": 180.0, "height": 80.0})
    page = FakePage({".small": small, ".large": large})
    tools = CoreBrowserTools(seed=11)
    tools.bind_task_context(TaskContext(env_id=1, task_name="demo_module", page=page, tools=None))

    small_result = await tools.click(selector=".small")
    large_result = await tools.click(selector=".large")

    assert small_result["trace"]["target_size"]["width"] == 10.0
    assert small_result["trace"]["move"]["distance"] > 100.0
    assert small_result["trace"]["move"]["steps"] > large_result["trace"]["move"]["steps"]

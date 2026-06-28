"""Host-owned humanized browser interaction tools."""

from __future__ import annotations

import asyncio
import math
import random
import secrets
import sys
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class BrowserToolConfig:
    pause_range: tuple[float, float] = (0.06, 0.18)
    click_pause_range: tuple[float, float] = (0.08, 0.24)
    typing_start_pause_range: tuple[float, float] = (0.12, 0.32)
    typing_chunk_pause_range: tuple[float, float] = (0.03, 0.09)
    typing_correction_pause_range: tuple[float, float] = (0.05, 0.14)
    move_steps_range: tuple[int, int] = (12, 22)
    drag_steps_range: tuple[int, int] = (26, 42)
    natural_drag_total_duration_range: tuple[float, float] = (1.2, 2.8)
    scroll_chunks_range: tuple[int, int] = (2, 6)
    scroll_chunk_pause_range: tuple[float, float] = (0.03, 0.11)
    mouse_down_dwell_range: tuple[float, float] = (0.045, 0.135)
    hover_dwell_range: tuple[float, float] = (0.18, 0.52)
    press_dwell_range: tuple[float, float] = (0.035, 0.12)
    pause_segments_range: tuple[int, int] = (2, 4)
    idle_motion_radius_range: tuple[float, float] = (4.0, 14.0)
    navigation_scan_radius_range: tuple[float, float] = (8.0, 24.0)
    click_margin_ratio: float = 0.18
    drag_margin_ratio: float = 0.14
    entry_point_x_range: tuple[float, float] = (92.0, 262.0)
    entry_point_y_range: tuple[float, float] = (78.0, 220.0)
    typing_correction_probability: float = 0.34
    drag_probe_ratio: tuple[float, float] = (0.04, 0.09)
    drag_overshoot_ratio: tuple[float, float] = (0.035, 0.075)
    drag_recover_ratio: tuple[float, float] = (0.12, 0.22)
    scroll_wobble_ratio: float = 0.18
    viewport_margin: float = 1.0
    select_all_shortcut: str | None = None

    def __post_init__(self) -> None:
        if self.select_all_shortcut is None:
            self.select_all_shortcut = "Meta+A" if sys.platform == "darwin" else "Control+A"


@dataclass(slots=True)
class BrowserSessionProfile:
    session_seed: int
    persona: str
    entry_point: tuple[float, float]
    motion_speed: float
    motion_curve: float
    pause_range: tuple[float, float]
    click_pause_range: tuple[float, float]
    typing_start_pause_range: tuple[float, float]
    typing_chunk_pause_range: tuple[float, float]
    typing_correction_pause_range: tuple[float, float]
    typing_mode: str
    typing_correction_probability: float
    click_margin_ratio: float
    drag_margin_ratio: float
    move_steps_range: tuple[int, int]
    drag_steps_range: tuple[int, int]
    drag_pre_pause_range: tuple[float, float]
    drag_probe_ratio: tuple[float, float]
    drag_overshoot_ratio: tuple[float, float]
    drag_recover_ratio: tuple[float, float]
    scroll_chunks_range: tuple[int, int]
    scroll_chunk_pause_range: tuple[float, float]
    scroll_wobble_ratio: float


@dataclass(slots=True)
class TypingTrace:
    mode: str
    clear_strategy: str
    chunks: list[str]
    corrections: list[str]
    correction_allowed: bool
    correction_attempted: bool
    correction_probability: float
    sensitive_input: bool
    sensitive_reasons: list[str]
    field_context: dict[str, Any] | None


@dataclass(slots=True)
class PauseTrace:
    scheduled_delay: float
    idle_motion_duration: float
    effective_delay: float
    total_delay: float
    segments: list[float]
    idle_motion: dict[str, Any] | None


@dataclass(slots=True)
class MoveTrace:
    start: tuple[float, float]
    target: tuple[float, float]
    requested_target: tuple[float, float]
    distance: float
    steps: int
    duration: float
    target_size: dict[str, float] | None
    acquisition_index: float
    viewport: dict[str, float] | None


@dataclass(slots=True)
class DragTrace:
    start: tuple[float, float]
    probe: tuple[float, float]
    approach: tuple[float, float]
    overshoot: tuple[float, float] | None
    settle: tuple[float, float] | None
    target: tuple[float, float]
    steps: list[int]
    pre_pause: float
    down_dwell: float
    release_pause: float
    strategy: str
    continuous_profile: str | None
    down_position: tuple[float, float]
    up_position: tuple[float, float]
    phase_names: list[str]
    phases: list[dict[str, Any]]
    sample_count: int


@dataclass(slots=True)
class ScrollTrace:
    chunks: list[tuple[float, float]]
    pauses: list[float]
    inertia: bool
    correction: tuple[float, float] | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    boundary: dict[str, bool] | None


class CoreBrowserTools:
    """Humanized browser primitives bound to the current TaskContext."""

    def __init__(
        self,
        *,
        seed: int | None = None,
        config: BrowserToolConfig | None = None,
    ) -> None:
        self._config = config or BrowserToolConfig()
        self._seed = seed if seed is not None else secrets.randbits(64)
        self._rng = random.Random(self._seed)
        self._session_profile = self._build_session_profile()
        self._task_context: Any | None = None
        self._bound_page: Any | None = None
        self._current_position: tuple[float, float] | None = None
        self._has_moved = False
        self._last_move_trace: MoveTrace | None = None
        self._last_move_samples: list[tuple[float, float, float]] = []

    def bind_task_context(self, context: Any) -> None:
        self._task_context = context
        page = getattr(context, "page", None)
        if page is self._bound_page:
            return
        self._bound_page = page
        self._current_position = self._random_entry_point()
        self._has_moved = False
        self._last_move_samples = []

    def is_available(self) -> bool:
        return self._page_or_none() is not None

    async def pause(
        self,
        minimum: float | None = None,
        maximum: float | None = None,
        *,
        idle_motion: bool = True,
    ) -> dict[str, Any]:
        self._validate_optional_range("browser.pause", minimum, maximum)
        low, high = self._pick_range(minimum, maximum, default=self._session_profile.pause_range)
        delay = self._rand_float(low, high)
        idle_trace = await self._idle_micro_motion() if idle_motion else None
        idle_duration = self._trace_duration(idle_trace)
        segments = self._split_pause_segments(delay)
        for segment in segments:
            await asyncio.sleep(segment)
        trace = PauseTrace(
            scheduled_delay=delay,
            idle_motion_duration=idle_duration,
            effective_delay=delay + idle_duration,
            total_delay=delay + idle_duration,
            segments=segments,
            idle_motion=idle_trace,
        )
        return {"delay": delay, "trace": asdict(trace), "session": self._session_metadata()}

    async def goto(
        self,
        url: str,
        *,
        wait_until: str = "domcontentloaded",
        timeout: int = 60000,
        before_pause: tuple[float, float] = (0.15, 0.35),
        after_pause: tuple[float, float] = (0.25, 0.45),
    ) -> dict[str, Any]:
        page = self._page()
        self._validate_range("before_pause", before_pause)
        self._validate_range("after_pause", after_pause)
        pre_scan = await self._idle_micro_motion(radius_range=self._config.navigation_scan_radius_range)
        before = await self.pause(*before_pause, idle_motion=False)
        await page.goto(url, wait_until=wait_until, timeout=timeout)
        self._current_position = self._random_entry_point()
        self._has_moved = False
        after = await self.pause(*after_pause, idle_motion=False)
        post_scan = await self._idle_micro_motion(radius_range=self._config.navigation_scan_radius_range)
        settle_delay = self._rand_float(0.08, 0.22)
        await asyncio.sleep(settle_delay)
        return {
            "url": self.current_url(),
            "wait_until": wait_until,
            "before_pause": before["delay"],
            "after_pause": after["delay"],
            "trace": {
                "pre_navigation_delay": before["delay"],
                "post_navigation_delay": after["delay"],
                "settle_delay": settle_delay,
                "pre_scan": pre_scan,
                "post_scan": post_scan,
            },
            "session": self._session_metadata(),
        }

    async def move(
        self,
        *,
        x: float,
        y: float,
        steps: int | None = None,
        precise: bool = False,
    ) -> dict[str, Any]:
        self._validate_steps(steps)
        if precise:
            target = await self._move_to_precise(float(x), float(y), steps=steps)
        else:
            target = await self._move_to(float(x), float(y), steps=steps)
        return {
            "point": {"x": target[0], "y": target[1]},
            "precise": precise,
            "trace": self._move_trace_dict(),
            "session": self._session_metadata(),
        }

    async def click(
        self,
        *,
        selector: str | None = None,
        locator: Any | None = None,
        x: float | None = None,
        y: float | None = None,
        button: str = "left",
        clicks: int = 1,
        steps: int | None = None,
        selector_hint: str | None = None,
    ) -> dict[str, Any]:
        self._validate_clicks(clicks)
        self._validate_steps(steps)
        target_size: dict[str, float] | None = None
        if selector:
            locator = self._page().locator(selector).first
            selector_hint = selector
        if locator is not None:
            await self._scroll_locator_into_view(locator)
            box = await self._bounding_box(locator)
            if box is None:
                detail = selector_hint or selector or "locator"
                raise RuntimeError(f"unable to resolve bounding box for selector: {detail}")
            target_x, target_y = self._point_within_box(box, margin_ratio=self._session_profile.click_margin_ratio)
            target_size = self._target_size(box)
        else:
            if x is None or y is None:
                raise ValueError("browser.click 需要 selector / locator 或 x+y 坐标")
            target_x = float(x)
            target_y = float(y)
        await self._move_to(target_x, target_y, steps=steps, target_size=target_size)
        move_trace = self._move_trace_dict()
        settle_trace = await self._settle_around_point(target_x, target_y)
        pre_click_pause = self._rand_float(*self._session_profile.click_pause_range)
        await asyncio.sleep(pre_click_pause)
        dwells: list[float] = []
        for index in range(clicks):
            await self._mouse_down(button)
            dwell = self._rand_float(*self._config.mouse_down_dwell_range)
            dwells.append(dwell)
            await asyncio.sleep(dwell)
            await self._mouse_up(button)
            if index < clicks - 1:
                await asyncio.sleep(self._rand_float(0.055, 0.16))
        return {
            "point": {"x": target_x, "y": target_y},
            "button": button,
            "clicks": clicks,
            "selector": selector_hint or selector,
            "trace": {
                "move": move_trace,
                "settle": settle_trace,
                "target_size": target_size,
                "pre_click_pause": pre_click_pause,
                "dwell": dwells[0] if dwells else 0.0,
                "dwells": dwells,
            },
            "session": self._session_metadata(),
        }

    async def hover(
        self,
        *,
        selector: str | None = None,
        locator: Any | None = None,
        x: float | None = None,
        y: float | None = None,
        selector_hint: str | None = None,
    ) -> dict[str, Any]:
        target_size: dict[str, float] | None = None
        if selector:
            locator = self._page().locator(selector).first
            selector_hint = selector
        if locator is not None:
            await self._scroll_locator_into_view(locator)
            box = await self._bounding_box(locator)
            if box is None:
                detail = selector_hint or selector or "locator"
                raise RuntimeError(f"unable to resolve bounding box for selector: {detail}")
            x, y = self._point_within_box(box, margin_ratio=self._session_profile.click_margin_ratio)
            target_size = self._target_size(box)
        if x is None or y is None:
            raise ValueError("browser.hover 需要 selector / locator 或 x+y 坐标")
        target = await self._move_to(float(x), float(y), target_size=target_size)
        move_trace = self._move_trace_dict()
        dwell = self._rand_float(*self._config.hover_dwell_range)
        drift = await self._hover_drift(target[0], target[1], target_size=target_size)
        await asyncio.sleep(dwell)
        return {
            "point": {"x": target[0], "y": target[1]},
            "selector": selector_hint or selector,
            "pause": dwell,
            "trace": {"move": move_trace, "target_size": target_size, "dwell": dwell, "drift": drift},
            "session": self._session_metadata(),
        }

    async def type(
        self,
        *,
        selector: str | None = None,
        locator: Any | None = None,
        text: str,
        clear: bool = True,
        mode: str = "natural",
        press_enter: bool = False,
        start_pause_range: tuple[float, float] | None = None,
        chunk_pause_range: tuple[float, float] | None = None,
        chunk_range: tuple[int, int] | None = None,
        allow_correction: bool | None = None,
    ) -> dict[str, Any]:
        self._validate_mode("browser.type mode", mode, {"exact", "natural"})
        if chunk_range is not None:
            self._validate_int_range("chunk_range", chunk_range)
        if start_pause_range is not None:
            self._validate_range("start_pause_range", start_pause_range)
        if chunk_pause_range is not None:
            self._validate_range("chunk_pause_range", chunk_pause_range)
        if selector:
            locator = self._page().locator(selector).first
        if locator is None:
            if not selector:
                raise ValueError("browser.type 需要 selector 或 locator")
            locator = self._page().locator(selector).first
        field_context = await self._field_context(locator, selector_hint=selector)
        focus_click = await self.click(locator=locator, selector_hint=selector)
        initial_pause_range = start_pause_range or self._session_profile.typing_start_pause_range
        start_pause = self._rand_float(*initial_pause_range)
        await asyncio.sleep(start_pause)
        if mode == "exact":
            trace = await self._type_exact(
                text=text,
                clear=clear,
                chunk_pause_range=chunk_pause_range,
                chunk_range=chunk_range,
                field_context=field_context,
            )
        else:
            trace = await self._type_natural(
                text=text,
                clear=clear,
                chunk_pause_range=chunk_pause_range,
                allow_correction=allow_correction,
                field_context=field_context,
            )
        enter_pause: float | None = None
        if press_enter:
            enter_pause = self._rand_float(0.04, 0.12)
            await asyncio.sleep(enter_pause)
            await self._page().keyboard.press("Enter")
        trace_payload = asdict(trace)
        trace_payload.update(
            {
                "focus_click": focus_click["trace"],
                "start_pause": start_pause,
                "enter_pause": enter_pause,
            }
        )
        return {
            "text": text,
            "mode": mode,
            "press_enter": press_enter,
            "trace": trace_payload,
            "session": self._session_metadata(),
        }

    async def press(self, *, key: str) -> dict[str, Any]:
        before = self._rand_float(0.035, 0.11)
        await asyncio.sleep(before)
        key_trace = await self._press_key_down_up(key)
        after = self._rand_float(0.025, 0.085)
        await asyncio.sleep(after)
        key_trace.update({"before": before, "after": after})
        return {
            "key": key,
            "trace": key_trace,
            "session": self._session_metadata(),
        }

    async def drag(
        self,
        *,
        selector: str | None = None,
        locator: Any | None = None,
        start_x: float | None = None,
        start_y: float | None = None,
        target_x: float | None = None,
        target_y: float | None = None,
        delta_x: float | None = None,
        delta_y: float | None = None,
        mode: str = "natural",
        steps: int | None = None,
        release_pause: bool = True,
    ) -> dict[str, Any]:
        self._validate_mode("browser.drag mode", mode, {"natural", "precise"})
        self._validate_steps(steps)
        if selector:
            locator = self._page().locator(selector).first
        if locator is not None:
            await self._scroll_locator_into_view(locator)
            box = await self._bounding_box(locator)
            if box is None:
                detail = selector or "locator"
                raise RuntimeError(f"unable to resolve bounding box for selector: {detail}")
            start_x, start_y = self._point_within_box(box, margin_ratio=self._session_profile.drag_margin_ratio)
        if start_x is None or start_y is None:
            raise ValueError("browser.drag 需要 selector / locator 或显式 start_x+start_y")
        if target_x is None:
            if delta_x is None:
                raise ValueError("browser.drag 需要 target_x 或 delta_x")
            target_x = float(start_x) + float(delta_x)
        if target_y is None:
            target_y = float(start_y) if delta_y is None else float(start_y) + float(delta_y)
        if mode == "precise":
            target, trace = await self._drag_to_precise(
                float(start_x),
                float(start_y),
                float(target_x),
                float(target_y),
                steps=steps,
                release_pause=release_pause,
            )
        else:
            target, trace = await self._drag_to(
                float(start_x),
                float(start_y),
                float(target_x),
                float(target_y),
                steps=steps,
                release_pause=release_pause,
            )
        return {
            "mode": mode,
            "target": {"x": target[0], "y": target[1]},
            "trace": asdict(trace),
            "session": self._session_metadata(),
        }

    async def scroll(
        self,
        *,
        delta_y: float,
        delta_x: float = 0.0,
        chunks: int | None = None,
    ) -> dict[str, Any]:
        self._validate_chunks(chunks)
        chunk_count = chunks if chunks is not None else self._rand_int(*self._session_profile.scroll_chunks_range)
        remaining_x = float(delta_x)
        correction_y = 0.0
        if abs(delta_y) >= 120.0:
            correction_y = -math.copysign(min(18.0, abs(delta_y) * self._rand_float(0.008, 0.02)), delta_y)
        remaining_y = float(delta_y) - correction_y
        weights = [self._rand_float(1.15, 1.55) * (0.72**index) for index in range(chunk_count)]
        weight_total = sum(weights)
        pauses: list[float] = []
        chunks_recorded: list[tuple[float, float]] = []
        before = await self._scroll_snapshot()
        await self.pause(0.01, 0.05, idle_motion=False)
        for index, weight in enumerate(weights):
            if index == chunk_count - 1:
                chunk_x = remaining_x
                chunk_y = remaining_y
            else:
                share = weight / weight_total
                chunk_x = float(delta_x) * share
                chunk_y = float(delta_y) * share
                remaining_x -= chunk_x
                remaining_y -= chunk_y
            if self._rand_float(0.0, 1.0) < self._session_profile.scroll_wobble_ratio:
                chunk_x += self._rand_float(-3.0, 3.0)
            await self._page().mouse.wheel(chunk_x, chunk_y)
            pause = self._rand_float(*self._session_profile.scroll_chunk_pause_range)
            pauses.append(pause)
            chunks_recorded.append((chunk_x, chunk_y))
            await asyncio.sleep(pause)
        correction: tuple[float, float] | None = None
        if correction_y:
            pause = self._rand_float(*self._session_profile.scroll_chunk_pause_range)
            correction = (0.0, correction_y)
            await self._page().mouse.wheel(0.0, correction_y)
            chunks_recorded.append(correction)
            pauses.append(pause)
            await asyncio.sleep(pause)
        after = await self._scroll_snapshot()
        trace = ScrollTrace(
            chunks=chunks_recorded,
            pauses=pauses,
            inertia=True,
            correction=correction,
            before=before,
            after=after,
            boundary=self._scroll_boundary(before=before, after=after, delta_y=float(delta_y)),
        )
        return {
            "delta_x": float(delta_x),
            "delta_y": float(delta_y),
            "trace": asdict(trace),
            "session": self._session_metadata(),
        }

    async def page_down(self) -> dict[str, Any]:
        viewport_height = self._viewport_height(default=self._rand_float(720.0, 960.0))
        ratio = self._rand_float(0.72, 0.92)
        delta_y = viewport_height * ratio
        result = await self.scroll(delta_y=delta_y)
        result["trace"].update(
            {
                "action": "page_down",
                "viewport_height": viewport_height,
                "distance_ratio": ratio,
                "derived_delta_y": delta_y,
            }
        )
        return result

    async def page_up(self) -> dict[str, Any]:
        viewport_height = self._viewport_height(default=self._rand_float(720.0, 960.0))
        ratio = self._rand_float(0.72, 0.92)
        delta_y = -(viewport_height * ratio)
        result = await self.scroll(delta_y=delta_y)
        result["trace"].update(
            {
                "action": "page_up",
                "viewport_height": viewport_height,
                "distance_ratio": ratio,
                "derived_delta_y": delta_y,
            }
        )
        return result

    def current_url(self) -> str:
        page = self._page_or_none()
        if page is None:
            return ""
        url = getattr(page, "url", "")
        if callable(url):
            try:
                url = url()
            except Exception:
                url = ""
        return str(url or "")

    def _page_or_none(self) -> Any | None:
        if self._task_context is None:
            return None
        return getattr(self._task_context, "page", None)

    def _page(self) -> Any:
        page = self._page_or_none()
        if page is None:
            raise RuntimeError("当前运行上下文没有可用的浏览器 Page")
        return page

    async def _type_exact(
        self,
        *,
        text: str,
        clear: bool,
        chunk_pause_range: tuple[float, float] | None,
        chunk_range: tuple[int, int] | None,
        field_context: dict[str, Any] | None,
    ) -> TypingTrace:
        if clear:
            await self._page().keyboard.press(self._config.select_all_shortcut or "Control+A")
            await self._page().keyboard.press("Backspace")
            await asyncio.sleep(self._rand_float(0.02, 0.06))
        if chunk_range is None:
            chunk_min = 2 if len(text) >= 4 else 1
            chunk_max = 4 if len(text) >= 6 else max(2, len(text))
        else:
            chunk_min, chunk_max = chunk_range
        sensitive_reasons = self._sensitive_reasons(text, field_context=field_context)
        trace = TypingTrace(
            mode="exact",
            clear_strategy="select_all" if clear else "none",
            chunks=self._chunk_text(text, chunk_min, chunk_max) or ([text] if text else []),
            corrections=[],
            correction_allowed=False,
            correction_attempted=False,
            correction_probability=0.0,
            sensitive_input=bool(sensitive_reasons),
            sensitive_reasons=sensitive_reasons,
            field_context=field_context,
        )
        pauses = chunk_pause_range or self._session_profile.typing_chunk_pause_range
        for index, chunk in enumerate(trace.chunks):
            await self._page().keyboard.type(chunk)
            if index < len(trace.chunks) - 1:
                await asyncio.sleep(self._rand_float(*pauses))
        return trace

    async def _type_natural(
        self,
        *,
        text: str,
        clear: bool,
        chunk_pause_range: tuple[float, float] | None,
        allow_correction: bool | None,
        field_context: dict[str, Any] | None,
    ) -> TypingTrace:
        if clear:
            await self._page().keyboard.press(self._config.select_all_shortcut or "Control+A")
            await self._page().keyboard.press("Backspace")
            await asyncio.sleep(self._rand_float(0.02, 0.06))
        mode = self._session_profile.typing_mode
        chunks = self._chunk_text(text, *self._typing_chunk_range_for_mode(mode)) or ([text] if text else [])
        corrections: list[str] = []
        pauses = chunk_pause_range or self._session_profile.typing_chunk_pause_range
        sensitive_reasons = self._sensitive_reasons(text, field_context=field_context)
        sensitive_input = bool(sensitive_reasons)
        correction_allowed = (not sensitive_input) if allow_correction is None else allow_correction
        correction_probability = self._session_profile.typing_correction_probability if correction_allowed else 0.0
        correction_attempted = (
            correction_allowed
            and len(text) > 2
            and self._rand_float(0.0, 1.0) < correction_probability
        )
        if correction_attempted:
            corrections = [await self._type_with_rewrite(text, chunk_pause_range=pauses)]
        else:
            for index, chunk in enumerate(chunks):
                await self._page().keyboard.type(chunk)
                if index < len(chunks) - 1:
                    pause = self._rand_float(*pauses)
                    if mode == "stutter":
                        pause *= self._rand_float(1.2, 1.8)
                    await asyncio.sleep(pause)
        return TypingTrace(
            mode=mode,
            clear_strategy="select_all" if clear else "none",
            chunks=chunks,
            corrections=corrections,
            correction_allowed=correction_allowed,
            correction_attempted=correction_attempted,
            correction_probability=correction_probability,
            sensitive_input=sensitive_input,
            sensitive_reasons=sensitive_reasons,
            field_context=field_context,
        )

    async def _type_with_rewrite(
        self,
        text: str,
        *,
        chunk_pause_range: tuple[float, float],
    ) -> str:
        if len(text) < 3:
            for chunk in self._chunk_text(text, 1, 2):
                await self._page().keyboard.type(chunk)
                await asyncio.sleep(self._rand_float(*chunk_pause_range))
            return ""
        correction_index = self._rand_int(1, len(text) - 2)
        prefix = text[:correction_index]
        wrong_char = self._pick_wrong_char(text[correction_index])
        correct_char = text[correction_index]
        suffix = text[correction_index + 1 :]
        correction_pause_range = self._session_profile.typing_correction_pause_range
        for chunk in self._chunk_text(prefix, 1, 3):
            await self._page().keyboard.type(chunk)
            await asyncio.sleep(self._rand_float(*chunk_pause_range))
        await self._page().keyboard.type(wrong_char)
        await asyncio.sleep(self._rand_float(*correction_pause_range))
        await self._page().keyboard.press("Backspace")
        await asyncio.sleep(self._rand_float(*correction_pause_range))
        await self._page().keyboard.type(correct_char)
        await asyncio.sleep(self._rand_float(*chunk_pause_range))
        for chunk in self._chunk_text(suffix, 1, 3):
            await self._page().keyboard.type(chunk)
            await asyncio.sleep(self._rand_float(*chunk_pause_range))
        return f"{wrong_char}->{correct_char}@{correction_index}"

    async def _drag_to(
        self,
        start_x: float,
        start_y: float,
        target_x: float,
        target_y: float,
        *,
        steps: int | None,
        release_pause: bool,
    ) -> tuple[tuple[float, float], DragTrace]:
        dx = target_x - start_x
        dy = target_y - start_y
        direction_x = 1.0 if dx >= 0 else -1.0
        profile = self._rng.choices(
            ["direct", "soft_overshoot", "late_correction", "hesitant"],
            weights=[3.0, 2.0, 2.8, 2.2],
            k=1,
        )[0]
        await self._move_to(start_x, start_y)
        pre_pause_delay = self._rand_float(*self._session_profile.drag_pre_pause_range)
        await asyncio.sleep(pre_pause_delay)
        await self._page().mouse.down()
        down_dwell = self._rand_float(0.05, 0.13)
        release_pause_delay = self._rand_float(0.1, 0.22) if release_pause else 0.0
        await asyncio.sleep(down_dwell)
        total_steps = steps if steps is not None else self._rand_int(*self._session_profile.drag_steps_range)
        point_count = max(8, int(total_steps * self._rand_float(1.0, 1.45)))
        planned_duration = self._planned_natural_drag_move_duration(
            start_x,
            start_y,
            target_x,
            target_y,
            pre_pause=pre_pause_delay,
            down_dwell=down_dwell,
            release_pause=release_pause_delay,
        )
        curve_power = self._rand_float(1.55, 2.45)
        side_phase = self._rand_float(0.0, math.tau)
        side_frequency = self._rand_float(0.75, 1.65)
        side_amplitude = self._clamp_between(abs(dx) * self._rand_float(0.006, 0.022), 0.8, 5.2)
        overshoot_strength = self._rand_float(0.025, 0.075) if profile == "soft_overshoot" else 0.0
        correction_strength = self._rand_float(0.006, 0.025) if profile in {"late_correction", "hesitant"} else 0.0
        weights: list[float] = []
        for index in range(1, point_count + 1):
            t = index / point_count
            weight = self._rand_float(0.7, 1.35)
            if profile == "hesitant" and 0.58 <= t <= 0.78:
                weight *= self._rand_float(1.45, 2.35)
            if profile == "late_correction" and t >= 0.86:
                weight *= self._rand_float(1.2, 1.8)
            weights.append(weight)
        weight_total = sum(weights)
        overshoot: tuple[float, float] | None = None
        settle: tuple[float, float] | None = None
        phases: list[dict[str, Any] | None] = []
        samples: list[tuple[float, float, float]] = []
        duration = 0.0
        viewport = self._viewport_size()
        try:
            for index, weight in enumerate(weights, start=1):
                t = index / point_count
                base = 1.0 - ((1.0 - t) ** curve_power)
                progress = base
                if profile == "soft_overshoot":
                    progress += overshoot_strength * (math.sin(math.pi * t) ** 0.7)
                elif profile == "late_correction" and t >= 0.78:
                    progress -= correction_strength * (math.sin(math.pi * min(1.0, (t - 0.78) / 0.22)) ** 2)
                elif profile == "hesitant" and 0.55 <= t <= 0.76:
                    progress -= correction_strength * self._rand_float(0.35, 0.85)
                if index == point_count:
                    progress = 1.0
                envelope = math.sin(math.pi * t) ** 0.75
                lateral = math.sin((math.pi * side_frequency * t) + side_phase) * side_amplitude * envelope
                lateral += self._rand_float(-0.35, 0.35) * envelope
                px = start_x + dx * progress
                py = start_y + dy * progress + lateral
                if index == point_count:
                    px, py = target_x, target_y
                px, py = self._clamp_to_viewport(px, py, viewport=viewport)
                pause = max(0.003, planned_duration * (weight / weight_total))
                await self._page().mouse.move(px, py)
                samples.append((px, py, pause))
                duration += pause
                await asyncio.sleep(pause)
        finally:
            await self._page().mouse.up()
        if samples:
            beyond_target = [
                sample
                for sample in samples
                if (direction_x >= 0 and sample[0] > target_x) or (direction_x < 0 and sample[0] < target_x)
            ]
            if beyond_target:
                overshoot_sample = max(beyond_target, key=lambda sample: abs(sample[0] - target_x))
                overshoot = (overshoot_sample[0], overshoot_sample[1])
            if profile in {"late_correction", "hesitant"} and len(samples) >= 2:
                settle = (samples[-2][0], samples[-2][1])
        self._current_position = (target_x, target_y)
        self._last_move_samples = samples
        self._last_move_trace = MoveTrace(
            start=(start_x, start_y),
            target=(target_x, target_y),
            requested_target=(target_x, target_y),
            distance=self._distance(start_x, start_y, target_x, target_y),
            steps=point_count,
            duration=duration,
            target_size=None,
            acquisition_index=self._target_acquisition_index(start_x, start_y, target_x, target_y, target_size=None),
            viewport=viewport,
        )
        phases.append(self._drag_phase_trace("continuous"))
        if release_pause_delay > 0:
            await asyncio.sleep(release_pause_delay)
        phase_traces = [phase for phase in phases if phase is not None]
        probe_point = samples[min(len(samples) - 1, max(0, int(len(samples) * 0.15)))] if samples else (start_x, start_y, 0.0)
        approach_point = samples[min(len(samples) - 1, max(0, int(len(samples) * 0.62)))] if samples else (target_x, target_y, 0.0)
        trace = DragTrace(
            start=(start_x, start_y),
            probe=(probe_point[0], probe_point[1]),
            approach=(approach_point[0], approach_point[1]),
            overshoot=overshoot,
            settle=settle,
            target=(target_x, target_y),
            steps=[phase["steps"] for phase in phase_traces],
            pre_pause=pre_pause_delay,
            down_dwell=down_dwell,
            release_pause=release_pause_delay,
            strategy="continuous",
            continuous_profile=profile,
            down_position=(start_x, start_y),
            up_position=(target_x, target_y),
            phase_names=[phase["name"] for phase in phase_traces],
            phases=phase_traces,
            sample_count=sum(len(phase["samples"]) for phase in phase_traces),
        )
        return (target_x, target_y), trace

    async def _drag_to_precise(
        self,
        start_x: float,
        start_y: float,
        target_x: float,
        target_y: float,
        *,
        steps: int | None,
        release_pause: bool,
    ) -> tuple[tuple[float, float], DragTrace]:
        dx = target_x - start_x
        dy = target_y - start_y
        direction_x = 1.0 if dx >= 0 else -1.0
        probe_ratio = self._rand_float(0.03, 0.07)
        approach_ratio = self._rand_float(0.58, 0.82)
        settle_offset = min(max(1.0, abs(dx) * self._rand_float(0.008, 0.02)), 4.0)
        probe_x = self._clamp_segment_point(
            start_x + dx * probe_ratio + direction_x * self._rand_float(0.6, 1.8),
            start_x,
            target_x,
        )
        probe_y = start_y + dy * probe_ratio + self._rand_float(-0.6, 0.6)
        approach_x = self._clamp_segment_point(start_x + dx * approach_ratio, start_x, target_x)
        approach_y = start_y + dy * approach_ratio + self._rand_float(-0.4, 0.4)
        pre_target_x = target_x
        if abs(dx) > 3.0:
            pre_target_x = self._clamp_segment_point(target_x - direction_x * settle_offset, start_x, target_x)
        pre_target_y = target_y + self._rand_float(-0.3, 0.3)
        micro_offset = min(settle_offset, self._rand_float(0.35, 1.25))
        micro_x = target_x
        if abs(dx) > 3.0:
            micro_x = self._clamp_segment_point(target_x - direction_x * micro_offset, start_x, target_x)
        micro_y = target_y + self._rand_float(-0.18, 0.18)
        await self._move_to(start_x, start_y)
        pre_pause_delay = self._rand_float(*self._session_profile.drag_pre_pause_range)
        await asyncio.sleep(pre_pause_delay)
        await self._page().mouse.down()
        down_dwell = self._rand_float(0.05, 0.12)
        release_pause_delay = 0.0
        await asyncio.sleep(down_dwell)
        total_steps = steps if steps is not None else self._rand_int(*self._session_profile.drag_steps_range)
        probe_steps = max(2, int(total_steps * 0.16))
        approach_steps = max(4, int(total_steps * 0.44))
        settle_steps = max(3, int(total_steps * 0.26))
        final_steps = max(2, int(total_steps * 0.14))
        micro_steps = max(2, int(total_steps * 0.08))
        phases: list[dict[str, Any] | None] = []
        try:
            await self._move_to_precise(probe_x, probe_y, steps=probe_steps)
            phases.append(self._drag_phase_trace("probe"))
            await asyncio.sleep(self._rand_float(0.02, 0.06))
            await self._move_to_precise(approach_x, approach_y, steps=approach_steps)
            phases.append(self._drag_phase_trace("approach"))
            await asyncio.sleep(self._rand_float(0.02, 0.05))
            await self._move_to_precise(pre_target_x, pre_target_y, steps=settle_steps)
            phases.append(self._drag_phase_trace("pre_target"))
            await asyncio.sleep(self._rand_float(0.015, 0.04))
            await self._move_to_precise(micro_x, micro_y, steps=micro_steps)
            phases.append(self._drag_phase_trace("micro_adjust"))
            await asyncio.sleep(self._rand_float(0.01, 0.03))
            await self._move_to_precise(target_x, target_y, steps=final_steps)
            phases.append(self._drag_phase_trace("target"))
        finally:
            await self._page().mouse.up()
        if release_pause:
            release_pause_delay = self._rand_float(0.09, 0.18)
            await asyncio.sleep(release_pause_delay)
        phase_traces = [phase for phase in phases if phase is not None]
        trace = DragTrace(
            start=(start_x, start_y),
            probe=(probe_x, probe_y),
            approach=(approach_x, approach_y),
            overshoot=None,
            settle=(pre_target_x, pre_target_y),
            target=(target_x, target_y),
            steps=[phase["steps"] for phase in phase_traces],
            pre_pause=pre_pause_delay,
            down_dwell=down_dwell,
            release_pause=release_pause_delay,
            strategy="segmented",
            continuous_profile=None,
            down_position=(start_x, start_y),
            up_position=(target_x, target_y),
            phase_names=[phase["name"] for phase in phase_traces],
            phases=phase_traces,
            sample_count=sum(len(phase["samples"]) for phase in phase_traces),
        )
        self._current_position = (target_x, target_y)
        return (target_x, target_y), trace

    async def _scroll_locator_into_view(self, locator: Any) -> None:
        try:
            await locator.scroll_into_view_if_needed()
        except Exception:
            pass

    async def _bounding_box(self, locator: Any) -> dict[str, float] | None:
        try:
            box = await locator.bounding_box()
        except Exception:
            return None
        if not box:
            return None
        if box.get("width", 0) <= 0 or box.get("height", 0) <= 0:
            return None
        return box

    async def _field_context(self, locator: Any, *, selector_hint: str | None) -> dict[str, Any] | None:
        if locator is None:
            return None
        context: dict[str, Any] = {"selector": selector_hint}
        for name in ("type", "name", "id", "autocomplete", "inputmode", "placeholder", "aria-label"):
            value = await self._locator_attribute(locator, name)
            if value not in (None, ""):
                context[name.replace("-", "_")] = str(value)
        if len(context) == 1 and context.get("selector") is None:
            return None
        return context

    async def _locator_attribute(self, locator: Any, name: str) -> str | None:
        getter = getattr(locator, "get_attribute", None)
        if callable(getter):
            try:
                value = await getter(name)
            except Exception:
                value = None
            if value not in (None, ""):
                return str(value)
        evaluator = getattr(locator, "evaluate", None)
        if callable(evaluator):
            try:
                value = await evaluator("(element, name) => element.getAttribute(name)", name)
            except TypeError:
                try:
                    value = await evaluator(f"(element) => element.getAttribute({name!r})")
                except Exception:
                    value = None
            except Exception:
                value = None
            if value not in (None, ""):
                return str(value)
        return None

    async def _scroll_snapshot(self) -> dict[str, Any] | None:
        page = self._page_or_none()
        evaluator = getattr(page, "evaluate", None) if page is not None else None
        if not callable(evaluator):
            return None
        try:
            snapshot = await evaluator(
                """() => ({
                    x: window.scrollX,
                    y: window.scrollY,
                    maxY: Math.max(0, document.documentElement.scrollHeight - window.innerHeight),
                    maxX: Math.max(0, document.documentElement.scrollWidth - window.innerWidth)
                })"""
            )
        except Exception:
            return None
        if not isinstance(snapshot, dict):
            return None
        normalized: dict[str, Any] = {}
        for key in ("x", "y", "maxX", "maxY"):
            value = snapshot.get(key)
            if isinstance(value, int | float):
                normalized[key] = float(value)
        return normalized or None

    def _scroll_boundary(
        self,
        *,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        delta_y: float,
    ) -> dict[str, bool] | None:
        if not before or not after:
            return None
        y = float(after.get("y", 0.0))
        max_y = float(after.get("maxY", 0.0))
        moved = abs(y - float(before.get("y", 0.0))) > 0.5
        at_top = y <= 0.5
        at_bottom = y >= max(0.0, max_y - 0.5)
        blocked = (delta_y < 0 and at_top and not moved) or (delta_y > 0 and at_bottom and not moved)
        return {
            "moved": moved,
            "at_top": at_top,
            "at_bottom": at_bottom,
            "blocked": blocked,
        }

    async def _move_to(
        self,
        x: float,
        y: float,
        *,
        steps: int | None = None,
        target_size: dict[str, float] | None = None,
    ) -> tuple[float, float]:
        start_x, start_y = self._ensure_position()
        requested_x, requested_y = x, y
        viewport = self._viewport_size()
        x, y = self._clamp_to_viewport(x, y, viewport=viewport)
        if not self._has_moved:
            await self._page().mouse.move(start_x, start_y)
            await asyncio.sleep(self._rand_float(0.01, 0.03))
            self._has_moved = True
        step_count = self._planned_move_steps(start_x, start_y, x, y, steps=steps, target_size=target_size)
        planned_duration = self._planned_move_duration(start_x, start_y, x, y, target_size=target_size)
        control_1_x, control_1_y = self._curve_control_point(
            start_x, start_y, x, y, 0.24, self._session_profile.motion_curve
        )
        control_2_x, control_2_y = self._curve_control_point(x, y, start_x, start_y, 0.12, 0.52)
        duration = 0.0
        samples: list[tuple[float, float, float]] = []
        for index in range(1, step_count + 1):
            t = index / step_count
            px = self._cubic_bezier(start_x, control_1_x, control_2_x, x, t)
            py = self._cubic_bezier(start_y, control_1_y, control_2_y, y, t)
            wobble = (1.0 - abs(2.0 * t - 1.0)) * self._rand_float(-0.9, 0.9)
            px += wobble * self._session_profile.scroll_wobble_ratio
            py += wobble * self._session_profile.scroll_wobble_ratio
            await self._page().mouse.move(px, py)
            pause = max(0.003, (planned_duration / step_count) * self._rand_float(0.72, 1.28))
            samples.append((px, py, pause))
            duration += pause
            await asyncio.sleep(pause)
        self._current_position = (x, y)
        self._last_move_samples = samples
        self._last_move_trace = MoveTrace(
            start=(start_x, start_y),
            target=(x, y),
            requested_target=(requested_x, requested_y),
            distance=self._distance(start_x, start_y, x, y),
            steps=step_count,
            duration=duration,
            target_size=target_size,
            acquisition_index=self._target_acquisition_index(start_x, start_y, x, y, target_size=target_size),
            viewport=viewport,
        )
        return x, y

    async def _move_to_precise(
        self,
        x: float,
        y: float,
        *,
        steps: int | None = None,
        target_size: dict[str, float] | None = None,
    ) -> tuple[float, float]:
        start_x, start_y = self._ensure_position()
        requested_x, requested_y = x, y
        viewport = self._viewport_size()
        x, y = self._clamp_to_viewport(x, y, viewport=viewport)
        if not self._has_moved:
            await self._page().mouse.move(start_x, start_y)
            await asyncio.sleep(self._rand_float(0.01, 0.03))
            self._has_moved = True
        step_count = self._planned_move_steps(start_x, start_y, x, y, steps=steps, target_size=target_size)
        planned_duration = self._planned_move_duration(start_x, start_y, x, y, target_size=target_size, precise=True)
        min_x = min(start_x, x)
        max_x = max(start_x, x)
        min_y = min(start_y, y) - 0.8
        max_y = max(start_y, y) + 0.8
        duration = 0.0
        samples: list[tuple[float, float, float]] = []
        for index in range(1, step_count + 1):
            t = index / step_count
            eased = 1.0 - ((1.0 - t) ** 2)
            px = start_x + (x - start_x) * eased
            py = start_y + (y - start_y) * eased
            if index < step_count:
                py += self._rand_float(-0.45, 0.45) * (1.0 - abs(2.0 * t - 1.0))
            px = self._clamp_between(px, min_x, max_x)
            py = self._clamp_between(py, min_y, max_y)
            await self._page().mouse.move(px, py)
            pause = max(0.003, (planned_duration / step_count) * self._rand_float(0.78, 1.18))
            samples.append((px, py, pause))
            duration += pause
            await asyncio.sleep(pause)
        self._current_position = (x, y)
        self._last_move_samples = samples
        self._last_move_trace = MoveTrace(
            start=(start_x, start_y),
            target=(x, y),
            requested_target=(requested_x, requested_y),
            distance=self._distance(start_x, start_y, x, y),
            steps=step_count,
            duration=duration,
            target_size=target_size,
            acquisition_index=self._target_acquisition_index(start_x, start_y, x, y, target_size=target_size),
            viewport=viewport,
        )
        return x, y

    async def _settle_around_point(self, x: float, y: float) -> list[dict[str, Any]]:
        if self._rand_float(0.0, 1.0) > 0.68:
            return []
        settle_x = x + self._rand_float(-2.8, 2.8)
        settle_y = y + self._rand_float(-2.4, 2.4)
        await self._move_to(settle_x, settle_y, steps=max(2, self._rand_int(2, 4)))
        outward = self._move_trace_dict()
        await asyncio.sleep(self._rand_float(0.01, 0.04))
        await self._move_to(x, y, steps=max(2, self._rand_int(2, 4)))
        back = self._move_trace_dict()
        return [trace for trace in (outward, back) if trace is not None]

    async def _idle_micro_motion(
        self,
        *,
        radius_range: tuple[float, float] | None = None,
    ) -> dict[str, Any] | None:
        if self._page_or_none() is None:
            return None
        low, high = radius_range or self._config.idle_motion_radius_range
        radius = self._rand_float(low, high)
        angle = self._rand_float(0.0, math.tau)
        start_x, start_y = self._ensure_position()
        drift_x = start_x + math.cos(angle) * radius
        drift_y = start_y + math.sin(angle) * radius
        await self._move_to_precise(drift_x, drift_y, steps=self._rand_int(2, 5))
        outward = self._move_trace_dict()
        dwell = self._rand_float(0.012, 0.045)
        await asyncio.sleep(dwell)
        await self._move_to_precise(start_x, start_y, steps=self._rand_int(2, 4))
        back = self._move_trace_dict()
        return {
            "start": {"x": start_x, "y": start_y},
            "drift": {"x": drift_x, "y": drift_y},
            "radius": radius,
            "dwell": dwell,
            "outward": outward,
            "back": back,
            "duration": self._trace_duration({"outward": outward, "back": back, "dwell": dwell}),
        }

    async def _hover_drift(
        self,
        x: float,
        y: float,
        *,
        target_size: dict[str, float] | None,
    ) -> list[dict[str, Any]]:
        drift_count = self._rand_int(1, 2)
        target_width = min(target_size["width"], target_size["height"]) if target_size else 24.0
        radius = self._clamp_between(target_width * self._rand_float(0.03, 0.08), 0.8, 4.5)
        traces: list[dict[str, Any]] = []
        for _ in range(drift_count):
            angle = self._rand_float(0.0, math.tau)
            drift_x = x + math.cos(angle) * radius
            drift_y = y + math.sin(angle) * radius
            await self._move_to_precise(drift_x, drift_y, steps=self._rand_int(2, 4), target_size=target_size)
            trace = self._move_trace_dict()
            if trace is not None:
                traces.append(trace)
            await asyncio.sleep(self._rand_float(0.018, 0.055))
        await self._move_to_precise(x, y, steps=self._rand_int(2, 4), target_size=target_size)
        trace = self._move_trace_dict()
        if trace is not None:
            traces.append(trace)
        return traces

    def _ensure_position(self) -> tuple[float, float]:
        if self._current_position is None:
            self._current_position = self._session_profile.entry_point
        return self._current_position

    def _random_entry_point(self) -> tuple[float, float]:
        return (
            self._rand_float(*self._config.entry_point_x_range),
            self._rand_float(*self._config.entry_point_y_range),
        )

    def _build_session_profile(self) -> BrowserSessionProfile:
        persona_a = ["quiet", "methodical", "restless", "curious", "steady", "nimble"]
        persona_b = ["morning", "noon", "evening", "warm", "cool", "soft", "sharp"]
        typing_modes = ["burst", "stutter", "rewrite"]
        entry_point = self._random_entry_point()
        motion_speed = self._rand_float(0.82, 1.22)
        motion_curve = self._rand_float(0.24, 0.68)
        typing_mode = self._rng.choices(typing_modes, weights=[3.0, 2.5, 1.8], k=1)[0]
        typing_correction_probability = self._clamp_between(self._config.typing_correction_probability, 0.0, 1.0)
        pause_range = self._scale_range(self._config.pause_range, 1.0 / motion_speed)
        click_pause_range = self._scale_range(self._config.click_pause_range, 1.0 / motion_speed)
        typing_start_pause_range = self._scale_range(self._config.typing_start_pause_range, 1.0 / motion_speed)
        typing_chunk_pause_range = self._scale_range(self._config.typing_chunk_pause_range, 1.0 / motion_speed)
        typing_correction_pause_range = self._scale_range(
            self._config.typing_correction_pause_range,
            1.0 / motion_speed,
        )
        drag_pre_pause_range = self._scale_range((0.08, 0.18), 1.0 / motion_speed)
        scroll_chunk_pause_range = self._scale_range(self._config.scroll_chunk_pause_range, 1.0 / motion_speed)
        move_steps_range = self._scale_int_range(self._config.move_steps_range, motion_speed)
        drag_steps_range = self._scale_int_range(self._config.drag_steps_range, motion_speed)
        scroll_chunks_range = self._scaled_scroll_chunks(motion_speed)
        return BrowserSessionProfile(
            session_seed=self._seed,
            persona=f"{self._rng.choice(persona_a)}-{self._rng.choice(persona_b)}",
            entry_point=entry_point,
            motion_speed=motion_speed,
            motion_curve=motion_curve,
            pause_range=pause_range,
            click_pause_range=click_pause_range,
            typing_start_pause_range=typing_start_pause_range,
            typing_chunk_pause_range=typing_chunk_pause_range,
            typing_correction_pause_range=typing_correction_pause_range,
            typing_mode=typing_mode,
            typing_correction_probability=typing_correction_probability,
            click_margin_ratio=self._config.click_margin_ratio,
            drag_margin_ratio=self._config.drag_margin_ratio,
            move_steps_range=move_steps_range,
            drag_steps_range=drag_steps_range,
            drag_pre_pause_range=drag_pre_pause_range,
            drag_probe_ratio=self._config.drag_probe_ratio,
            drag_overshoot_ratio=self._config.drag_overshoot_ratio,
            drag_recover_ratio=self._config.drag_recover_ratio,
            scroll_chunks_range=scroll_chunks_range,
            scroll_chunk_pause_range=scroll_chunk_pause_range,
            scroll_wobble_ratio=self._config.scroll_wobble_ratio,
        )

    def _typing_chunk_range_for_mode(self, mode: str) -> tuple[int, int]:
        if mode == "burst":
            return (2, 4)
        if mode == "stutter":
            return (1, 2)
        return (1, 3)

    def _session_metadata(self) -> dict[str, Any]:
        return {
            "seed": self._session_profile.session_seed,
            "persona": self._session_profile.persona,
        }

    def _move_trace_dict(self) -> dict[str, Any] | None:
        if self._last_move_trace is None:
            return None
        return asdict(self._last_move_trace)

    def _drag_phase_trace(self, name: str) -> dict[str, Any] | None:
        if self._last_move_trace is None:
            return None
        trace = asdict(self._last_move_trace)
        return {
            "name": name,
            "start": trace["start"],
            "target": trace["target"],
            "requested_target": trace["requested_target"],
            "distance": trace["distance"],
            "steps": trace["steps"],
            "duration": trace["duration"],
            "samples": [{"x": x, "y": y, "dt": dt} for x, y, dt in self._last_move_samples],
        }

    def _point_within_box(
        self,
        box: dict[str, float],
        *,
        margin_ratio: float,
    ) -> tuple[float, float]:
        x_margin = box["width"] * margin_ratio
        y_margin = box["height"] * margin_ratio
        left = box["x"] + x_margin
        right = box["x"] + box["width"] - x_margin
        top = box["y"] + y_margin
        bottom = box["y"] + box["height"] - y_margin
        if right <= left:
            left = box["x"]
            right = box["x"] + box["width"]
        if bottom <= top:
            top = box["y"]
            bottom = box["y"] + box["height"]
        return self._rand_float(left, right), self._rand_float(top, bottom)

    def _target_size(self, box: dict[str, float]) -> dict[str, float]:
        return {"width": float(box["width"]), "height": float(box["height"])}

    def _planned_move_steps(
        self,
        start_x: float,
        start_y: float,
        target_x: float,
        target_y: float,
        *,
        steps: int | None,
        target_size: dict[str, float] | None,
    ) -> int:
        if steps is not None:
            return steps
        distance = self._distance(start_x, start_y, target_x, target_y)
        base_steps = self._rand_int(*self._session_profile.move_steps_range)
        acquisition_index = self._target_acquisition_index(
            start_x,
            start_y,
            target_x,
            target_y,
            target_size=target_size,
        )
        distance_steps = int(max(1.0, distance / self._rand_float(14.0, 22.0)))
        planned = max(base_steps, int(round(distance_steps + acquisition_index * self._rand_float(3.8, 5.8))))
        return max(1, int(round(planned * self._session_profile.motion_speed)))

    def _planned_move_duration(
        self,
        start_x: float,
        start_y: float,
        target_x: float,
        target_y: float,
        *,
        target_size: dict[str, float] | None,
        precise: bool = False,
    ) -> float:
        distance = self._distance(start_x, start_y, target_x, target_y)
        acquisition_index = self._target_acquisition_index(
            start_x,
            start_y,
            target_x,
            target_y,
            target_size=target_size,
        )
        base = 0.08 + distance / self._rand_float(1450.0, 2100.0)
        precision_cost = acquisition_index * self._rand_float(0.018, 0.032)
        if precise:
            precision_cost *= 1.18
        return max(0.035, (base + precision_cost) / self._session_profile.motion_speed)

    def _planned_natural_drag_move_duration(
        self,
        start_x: float,
        start_y: float,
        target_x: float,
        target_y: float,
        *,
        pre_pause: float,
        down_dwell: float,
        release_pause: float,
    ) -> float:
        base = self._planned_move_duration(start_x, start_y, target_x, target_y, target_size=None)
        planned = base * self._rand_float(3.8, 6.4)
        minimum, maximum = self._config.natural_drag_total_duration_range
        fixed = pre_pause + down_dwell + release_pause
        return self._clamp_between(planned, max(0.08, minimum - fixed), max(0.08, maximum - fixed))

    def _target_acquisition_index(
        self,
        start_x: float,
        start_y: float,
        target_x: float,
        target_y: float,
        *,
        target_size: dict[str, float] | None,
    ) -> float:
        distance = self._distance(start_x, start_y, target_x, target_y)
        width = 24.0
        if target_size is not None:
            width = max(3.0, min(float(target_size["width"]), float(target_size["height"])))
        return math.log2((distance / width) + 1.0)

    def _distance(self, start_x: float, start_y: float, target_x: float, target_y: float) -> float:
        return math.hypot(target_x - start_x, target_y - start_y)

    def _curve_control_point(
        self,
        anchor_x: float,
        anchor_y: float,
        opposite_x: float,
        opposite_y: float,
        ratio_low: float,
        ratio_high: float,
    ) -> tuple[float, float]:
        ratio = self._rand_float(ratio_low, ratio_high)
        x = anchor_x + (opposite_x - anchor_x) * ratio + self._rand_float(-26.0, 26.0)
        y = anchor_y + (opposite_y - anchor_y) * ratio + self._rand_float(-26.0, 26.0)
        return x, y

    def _chunk_text(self, text: str, minimum: int, maximum: int) -> list[str]:
        if not text:
            return []
        if len(text) <= maximum:
            return [text]
        chunks: list[str] = []
        index = 0
        while index < len(text):
            remaining = len(text) - index
            chunk_size = min(remaining, self._rand_int(max(1, minimum), max(1, maximum)))
            chunks.append(text[index : index + chunk_size])
            index += chunk_size
        return chunks

    def _pick_wrong_char(self, expected: str) -> str:
        if expected.isdigit():
            options = [char for char in "0123456789" if char != expected]
            return self._rng.choice(options)
        if expected.isalpha():
            pool = "abcdefghijklmnopqrstuvwxyz"
            options = [char for char in pool if char != expected.lower()]
            choice = self._rng.choice(options)
            return choice.upper() if expected.isupper() else choice
        options = [char for char in "aeiourstln" if char != expected]
        return self._rng.choice(options) if options else "x"

    def _scale_range(self, pair: tuple[float, float], factor: float) -> tuple[float, float]:
        low, high = pair
        scaled_low = max(0.001, low * factor)
        scaled_high = max(scaled_low, high * factor)
        return scaled_low, scaled_high

    def _scale_int_range(self, pair: tuple[int, int], factor: float) -> tuple[int, int]:
        low, high = pair
        scaled_low = max(1, int(round(low * factor)))
        scaled_high = max(scaled_low, int(round(high * factor)))
        return scaled_low, scaled_high

    def _scaled_scroll_chunks(self, speed: float) -> tuple[int, int]:
        low, high = self._config.scroll_chunks_range
        if speed >= 1.0:
            return max(2, low), max(2, high)
        return max(2, low + 1), max(2, high + 1)

    def _split_pause_segments(self, delay: float) -> list[float]:
        low, high = self._config.pause_segments_range
        segment_count = self._rand_int(max(1, low), max(1, high))
        if segment_count <= 1 or delay <= 0.015:
            return [delay]
        weights = [self._rand_float(0.65, 1.45) for _ in range(segment_count)]
        weight_total = sum(weights)
        remaining = delay
        segments: list[float] = []
        for index, weight in enumerate(weights):
            if index == segment_count - 1:
                segment = remaining
            else:
                segment = delay * (weight / weight_total)
                remaining -= segment
            segments.append(max(0.0, segment))
        return segments

    def _trace_duration(self, trace: dict[str, Any] | None) -> float:
        if not trace:
            return 0.0
        duration = trace.get("duration")
        if isinstance(duration, int | float):
            return float(duration)
        total = 0.0
        dwell = trace.get("dwell")
        if isinstance(dwell, int | float):
            total += float(dwell)
        for key in ("outward", "back"):
            child = trace.get(key)
            if isinstance(child, dict) and isinstance(child.get("duration"), int | float):
                total += float(child["duration"])
        return total

    def _viewport_height(self, *, default: float) -> float:
        page = self._page_or_none()
        viewport = getattr(page, "viewport_size", None) if page is not None else None
        if callable(viewport):
            try:
                viewport = viewport()
            except Exception:
                viewport = None
        if isinstance(viewport, dict):
            height = viewport.get("height")
            if isinstance(height, int | float) and height > 0:
                return float(height)
        return float(default)

    def _viewport_size(self) -> dict[str, float] | None:
        page = self._page_or_none()
        viewport = getattr(page, "viewport_size", None) if page is not None else None
        if callable(viewport):
            try:
                viewport = viewport()
            except Exception:
                viewport = None
        if not isinstance(viewport, dict):
            return None
        width = viewport.get("width")
        height = viewport.get("height")
        if not isinstance(width, int | float) or not isinstance(height, int | float):
            return None
        if width <= 0 or height <= 0:
            return None
        return {"width": float(width), "height": float(height)}

    def _clamp_to_viewport(
        self,
        x: float,
        y: float,
        *,
        viewport: dict[str, float] | None,
    ) -> tuple[float, float]:
        if viewport is None:
            return x, y
        margin = max(0.0, float(self._config.viewport_margin))
        return (
            self._clamp_between(float(x), margin, max(margin, viewport["width"] - margin)),
            self._clamp_between(float(y), margin, max(margin, viewport["height"] - margin)),
        )

    async def _mouse_down(self, button: str) -> None:
        mouse = self._page().mouse
        try:
            await mouse.down(button=button)
        except TypeError:
            await mouse.down()

    async def _mouse_up(self, button: str) -> None:
        mouse = self._page().mouse
        try:
            await mouse.up(button=button)
        except TypeError:
            await mouse.up()

    async def _press_key_down_up(self, key: str) -> dict[str, Any]:
        keyboard = self._page().keyboard
        parts = [part.strip() for part in key.split("+") if part.strip()]
        if not parts:
            raise ValueError("browser.press key 不能为空")
        dwell = self._rand_float(*self._config.press_dwell_range)
        if not hasattr(keyboard, "down") or not hasattr(keyboard, "up"):
            await keyboard.press(key)
            await asyncio.sleep(dwell)
            return {
                "strategy": "press",
                "dwell": dwell,
                "down_sequence": [],
                "up_sequence": [],
                "fallback": False,
            }
        pressed: list[str] = []
        try:
            for part in parts:
                await keyboard.down(part)
                pressed.append(part)
                await asyncio.sleep(self._rand_float(0.006, 0.025))
            await asyncio.sleep(dwell)
            released: list[str] = []
            for part in reversed(pressed):
                await keyboard.up(part)
                released.append(part)
                await asyncio.sleep(self._rand_float(0.005, 0.02))
            return {
                "strategy": "down_up",
                "dwell": dwell,
                "down_sequence": list(pressed),
                "up_sequence": released,
                "fallback": False,
            }
        except Exception:
            for part in reversed(pressed):
                try:
                    await keyboard.up(part)
                except Exception:
                    pass
            await keyboard.press(key)
            return {
                "strategy": "press",
                "dwell": dwell,
                "down_sequence": list(pressed),
                "up_sequence": [],
                "fallback": True,
            }

    def _sensitive_reasons(
        self,
        text: str,
        *,
        field_context: dict[str, Any] | None,
    ) -> list[str]:
        reasons: list[str] = []
        stripped = text.strip()
        if len(stripped) >= 6 and sum(char.isdigit() for char in stripped) / max(1, len(stripped)) >= 0.6:
            reasons.append("numeric_like")
        if "@" in stripped and "." in stripped:
            reasons.append("email_like")
        lowered_text = stripped.lower()
        if any(token in lowered_text for token in ("password", "token", "secret")):
            reasons.append("secret_text")
        if field_context:
            searchable = " ".join(str(value).lower() for value in field_context.values() if value)
            field_type = str(field_context.get("type") or "").strip().lower()
            autocomplete = str(field_context.get("autocomplete") or "").strip().lower()
            if field_type in {"password", "email", "tel"}:
                reasons.append(f"field_type:{field_type}")
            if field_type in {"number"} and len(stripped) >= 4:
                reasons.append("field_type:number")
            for token in (
                "password",
                "passwd",
                "pwd",
                "token",
                "secret",
                "otp",
                "one-time-code",
                "captcha",
                "verify",
                "verification",
                "code",
                "phone",
                "mobile",
                "email",
                "credit",
                "card",
            ):
                if token in searchable:
                    reasons.append(f"field_hint:{token}")
            if autocomplete in {"current-password", "new-password", "one-time-code", "cc-number", "email", "tel"}:
                reasons.append(f"autocomplete:{autocomplete}")
        return sorted(set(reasons))

    def _looks_sensitive(self, text: str) -> bool:
        return bool(self._sensitive_reasons(text, field_context=None))

    def _validate_mode(self, label: str, mode: str, allowed: set[str]) -> None:
        if mode not in allowed:
            expected = ", ".join(sorted(allowed))
            raise ValueError(f"{label} 必须是 {expected}，收到: {mode}")

    def _validate_clicks(self, clicks: int) -> None:
        if not isinstance(clicks, int) or clicks < 1 or clicks > 3:
            raise ValueError("browser.click clicks 必须是 1 到 3 的整数")

    def _validate_steps(self, steps: int | None) -> None:
        if steps is None:
            return
        if not isinstance(steps, int) or steps < 1 or steps > 360:
            raise ValueError("steps 必须是 1 到 360 的整数")

    def _validate_chunks(self, chunks: int | None) -> None:
        if chunks is None:
            return
        if not isinstance(chunks, int) or chunks < 2 or chunks > 80:
            raise ValueError("browser.scroll chunks 必须是 2 到 80 的整数")

    def _validate_range(self, label: str, pair: tuple[float, float]) -> None:
        low, high = pair
        if not math.isfinite(float(low)) or not math.isfinite(float(high)) or low < 0 or high < 0 or high < low:
            raise ValueError(f"{label} 必须是非负且递增的二元范围")

    def _validate_optional_range(self, label: str, minimum: float | None, maximum: float | None) -> None:
        for name, value in (("minimum", minimum), ("maximum", maximum)):
            if value is None:
                continue
            if not isinstance(value, int | float) or not math.isfinite(float(value)) or value < 0:
                raise ValueError(f"{label} {name} 必须是非负有限数字")
        if minimum is not None and maximum is not None and maximum < minimum:
            raise ValueError(f"{label} minimum 不能大于 maximum")

    def _validate_int_range(self, label: str, pair: tuple[int, int]) -> None:
        low, high = pair
        if low < 1 or high < low:
            raise ValueError(f"{label} 必须是从正整数开始的递增二元范围")

    def _pick_range(
        self,
        minimum: float | None,
        maximum: float | None,
        *,
        default: tuple[float, float],
    ) -> tuple[float, float]:
        low, high = default
        if minimum is not None:
            low = minimum
        if maximum is not None:
            high = maximum
        if high < low:
            low, high = high, low
        return low, high

    def _rand_float(self, minimum: float, maximum: float) -> float:
        if minimum == maximum:
            return minimum
        return self._rng.uniform(minimum, maximum)

    def _rand_int(self, minimum: int, maximum: int) -> int:
        if minimum == maximum:
            return minimum
        return self._rng.randint(minimum, maximum)

    def _clamp_between(self, value: float, minimum: float, maximum: float) -> float:
        if minimum > maximum:
            minimum, maximum = maximum, minimum
        return min(max(value, minimum), maximum)

    def _clamp_segment_point(self, value: float, start: float, target: float) -> float:
        return self._clamp_between(value, min(start, target), max(start, target))

    def _cubic_bezier(self, p0: float, p1: float, p2: float, p3: float, t: float) -> float:
        return (
            ((1 - t) ** 3) * p0
            + 3 * ((1 - t) ** 2) * t * p1
            + 3 * (1 - t) * (t**2) * p2
            + (t**3) * p3
        )

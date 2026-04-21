"""qasync compatibility guards for the packaged PyQt runtime."""

from __future__ import annotations

import asyncio
import time
from typing import Any


def _format_handle(qasync_module: Any, handle: asyncio.Handle) -> str:
    formatter = getattr(qasync_module, "_format_handle", None)
    if callable(formatter):
        return formatter(handle)
    return repr(handle)


def install_qasync_timer_compat(qasync_module: Any) -> bool:
    """Patch qasync's private timer to avoid QObject.startTimer crashes on Qt 6."""

    qtcore = getattr(qasync_module, "QtCore", None)
    original_timer = getattr(qasync_module, "_SimpleTimer", None)
    if qtcore is None or original_timer is None:
        return False
    if getattr(qasync_module, "_crawler4j_safe_timer_installed", False):
        return True

    class _Crawler4jSafeSimpleTimer(qtcore.QObject):
        def __init__(self):
            super().__init__()
            self.__callbacks: dict[int, asyncio.Handle] = {}
            self.__timers: dict[int, Any] = {}
            self.__next_timer_id = 0
            self._stopped = False
            self.__debug_enabled = False

        def add_callback(self, handle: asyncio.Handle, delay: float = 0):
            interval_ms = max(0, int(delay * 1000))
            timer_id = self.__next_timer_id
            self.__next_timer_id += 1

            timer = qtcore.QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda tid=timer_id: self._fire_timer(tid))

            self.__callbacks[timer_id] = handle
            self.__timers[timer_id] = timer
            timer.start(interval_ms)
            return handle

        def _fire_timer(self, timer_id: int) -> None:
            handle = self.__callbacks.pop(timer_id, None)
            timer = self.__timers.pop(timer_id, None)
            try:
                if timer is not None:
                    timer.stop()
                if self._stopped or handle is None:
                    return
                if handle._cancelled:
                    return
                if self.__debug_enabled:
                    loop = asyncio.get_event_loop()
                    try:
                        loop._current_handle = handle
                        t0 = time.time()
                        handle._run()
                        dt = time.time() - t0
                        if dt >= loop.slow_callback_duration:
                            qasync_module.logger.warning(
                                "Executing %s took %.3f seconds",
                                _format_handle(qasync_module, handle),
                                dt,
                            )
                    finally:
                        loop._current_handle = None
                else:
                    handle._run()
            finally:
                if timer is not None:
                    timer.deleteLater()

        def stop(self) -> None:
            self._stopped = True
            for timer in list(self.__timers.values()):
                timer.stop()
                timer.deleteLater()
            self.__timers.clear()
            self.__callbacks.clear()

        def set_debug(self, enabled: bool) -> None:
            self.__debug_enabled = enabled

    qasync_module._SimpleTimer = _Crawler4jSafeSimpleTimer
    qasync_module._crawler4j_safe_timer_installed = True
    return True

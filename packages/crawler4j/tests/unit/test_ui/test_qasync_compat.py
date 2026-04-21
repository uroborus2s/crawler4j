from __future__ import annotations

import asyncio
from types import SimpleNamespace

from PyQt6.QtCore import QObject

from src.ui.qasync_compat import install_qasync_timer_compat


def _build_fake_qasync():
    from PyQt6 import QtCore

    class _OriginalTimer(QObject):
        pass

    return SimpleNamespace(
        QtCore=QtCore,
        _SimpleTimer=_OriginalTimer,
        logger=SimpleNamespace(warning=lambda *args, **kwargs: None),
    )


def test_install_qasync_timer_compat_replaces_private_timer_class():
    fake_qasync = _build_fake_qasync()
    original_timer = fake_qasync._SimpleTimer

    installed = install_qasync_timer_compat(fake_qasync)

    assert installed is True
    assert fake_qasync._SimpleTimer is not original_timer
    assert fake_qasync._crawler4j_safe_timer_installed is True


def test_safe_qasync_timer_runs_callbacks_without_qobject_starttimer(qtbot):
    fake_qasync = _build_fake_qasync()
    install_qasync_timer_compat(fake_qasync)
    timer = fake_qasync._SimpleTimer()
    loop = asyncio.new_event_loop()
    observed: list[str] = []

    try:
        handle = asyncio.Handle(lambda: observed.append("ran"), (), loop)
        timer.add_callback(handle, 0.01)
        qtbot.waitUntil(lambda: observed == ["ran"], timeout=1000)
    finally:
        timer.stop()
        loop.close()


def test_safe_qasync_timer_stop_cancels_pending_callbacks(qtbot):
    fake_qasync = _build_fake_qasync()
    install_qasync_timer_compat(fake_qasync)
    timer = fake_qasync._SimpleTimer()
    loop = asyncio.new_event_loop()
    observed: list[str] = []

    try:
        handle = asyncio.Handle(lambda: observed.append("ran"), (), loop)
        timer.add_callback(handle, 0.05)
        timer.stop()
        qtbot.wait(120)
        assert observed == []
    finally:
        loop.close()

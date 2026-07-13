import asyncio
import weakref
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import src.core.rem.cookie_service as cookie_service_module
from src.core.rem.cookie_service import EnvCookieService, cookie_sets_match, normalize_expected_cookies
from src.core.rem.handle import BrowserHandle
from src.core.rem.manager import EnvironmentManager
from src.core.rem.models import Environment, EnvKind, EnvStatus


EXPECTED_COOKIE = {
    "name": "cticket",
    "value": "cticket-new",
    "domain": ".ctrip.com",
    "path": "/",
    "expires": 1_893_456_000.5,
    "secure": True,
    "httpOnly": True,
}
EXTRA_COOKIE = {
    "name": "other",
    "value": "must-be-deleted",
    "domain": ".ctrip.com",
    "path": "/",
    "expires": 1_893_456_100.0,
    "secure": False,
    "httpOnly": False,
}


def _handle(cookies: list[dict]) -> BrowserHandle:
    handle = BrowserHandle(browser_id="101")
    handle._page = SimpleNamespace(url="about:blank")
    handle._context = SimpleNamespace(cookies=AsyncMock(return_value=[dict(item) for item in cookies]))
    return handle


class _FakeProvider:
    name = "virtualbrowser"

    def __init__(self, persisted: list[dict], calls: list[str], *, ignore_replace: bool = False):
        self.persisted = [dict(item) for item in persisted]
        self.calls = calls
        self.ignore_replace = ignore_replace
        self.active_reads = 0
        self.max_active_reads = 0
        self.get_error: Exception | None = None
        self.get_error_after = 1
        self.get_calls = 0
        self.replace_error: Exception | None = None

    async def get_persisted_cookies(self, env: Environment) -> list[dict]:
        del env
        self.calls.append("get_persisted")
        self.get_calls += 1
        if self.get_error is not None and self.get_calls >= self.get_error_after:
            raise self.get_error
        self.active_reads += 1
        self.max_active_reads = max(self.max_active_reads, self.active_reads)
        await asyncio.sleep(0)
        self.active_reads -= 1
        return [dict(item) for item in self.persisted]

    async def replace_persisted_cookies(self, env: Environment, cookies: list[dict]) -> None:
        del env
        self.calls.append("replace_persisted")
        if self.replace_error is not None:
            raise self.replace_error
        if not self.ignore_replace:
            self.persisted = [dict(item) for item in cookies]


class _FakeManager:
    def __init__(self, env: Environment, calls: list[str], expected: list[dict]):
        self.env = env
        self.calls = calls
        self.expected = expected
        self.lifecycle_lock = asyncio.Lock()
        self.stop_success = True
        self.start_success = True
        self.runtime_after = expected

    def get_env_lifecycle_lock(self, env_id: int) -> asyncio.Lock:
        assert env_id == self.env.id
        return self.lifecycle_lock

    async def get_env(self, env_id: int) -> Environment | None:
        return self.env if env_id == self.env.id else None

    async def _stop_env_unlocked(self, env_id: int) -> bool:
        assert env_id == self.env.id
        self.calls.append("stop")
        if not self.stop_success:
            return False
        self.env.status = EnvStatus.READY
        self.env.handle = BrowserHandle(browser_id="101")
        return True

    async def _start_env_unlocked(self, env_id: int) -> bool:
        assert env_id == self.env.id
        self.calls.append("start")
        if not self.start_success:
            return False
        self.env.status = EnvStatus.RUNNING
        self.env.handle = _handle(self.runtime_after)
        return True

    async def external_stop(self) -> None:
        async with self.lifecycle_lock:
            self.calls.append("external_stop")


def _service(
    *,
    persisted: list[dict],
    runtime: list[dict],
    expected: list[dict] | None = None,
    ignore_replace: bool = False,
    status: EnvStatus = EnvStatus.RUNNING,
) -> tuple[EnvCookieService, _FakeProvider, _FakeManager, list[str]]:
    calls: list[str] = []
    target = expected if expected is not None else [EXPECTED_COOKIE]
    env = Environment(
        id=7,
        name="cookie-env",
        kind=EnvKind.BROWSER,
        provider="virtualbrowser",
        status=status,
        handle=_handle(runtime),
    )
    provider = _FakeProvider(persisted, calls, ignore_replace=ignore_replace)
    manager = _FakeManager(env, calls, target)
    service = EnvCookieService(manager, provider_resolver=lambda _name: provider)
    return service, provider, manager, calls


def test_cookie_sets_match_requires_complete_set_and_allows_empty_clear():
    expected = normalize_expected_cookies([EXPECTED_COOKIE])

    assert cookie_sets_match(expected, [EXPECTED_COOKIE]) is True
    assert cookie_sets_match(expected, [EXPECTED_COOKIE, EXTRA_COOKIE]) is False
    assert cookie_sets_match([], []) is True
    assert cookie_sets_match([], [EXTRA_COOKIE]) is False


def test_cookie_sets_match_compares_expiry_strictly():
    expected = normalize_expected_cookies([EXPECTED_COOKIE])

    assert cookie_sets_match(expected, [{**EXPECTED_COOKIE, "expires": EXPECTED_COOKIE["expires"] + 0.1}]) is False
    assert cookie_sets_match(expected, [{**EXPECTED_COOKIE, "expires": EXPECTED_COOKIE["expires"] + 1.0}]) is False


@pytest.mark.asyncio
async def test_ensure_replaces_complete_set_removes_omitted_cookie_and_restarts():
    service, provider, manager, calls = _service(
        persisted=[{**EXPECTED_COOKIE, "value": "cticket-old"}, EXTRA_COOKIE],
        runtime=[{**EXPECTED_COOKIE, "value": "cticket-old"}, EXTRA_COOKIE],
    )

    result = await service.ensure(
        env_id=7,
        cookies=[EXPECTED_COOKIE],
        reload="restart_if_changed",
        verify="runtime",
    )

    assert result.as_dict() == {
        "persisted": True,
        "restarted": True,
        "browser_ready": True,
        "runtime_matched": True,
    }
    assert provider.persisted == [EXPECTED_COOKIE]
    assert manager.env.handle is not None
    assert calls == [
        "get_persisted",
        "replace_persisted",
        "get_persisted",
        "stop",
        "start",
    ]


@pytest.mark.asyncio
async def test_ensure_is_idempotent_when_persisted_and_runtime_sets_match():
    service, _provider, _manager, calls = _service(
        persisted=[EXPECTED_COOKIE],
        runtime=[EXPECTED_COOKIE],
    )

    result = await service.ensure(
        env_id=7,
        cookies=[EXPECTED_COOKIE],
        reload="restart_if_changed",
        verify="runtime",
    )

    assert result.restarted is False
    assert result.runtime_matched is True
    assert calls == ["get_persisted"]


@pytest.mark.asyncio
async def test_ensure_stops_busy_open_environment_before_starting_again():
    service, _provider, _manager, calls = _service(
        persisted=[EXPECTED_COOKIE],
        runtime=[],
        status=EnvStatus.BUSY,
    )

    result = await service.ensure(
        env_id=7,
        cookies=[EXPECTED_COOKIE],
        reload="restart_if_changed",
        verify="runtime",
    )

    assert result.restarted is True
    assert calls == ["get_persisted", "stop", "start"]


@pytest.mark.asyncio
async def test_ensure_empty_list_clears_all_cookies_and_restarts():
    service, provider, _manager, calls = _service(
        persisted=[EXTRA_COOKIE],
        runtime=[EXTRA_COOKIE],
        expected=[],
    )

    result = await service.ensure(
        env_id=7,
        cookies=[],
        reload="restart_if_changed",
        verify="runtime",
    )

    assert result.runtime_matched is True
    assert result.restarted is True
    assert provider.persisted == []
    assert calls == ["get_persisted", "replace_persisted", "get_persisted", "stop", "start"]


@pytest.mark.asyncio
async def test_ensure_fails_closed_when_stop_or_start_fails():
    service, _provider, manager, _calls = _service(
        persisted=[EXTRA_COOKIE],
        runtime=[EXTRA_COOKIE],
    )
    manager.stop_success = False

    with pytest.raises(RuntimeError, match="停止浏览器失败"):
        await service.ensure(7, [EXPECTED_COOKIE], reload="restart_if_changed", verify="runtime")

    service, _provider, manager, _calls = _service(
        persisted=[EXTRA_COOKIE],
        runtime=[EXTRA_COOKIE],
    )
    manager.start_success = False

    with pytest.raises(RuntimeError, match="启动浏览器失败"):
        await service.ensure(7, [EXPECTED_COOKIE], reload="restart_if_changed", verify="runtime")


@pytest.mark.asyncio
async def test_ensure_fails_closed_when_restarted_runtime_does_not_match():
    service, _provider, manager, _calls = _service(
        persisted=[EXTRA_COOKIE],
        runtime=[EXTRA_COOKIE],
    )
    manager.runtime_after = [EXTRA_COOKIE]

    with pytest.raises(RuntimeError, match="运行态 Cookie 校验失败"):
        await service.ensure(7, [EXPECTED_COOKIE], reload="restart_if_changed", verify="runtime")


@pytest.mark.asyncio
async def test_ensure_holds_shared_lifecycle_lock_through_ready_callback():
    service, _provider, manager, calls = _service(
        persisted=[EXPECTED_COOKIE],
        runtime=[EXPECTED_COOKIE],
    )
    callback_entered = asyncio.Event()
    release_callback = asyncio.Event()

    async def on_ready(_env, _result) -> None:
        calls.append("rebind")
        callback_entered.set()
        await release_callback.wait()

    ensure_task = asyncio.create_task(
        service.ensure(
            7,
            [EXPECTED_COOKIE],
            reload="restart_if_changed",
            verify="runtime",
            on_ready=on_ready,
        )
    )
    await callback_entered.wait()
    external_task = asyncio.create_task(manager.external_stop())
    await asyncio.sleep(0)

    assert "external_stop" not in calls
    release_callback.set()
    await ensure_task
    await external_task
    assert calls[-2:] == ["rebind", "external_stop"]


@pytest.mark.asyncio
async def test_ensure_cancellation_releases_shared_lifecycle_lock():
    service, _provider, manager, _calls = _service(
        persisted=[EXPECTED_COOKIE],
        runtime=[EXPECTED_COOKIE],
    )
    callback_entered = asyncio.Event()
    never_release = asyncio.Event()

    async def on_ready(_env, _result) -> None:
        callback_entered.set()
        await never_release.wait()

    task = asyncio.create_task(
        service.ensure(
            7,
            [EXPECTED_COOKIE],
            reload="restart_if_changed",
            verify="runtime",
            on_ready=on_ready,
        )
    )
    await callback_entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert manager.lifecycle_lock.locked() is False
    result = await service.ensure(7, [EXPECTED_COOKIE], reload="restart_if_changed", verify="runtime")
    assert result.runtime_matched is True


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["get", "replace"])
async def test_ensure_hides_provider_api_and_sensitive_error_details(operation):
    service, provider, _manager, _calls = _service(
        persisted=[EXTRA_COOKIE],
        runtime=[EXTRA_COOKIE],
    )
    secret_error = RuntimeError("VirtualBrowser updateCookie api-key-secret cookie-value-secret")
    if operation == "get":
        provider.get_error = secret_error
    else:
        provider.replace_error = secret_error

    with pytest.raises(RuntimeError) as exc_info:
        await service.ensure(7, [EXPECTED_COOKIE], reload="restart_if_changed", verify="runtime")

    message = str(exc_info.value)
    assert "VirtualBrowser" not in message
    assert "updateCookie" not in message
    assert "api-key-secret" not in message
    assert "cookie-value-secret" not in message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("operation", "expected_stage"),
    [
        ("get", "read_persisted"),
        ("replace", "replace_persisted"),
        ("verify", "verify_persisted"),
    ],
)
async def test_ensure_logs_redacted_provider_failure_diagnostics(monkeypatch, operation, expected_stage):
    service, provider, _manager, _calls = _service(
        persisted=[EXTRA_COOKIE],
        runtime=[EXTRA_COOKIE],
    )
    provider_error = RuntimeError(
        'HTTP request failed api-key=api-key-secret payload={"value":"cookie-value-secret"}'
    )
    if operation == "get":
        provider.get_error = provider_error
    elif operation == "replace":
        provider.replace_error = provider_error
    else:
        provider.get_error = provider_error
        provider.get_error_after = 2
    log_error = Mock()
    monkeypatch.setattr(cookie_service_module.logger, "error", log_error)

    with pytest.raises(RuntimeError):
        await service.ensure(7, [EXPECTED_COOKIE], reload="restart_if_changed", verify="runtime")

    log_error.assert_called_once()
    diagnostic = log_error.call_args.args[0]
    assert "[CookieEnsure]" in diagnostic
    assert f"stage={expected_stage}" in diagnostic
    assert "env_id=7" in diagnostic
    assert "provider=virtualbrowser" in diagnostic
    assert "browser_id=101" in diagnostic
    assert "error_type=RuntimeError" in diagnostic
    assert "api-key-secret" not in diagnostic
    assert "cookie-value-secret" not in diagnostic
    assert "<redacted>" in diagnostic


@pytest.mark.asyncio
async def test_ensure_raises_when_full_replace_does_not_persist():
    service, _provider, _manager, calls = _service(
        persisted=[EXTRA_COOKIE],
        runtime=[EXTRA_COOKIE],
        ignore_replace=True,
    )

    with pytest.raises(RuntimeError, match="Cookie 持久化校验失败") as exc_info:
        await service.ensure(
            env_id=7,
            cookies=[EXPECTED_COOKIE],
            reload="restart_if_changed",
            verify="runtime",
        )

    assert EXPECTED_COOKIE["value"] not in str(exc_info.value)
    assert calls == ["get_persisted", "replace_persisted", "get_persisted"]


@pytest.mark.asyncio
async def test_ensure_serializes_calls_for_same_environment():
    service, provider, _manager, _calls = _service(
        persisted=[EXPECTED_COOKIE],
        runtime=[EXPECTED_COOKIE],
    )

    await asyncio.gather(
        service.ensure(7, [EXPECTED_COOKIE], reload="restart_if_changed", verify="runtime"),
        service.ensure(7, [EXPECTED_COOKIE], reload="restart_if_changed", verify="runtime"),
    )

    assert provider.max_active_reads == 1


def test_normalize_expected_cookies_rejects_duplicate_identity_without_exposing_values():
    with pytest.raises(ValueError, match="重复 Cookie") as exc_info:
        normalize_expected_cookies([EXPECTED_COOKIE, {**EXPECTED_COOKIE, "value": "do-not-log"}])

    assert "do-not-log" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_environment_manager_public_lifecycle_writes_share_same_environment_lock():
    manager = EnvironmentManager.__new__(EnvironmentManager)
    manager._env_lifecycle_locks = weakref.WeakValueDictionary()
    manager._start_env_unlocked = AsyncMock(return_value=True)
    manager._stop_env_unlocked = AsyncMock(return_value=True)
    manager._pause_env_unlocked = AsyncMock(return_value=True)
    manager._resume_env_unlocked = AsyncMock(return_value=True)
    lock = manager.get_env_lifecycle_lock(7)

    async with lock:
        start_task = asyncio.create_task(manager.start_env("7"))
        stop_task = asyncio.create_task(manager.stop_env(7))
        pause_task = asyncio.create_task(manager.pause_env("7"))
        resume_task = asyncio.create_task(manager.resume_env(7))
        await asyncio.sleep(0)
        manager._start_env_unlocked.assert_not_awaited()
        manager._stop_env_unlocked.assert_not_awaited()
        manager._pause_env_unlocked.assert_not_awaited()
        manager._resume_env_unlocked.assert_not_awaited()

    assert await start_task is True
    assert await stop_task is True
    assert await pause_task is True
    assert await resume_task is True
    manager._start_env_unlocked.assert_awaited_once_with("7")
    manager._stop_env_unlocked.assert_awaited_once_with(7)
    manager._pause_env_unlocked.assert_awaited_once_with("7")
    manager._resume_env_unlocked.assert_awaited_once_with(7)

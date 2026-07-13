"""供应商无关的环境 Cookie 全量替换与运行态校验。"""

from __future__ import annotations

import inspect
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from src.core.rem.models import EnvStatus
from src.core.rem.provider import get_provider

_REQUIRED_COOKIE_FIELDS = {
    "name",
    "value",
    "domain",
    "path",
    "expires",
    "secure",
    "httpOnly",
}
_OPTIONAL_COOKIE_FIELDS = {"sameSite"}
_ALLOWED_COOKIE_FIELDS = _REQUIRED_COOKIE_FIELDS | _OPTIONAL_COOKIE_FIELDS


@dataclass(frozen=True)
class CookieEnsureResult:
    persisted: bool
    restarted: bool
    browser_ready: bool
    runtime_matched: bool

    def as_dict(self) -> dict[str, bool]:
        return {
            "persisted": self.persisted,
            "restarted": self.restarted,
            "browser_ready": self.browser_ready,
            "runtime_matched": self.runtime_matched,
        }


def _cookie_identity(cookie: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(cookie.get("name") or ""),
        str(cookie.get("domain") or "").lower(),
        str(cookie.get("path") or "/"),
    )


def normalize_expected_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """校验并规范化模块传入的完整目标 Cookie 集合。"""
    if not isinstance(cookies, list):
        raise ValueError("cookies 必须是列表")

    normalized: list[dict[str, Any]] = []
    identities: set[tuple[str, str, str]] = set()
    for index, item in enumerate(cookies):
        if not isinstance(item, Mapping):
            raise ValueError(f"cookies[{index}] 必须是对象")
        missing = sorted(_REQUIRED_COOKIE_FIELDS - item.keys())
        if missing:
            raise ValueError(f"cookies[{index}] 缺少字段: {', '.join(missing)}")
        unknown = sorted(item.keys() - _ALLOWED_COOKIE_FIELDS)
        if unknown:
            raise ValueError(f"cookies[{index}] 包含未知字段: {', '.join(unknown)}")

        name = item["name"]
        value = item["value"]
        domain = item["domain"]
        path = item["path"]
        expires = item["expires"]
        secure = item["secure"]
        http_only = item["httpOnly"]
        if not isinstance(name, str) or not name:
            raise ValueError(f"cookies[{index}].name 必须是非空字符串")
        if not isinstance(value, str):
            raise ValueError(f"cookies[{index}].value 必须是字符串")
        if not isinstance(domain, str) or not domain:
            raise ValueError(f"cookies[{index}].domain 必须是非空字符串")
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError(f"cookies[{index}].path 必须以 / 开头")
        if isinstance(expires, bool) or not isinstance(expires, (int, float)):
            raise ValueError(f"cookies[{index}].expires 必须是 Unix seconds 数值")
        expires_value = float(expires)
        if not math.isfinite(expires_value):
            raise ValueError(f"cookies[{index}].expires 必须是有限数值")
        if not isinstance(secure, bool):
            raise ValueError(f"cookies[{index}].secure 必须是布尔值")
        if not isinstance(http_only, bool):
            raise ValueError(f"cookies[{index}].httpOnly 必须是布尔值")

        cookie = {
            "name": name,
            "value": value,
            "domain": domain.lower(),
            "path": path,
            "expires": expires_value,
            "secure": secure,
            "httpOnly": http_only,
        }
        if "sameSite" in item:
            same_site = item["sameSite"]
            if not isinstance(same_site, str) or same_site.lower() not in {"strict", "lax", "none"}:
                raise ValueError(f"cookies[{index}].sameSite 必须是 Strict、Lax 或 None")
            cookie["sameSite"] = same_site.lower()

        identity = _cookie_identity(cookie)
        if identity in identities:
            raise ValueError(f"cookies[{index}] 存在重复 Cookie 标识")
        identities.add(identity)
        normalized.append(cookie)
    return normalized


def cookie_sets_match(expected: list[dict[str, Any]], actual: list[dict[str, Any]]) -> bool:
    """比较完整集合；实际集合存在任何额外 Cookie 都视为不匹配。"""
    if not isinstance(actual, list) or len(actual) != len(expected):
        return False

    actual_by_identity: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for item in actual:
        if not isinstance(item, Mapping):
            return False
        identity = _cookie_identity(item)
        if identity in actual_by_identity:
            return False
        actual_by_identity[identity] = item

    for target in expected:
        current = actual_by_identity.get(_cookie_identity(target))
        if current is None or current.get("value") != target["value"]:
            return False
        current_expires = current.get("expires", current.get("expirationDate"))
        try:
            if float(current_expires) != float(target["expires"]):
                return False
        except (TypeError, ValueError):
            return False
        if current.get("secure") is not target["secure"]:
            return False
        if current.get("httpOnly") is not target["httpOnly"]:
            return False
        if "sameSite" in target:
            if str(current.get("sameSite") or "").lower() != target["sameSite"]:
                return False
    return True


class EnvCookieService:
    """按环境串行执行 Cookie 全量替换、重启和运行态校验。"""

    def __init__(
        self,
        manager: Any,
        *,
        provider_resolver: Callable[[str], Any | None] = get_provider,
    ) -> None:
        self._manager = manager
        self._provider_resolver = provider_resolver

    @staticmethod
    async def _runtime_cookies(env: Any) -> list[dict[str, Any]] | None:
        handle = getattr(env, "handle", None)
        context = getattr(handle, "context", None)
        if context is None:
            return None
        try:
            cookies = await context.cookies()
        except Exception as exc:
            raise RuntimeError("读取浏览器运行态 Cookie 失败") from exc
        return cookies if isinstance(cookies, list) else None

    @staticmethod
    def _browser_ready(env: Any) -> bool:
        handle = getattr(env, "handle", None)
        return bool(
            handle and getattr(handle, "page", None) is not None and getattr(handle, "context", None) is not None
        )

    async def ensure(
        self,
        env_id: int,
        cookies: list[dict[str, Any]],
        *,
        reload: str,
        verify: str,
        on_ready: Callable[[Any, CookieEnsureResult], Any] | None = None,
    ) -> CookieEnsureResult:
        if isinstance(env_id, bool) or not isinstance(env_id, int) or env_id <= 0:
            raise ValueError("env_id 必须是正整数")
        if reload != "restart_if_changed":
            raise ValueError("reload 只支持 restart_if_changed")
        if verify != "runtime":
            raise ValueError("verify 只支持 runtime")
        expected = normalize_expected_cookies(cookies)

        lifecycle_lock = self._manager.get_env_lifecycle_lock(env_id)
        async with lifecycle_lock:
            env = await self._manager.get_env(env_id)
            if env is None:
                raise RuntimeError(f"环境不存在: {env_id}")
            provider = self._provider_resolver(str(getattr(env, "provider", "") or ""))
            get_persisted = getattr(provider, "get_persisted_cookies", None)
            replace_persisted = getattr(provider, "replace_persisted_cookies", None)
            if not callable(get_persisted) or not callable(replace_persisted):
                raise RuntimeError("当前环境不支持持久化 Cookie")

            try:
                persisted_before = await get_persisted(env)
            except Exception:
                raise RuntimeError("读取环境持久化 Cookie 失败") from None
            persisted_matched = cookie_sets_match(expected, persisted_before)
            runtime_before = await self._runtime_cookies(env)
            runtime_matched = runtime_before is not None and cookie_sets_match(expected, runtime_before)

            if not persisted_matched:
                try:
                    await replace_persisted(env, expected)
                except Exception:
                    raise RuntimeError("全量替换环境持久化 Cookie 失败") from None
                try:
                    persisted_after = await get_persisted(env)
                except Exception:
                    raise RuntimeError("复核环境持久化 Cookie 失败") from None
                if not cookie_sets_match(expected, persisted_after):
                    raise RuntimeError("Cookie 持久化校验失败")

            restarted = False
            if not persisted_matched or not runtime_matched:
                was_running = getattr(env, "status", None) in {EnvStatus.BUSY, EnvStatus.RUNNING}
                if was_running:
                    if not await self._manager._stop_env_unlocked(env_id):
                        raise RuntimeError("Cookie 生效前停止浏览器失败")
                    restarted = True
                if not await self._manager._start_env_unlocked(env_id):
                    raise RuntimeError("Cookie 生效后启动浏览器失败")
                env = await self._manager.get_env(env_id)
                if env is None:
                    raise RuntimeError(f"重启后环境不存在: {env_id}")
                runtime_after = await self._runtime_cookies(env)
            else:
                runtime_after = runtime_before

            browser_ready = self._browser_ready(env)
            if not browser_ready:
                raise RuntimeError("浏览器重连后 Page/Context 不可用")
            if runtime_after is None or not cookie_sets_match(expected, runtime_after):
                raise RuntimeError("浏览器运行态 Cookie 校验失败")

            result = CookieEnsureResult(
                persisted=True,
                restarted=restarted,
                browser_ready=True,
                runtime_matched=True,
            )
            if on_ready is not None:
                callback_result = on_ready(env, result)
                if inspect.isawaitable(callback_result):
                    await callback_result
            return result

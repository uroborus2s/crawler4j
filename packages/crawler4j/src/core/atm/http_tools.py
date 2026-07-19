"""宿主管理的 HTTP 请求工具。"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

import httpx


_HTTP_METHOD_RE = re.compile(r"^[A-Z]+$")
_HTTP_SCHEMES = frozenset({"http", "https"})


def _normalize_method(method: str) -> str:
    normalized = str(method or "").strip().upper()
    if not _HTTP_METHOD_RE.fullmatch(normalized):
        raise ValueError("method 必须是非空 HTTP 方法")
    return normalized


def _validate_http_url(url: str, *, field_name: str) -> str:
    normalized = str(url or "").strip()
    parsed = urlsplit(normalized)
    if parsed.scheme.lower() not in _HTTP_SCHEMES or not parsed.hostname:
        raise ValueError(f"{field_name} 必须是完整的 HTTP 或 HTTPS URL")
    return normalized


def _normalize_headers(
    headers: Mapping[str, str] | Sequence[tuple[str, str]] | None,
) -> list[tuple[str, str]] | None:
    if headers is None:
        return None
    items = headers.items() if isinstance(headers, Mapping) else headers
    normalized: list[tuple[str, str]] = []
    for index, item in enumerate(items):
        if not isinstance(item, (tuple, list)) or len(item) != 2:
            raise ValueError(f"headers[{index}] 必须是二元键值对")
        name, value = item
        normalized.append((str(name), str(value)))
    return normalized


def _validate_bool(value: bool, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} 必须是 bool")
    return value


class CoreHttpTools:
    """只由 Core 实现、通过 ``ctx.tools`` 暴露的 HTTP 能力。"""

    async def request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str] | Sequence[tuple[str, str]] | None = None,
        content: bytes | str | None = None,
        proxy_url: str | None = None,
        http2: bool = False,
        require_http2: bool = False,
        follow_redirects: bool = False,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        """发送一次请求并返回不泄漏第三方类型的结构化响应。"""

        normalized_method = _normalize_method(method)
        normalized_url = _validate_http_url(url, field_name="url")
        normalized_proxy = (
            _validate_http_url(proxy_url, field_name="proxy_url") if proxy_url is not None else None
        )
        normalized_headers = _normalize_headers(headers)
        normalized_http2 = _validate_bool(http2, field_name="http2")
        normalized_require_http2 = _validate_bool(require_http2, field_name="require_http2")
        normalized_follow_redirects = _validate_bool(
            follow_redirects,
            field_name="follow_redirects",
        )
        if normalized_require_http2 and not normalized_http2:
            raise ValueError("require_http2=True 时必须同时传入 http2=True")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError("timeout 必须是大于 0 的秒数")
        if content is not None and not isinstance(content, (bytes, str)):
            raise ValueError("content 必须是 bytes、str 或 None")

        request = httpx.Request(
            method=normalized_method,
            url=normalized_url,
            headers=normalized_headers,
            content=content,
        )
        try:
            async with httpx.AsyncClient(
                http2=normalized_http2,
                proxy=normalized_proxy,
                trust_env=False,
                timeout=float(timeout),
            ) as client:
                response = await client.send(
                    request,
                    follow_redirects=normalized_follow_redirects,
                )
                response_content = await response.aread()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"HOST_HTTP_REQUEST_FAILED:{type(exc).__name__}") from None

        if normalized_require_http2 and response.http_version != "HTTP/2":
            raise RuntimeError("HOST_HTTP2_NOT_NEGOTIATED")

        return {
            "status_code": int(response.status_code),
            "headers": list(response.headers.multi_items()),
            "content": response_content,
            "http_version": str(response.http_version),
        }


__all__ = ["CoreHttpTools"]

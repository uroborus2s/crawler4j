from __future__ import annotations

from typing import Any

import brotli
import httpx
import pytest

from src.core.atm.runtime_capabilities import (
    RUNTIME_SURFACE_ENV_CLEANUP_CANDIDATES,
    RUNTIME_SURFACE_ENV_CANDIDATES,
    RUNTIME_SURFACE_HOSTED_UI_ACTION,
    RUNTIME_SURFACE_HOSTED_UI_DECLARE,
    RUNTIME_SURFACE_HOSTED_UI_READONLY,
    build_runtime_capabilities,
)


class _FakeResponse:
    def __init__(self, *, http_version: str = "HTTP/2") -> None:
        self.status_code = 200
        self.http_version = http_version
        self.headers = httpx.Headers(
            [("content-type", "application/json"), ("set-cookie", "a=1"), ("set-cookie", "b=2")]
        )

    async def aread(self) -> bytes:
        return b'{"ok":true}'


class _FakeAsyncClient:
    calls: list[dict[str, Any]] = []
    response = _FakeResponse()

    def __init__(self, **kwargs: Any) -> None:
        self.client_kwargs = kwargs

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, *_args: Any) -> None:
        return None

    async def send(self, request: httpx.Request, *, follow_redirects: bool) -> _FakeResponse:
        self.calls.append(
            {
                "client": self.client_kwargs,
                "request": {
                    "method": request.method,
                    "url": str(request.url),
                    "headers": list(request.headers.multi_items()),
                    "content": request.content,
                    "follow_redirects": follow_redirects,
                },
            }
        )
        return self.response


@pytest.fixture(autouse=True)
def _reset_fake_client() -> None:
    _FakeAsyncClient.calls = []
    _FakeAsyncClient.response = _FakeResponse()


@pytest.mark.asyncio
async def test_http_request_is_a_host_tool_and_preserves_http2_request_contract(monkeypatch):
    monkeypatch.setattr("src.core.atm.http_tools.httpx.AsyncClient", _FakeAsyncClient)
    caps = build_runtime_capabilities("demo_module")

    result = await caps.tools.call(
        "http.request",
        method="POST",
        url="https://m.ctrip.com/restapi/soa2/28000/json/minihotelroomlist",
        headers=[
            ("host", "m.ctrip.com"),
            ("content-length", "2"),
            ("x-test", "one"),
            ("x-test", "two"),
        ],
        content=b"{}",
        proxy_url="http://127.0.0.1:8080",
        http2=True,
        require_http2=True,
        follow_redirects=False,
        timeout=30.0,
    )

    assert caps.tools.has_tool("http.request") is True
    assert {spec.name: spec.is_async for spec in caps.tools.list_tools()}["http.request"] is True
    assert result == {
        "status_code": 200,
        "headers": [
            ("content-type", "application/json"),
            ("set-cookie", "a=1"),
            ("set-cookie", "b=2"),
        ],
        "content": b'{"ok":true}',
        "http_version": "HTTP/2",
    }
    assert _FakeAsyncClient.calls == [
        {
            "client": {
                "http2": True,
                "proxy": "http://127.0.0.1:8080",
                "trust_env": False,
                "timeout": 30.0,
            },
            "request": {
                "method": "POST",
                "url": "https://m.ctrip.com/restapi/soa2/28000/json/minihotelroomlist",
                "headers": [
                    ("host", "m.ctrip.com"),
                    ("content-length", "2"),
                    ("x-test", "one"),
                    ("x-test", "two"),
                ],
                "content": b"{}",
                "follow_redirects": False,
            },
        }
    ]


@pytest.mark.asyncio
async def test_http_request_rejects_protocol_downgrade(monkeypatch):
    monkeypatch.setattr("src.core.atm.http_tools.httpx.AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.response = _FakeResponse(http_version="HTTP/1.1")
    caps = build_runtime_capabilities("demo_module")

    with pytest.raises(RuntimeError, match="HOST_HTTP2_NOT_NEGOTIATED"):
        await caps.tools.call(
            "http.request",
            method="GET",
            url="https://example.com/",
            http2=True,
            require_http2=True,
        )


@pytest.mark.asyncio
async def test_http_request_decodes_brotli_response(monkeypatch):
    real_async_client = httpx.AsyncClient
    compressed = brotli.compress(b'{"encoding":"br"}')

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"content-encoding": "br"},
            content=compressed,
        )

    def client_factory(**kwargs: Any) -> httpx.AsyncClient:
        return real_async_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr("src.core.atm.http_tools.httpx.AsyncClient", client_factory)
    caps = build_runtime_capabilities("demo_module")

    result = await caps.tools.call(
        "http.request",
        method="GET",
        url="https://example.com/compressed",
    )

    assert result["content"] == b'{"encoding":"br"}'


@pytest.mark.parametrize(
    "surface",
    [
        RUNTIME_SURFACE_HOSTED_UI_DECLARE,
        RUNTIME_SURFACE_HOSTED_UI_READONLY,
        RUNTIME_SURFACE_HOSTED_UI_ACTION,
        RUNTIME_SURFACE_ENV_CANDIDATES,
        RUNTIME_SURFACE_ENV_CLEANUP_CANDIDATES,
    ],
)
def test_http_request_is_only_available_on_full_runtime_surface(surface):
    caps = build_runtime_capabilities("demo_module", surface=surface)

    assert caps.tools.has_tool("http.request") is False
    with pytest.raises(KeyError, match=r"Unknown core tool: http.request"):
        caps.tools.call("http.request", method="GET", url="https://example.com/")


@pytest.mark.asyncio
async def test_http_request_rejects_invalid_or_ambiguous_input():
    caps = build_runtime_capabilities("demo_module")

    with pytest.raises(ValueError, match="http2=True"):
        await caps.tools.call(
            "http.request",
            method="GET",
            url="https://example.com/",
            require_http2=True,
        )

    with pytest.raises(ValueError, match="HTTP 或 HTTPS"):
        await caps.tools.call(
            "http.request",
            method="GET",
            url="file:///tmp/private",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("parameter", "value"),
    [("http2", 1), ("require_http2", "yes"), ("follow_redirects", 1)],
)
async def test_http_request_requires_boolean_flags(parameter, value):
    caps = build_runtime_capabilities("demo_module")

    with pytest.raises(ValueError, match=f"{parameter} 必须是 bool"):
        await caps.tools.call(
            "http.request",
            method="GET",
            url="https://example.com/",
            **{parameter: value},
        )

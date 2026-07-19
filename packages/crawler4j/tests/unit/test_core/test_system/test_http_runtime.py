from __future__ import annotations

import pytest

from src.core.system.http_runtime import verify_host_http_runtime


def test_host_runtime_can_construct_http2_client_with_brotli() -> None:
    result = verify_host_http_runtime()

    assert set(result) == {"httpx", "h2", "hpack", "hyperframe", "brotli", "http2_client"}
    assert all(result[name] for name in ("httpx", "h2", "hpack", "hyperframe", "brotli"))
    assert result["http2_client"] == "ok"


def test_host_runtime_does_not_hide_http2_initialization_failure(monkeypatch) -> None:
    from src.core.system import http_runtime

    class BrokenClient:
        def __init__(self, *, http2: bool) -> None:
            assert http2 is True
            raise ImportError("missing h2")

    monkeypatch.setattr(http_runtime.httpx, "Client", BrokenClient)

    with pytest.raises(ImportError, match="missing h2"):
        verify_host_http_runtime()

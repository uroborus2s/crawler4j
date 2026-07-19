"""Host-provided HTTP/2 and Brotli runtime capability check."""

from __future__ import annotations

from importlib import metadata
from types import ModuleType

import brotli
import h2
import hpack
import httpx
import hyperframe


_RUNTIME_MODULES: dict[str, tuple[str, ModuleType]] = {
    "httpx": ("httpx", httpx),
    "h2": ("h2", h2),
    "hpack": ("hpack", hpack),
    "hyperframe": ("hyperframe", hyperframe),
    "brotli": ("Brotli", brotli),
}


def verify_host_http_runtime() -> dict[str, str]:
    """Verify the shared host interpreter can construct an HTTP/2 client."""

    versions = {
        import_name: metadata.version(distribution_name)
        for import_name, (distribution_name, _module) in _RUNTIME_MODULES.items()
    }
    client = httpx.Client(http2=True)
    client.close()
    return {**versions, "http2_client": "ok"}


__all__ = ["verify_host_http_runtime"]

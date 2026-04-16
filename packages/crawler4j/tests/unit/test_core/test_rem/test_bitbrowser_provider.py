from types import SimpleNamespace

import pytest

from src.core.rem.provider import BitBrowserProvider


@pytest.mark.asyncio
async def test_bitbrowser_provider_reads_creation_params_fallback(monkeypatch):
    provider = BitBrowserProvider()
    captured: dict[str, object] = {}

    async def create_browser(name, proxy, group_id, fingerprint):
        captured.update(
            {
                "name": name,
                "proxy": proxy,
                "group_id": group_id,
                "fingerprint": fingerprint,
            }
        )
        return 77

    monkeypatch.setattr(
        provider,
        "_get_api_client",
        lambda: SimpleNamespace(create_browser=create_browser),
    )

    env = await provider.create(
        {
            "env_name": "bit-env",
            "creation_params": {
                "group_id": "group-1",
                "fingerprint": {"randomize_all": True},
            },
        }
    )

    assert captured["name"] == "bit-env"
    assert captured["group_id"] == "group-1"
    assert captured["fingerprint"] == {"randomize_all": True}
    assert env.external_id == "77"

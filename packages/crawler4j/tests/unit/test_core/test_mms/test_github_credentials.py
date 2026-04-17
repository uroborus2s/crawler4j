from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.mms.github_credentials import get_github_credential_store
from src.core.persistence import get_config_store


@pytest.fixture(autouse=True)
def temp_data_dir(tmp_path: Path):
    with ExitStack() as stack:
        stack.enter_context(patch("src.utils.paths.get_app_data_dir", return_value=tmp_path))
        from src.core.persistence.database import init_database

        init_database()
        yield tmp_path


def test_github_credential_store_roundtrip_encrypts_token(temp_data_dir: Path):
    store = get_github_credential_store()

    store.set_token("example/private-repo", "ghp_secret_token_1234")

    raw_setting = get_config_store().get_setting("mms.github.repo_token.example__private-repo")
    assert raw_setting is not None
    assert "ghp_secret_token_1234" not in raw_setting
    assert store.has_token("example/private-repo") is True
    assert store.get_token("example/private-repo") == "ghp_secret_token_1234"
    assert (temp_data_dir / ".secrets" / "github_repo_tokens.key").exists()


def test_github_credential_store_clear_token():
    store = get_github_credential_store()
    store.set_token("example/private-repo", "ghp_secret_token_1234")

    assert store.clear_token("example/private-repo") is True
    assert store.has_token("example/private-repo") is False
    assert store.get_token("example/private-repo") is None


def test_github_credential_store_rejects_corrupted_payload():
    store = get_github_credential_store()
    get_config_store().set_setting(
        "mms.github.repo_token.example__private-repo",
        '{"version":"v1","ciphertext":"v1:broken"}',
    )

    with pytest.raises(ValueError) as exc_info:
        store.get_token("example/private-repo")

    assert "已损坏" in str(exc_info.value) or "校验失败" in str(exc_info.value)

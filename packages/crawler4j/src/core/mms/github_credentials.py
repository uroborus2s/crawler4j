"""GitHub 仓库凭据存储。

Token 以 repo 为维度加密后保存在应用配置库中。
数据库只保存密文，应用主密钥保存在本地 app data 目录下的私有文件。
"""

from __future__ import annotations

import base64
import hmac
import os
from pathlib import Path

from src.utils import paths


TOKEN_NAMESPACE = "mms.github"
TOKEN_KEY_PREFIX = "repo_token."
SECRET_DIRNAME = ".secrets"
MASTER_KEY_FILENAME = "github_repo_tokens.key"
MASTER_KEY_SIZE = 32
NONCE_SIZE = 16
TAG_SIZE = 32
PAYLOAD_VERSION = "v1"


class GitHubCredentialStore:
    """按 GitHub repo 保存加密 token。"""

    def __init__(self) -> None:
        from src.core.system.config_center import get_config_center

        self._config_center = get_config_center()

    def has_token(self, repo: str) -> bool:
        return self._config_center.get_internal(TOKEN_NAMESPACE, self._setting_key(repo)) is not None

    def get_token(self, repo: str) -> str | None:
        payload = self._config_center.get_internal(TOKEN_NAMESPACE, self._setting_key(repo))
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ValueError(f"仓库 {repo} 的 GitHub Token 存储已损坏，请重新配置")
        ciphertext = str(payload.get("ciphertext", "") or "").strip()
        if not ciphertext:
            raise ValueError(f"仓库 {repo} 的 GitHub Token 存储已损坏，请重新配置")
        return self._decrypt_token(ciphertext, repo)

    # Compatibility aliases for older UI/tests that still speak in repo-token terms.
    def get_repo_token(self, repo: str) -> str | None:
        return self.get_token(repo)

    def set_token(self, repo: str, token: str) -> None:
        repo = str(repo or "").strip()
        token = str(token or "").strip()
        if not repo:
            raise ValueError("GitHub 仓库不能为空")
        if not token:
            raise ValueError("GitHub Token 不能为空")
        payload = {
            "version": PAYLOAD_VERSION,
            "ciphertext": self._encrypt_token(token),
        }
        self._config_center.set_internal(TOKEN_NAMESPACE, self._setting_key(repo), payload)

    def set_repo_token(self, repo: str, token: str) -> None:
        self.set_token(repo, token)

    def clear_token(self, repo: str) -> bool:
        return self._config_center.delete_internal(TOKEN_NAMESPACE, self._setting_key(repo))

    def remove_repo_token(self, repo: str) -> bool:
        return self.clear_token(repo)

    @staticmethod
    def _setting_key(repo: str) -> str:
        return TOKEN_KEY_PREFIX + str(repo or "").strip().replace("/", "__")

    def _encrypt_token(self, token: str) -> str:
        plaintext = token.encode("utf-8")
        nonce = os.urandom(NONCE_SIZE)
        enc_key = self._derive_subkey(b"enc")
        mac_key = self._derive_subkey(b"mac")
        ciphertext = self._xor_bytes(plaintext, self._keystream(enc_key, nonce, len(plaintext)))
        tag = hmac.digest(mac_key, nonce + ciphertext, "sha256")
        encoded = base64.urlsafe_b64encode(nonce + tag + ciphertext).decode("ascii")
        return f"{PAYLOAD_VERSION}:{encoded}"

    def _decrypt_token(self, payload: str, repo: str) -> str:
        version, sep, encoded = str(payload or "").partition(":")
        if sep != ":" or version != PAYLOAD_VERSION:
            raise ValueError(f"仓库 {repo} 的 GitHub Token 版本不受支持，请重新配置")
        try:
            blob = base64.urlsafe_b64decode(encoded.encode("ascii"))
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"仓库 {repo} 的 GitHub Token 存储已损坏，请重新配置") from exc
        if len(blob) < NONCE_SIZE + TAG_SIZE:
            raise ValueError(f"仓库 {repo} 的 GitHub Token 存储已损坏，请重新配置")

        nonce = blob[:NONCE_SIZE]
        tag = blob[NONCE_SIZE:NONCE_SIZE + TAG_SIZE]
        ciphertext = blob[NONCE_SIZE + TAG_SIZE:]
        mac_key = self._derive_subkey(b"mac")
        expected_tag = hmac.digest(mac_key, nonce + ciphertext, "sha256")
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError(f"仓库 {repo} 的 GitHub Token 校验失败，请重新配置")
        enc_key = self._derive_subkey(b"enc")
        plaintext = self._xor_bytes(ciphertext, self._keystream(enc_key, nonce, len(ciphertext)))
        return plaintext.decode("utf-8")

    def _derive_subkey(self, purpose: bytes) -> bytes:
        return hmac.digest(self._get_master_key(), b"crawler4j:mms:github-token:" + purpose, "sha256")

    def _get_master_key(self) -> bytes:
        path = self._master_key_path()
        if path.exists():
            encoded = path.read_text(encoding="utf-8").strip()
            try:
                key = base64.urlsafe_b64decode(encoded.encode("ascii"))
            except Exception as exc:  # pragma: no cover - defensive
                raise ValueError("GitHub Token 主密钥文件已损坏，请清理后重新配置") from exc
            if len(key) != MASTER_KEY_SIZE:
                raise ValueError("GitHub Token 主密钥长度无效，请清理后重新配置")
            return key

        key = os.urandom(MASTER_KEY_SIZE)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(base64.urlsafe_b64encode(key).decode("ascii"), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return key

    @staticmethod
    def _xor_bytes(left: bytes, right: bytes) -> bytes:
        return bytes(a ^ b for a, b in zip(left, right, strict=True))

    @staticmethod
    def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
        blocks = bytearray()
        counter = 0
        while len(blocks) < length:
            counter_bytes = counter.to_bytes(8, "big")
            blocks.extend(hmac.digest(key, nonce + counter_bytes, "sha256"))
            counter += 1
        return bytes(blocks[:length])

    @staticmethod
    def _master_key_path() -> Path:
        return paths.get_app_data_dir() / SECRET_DIRNAME / MASTER_KEY_FILENAME


_github_credential_store: GitHubCredentialStore | None = None


def get_github_credential_store() -> GitHubCredentialStore:
    global _github_credential_store
    if _github_credential_store is None:
        _github_credential_store = GitHubCredentialStore()
    return _github_credential_store

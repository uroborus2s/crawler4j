# TASK-037 Contracts 0.4.3 / SDK 0.4.4 发布证据

- 日期：2026-07-10（Asia/Shanghai）
- 状态：READY_TO_PUBLISH
- 范围：仅 `crawler4j-contracts` 与 `crawler4j-sdk`；客户端保持现有 `0.4.29`

## PyPI 发布前检查

- `https://pypi.org/pypi/crawler4j-contracts/json`：HTTP 200，最新版本 `0.4.2`。
- `https://pypi.org/pypi/crawler4j-contracts/0.4.3/json`：HTTP 404，目标版本未占用。
- `https://pypi.org/pypi/crawler4j-sdk/json`：HTTP 200，最新版本 `0.4.3`。
- `https://pypi.org/pypi/crawler4j-sdk/0.4.4/json`：HTTP 404，目标版本未占用。

## 发布前验证

- 首次全量 unit：`1132 passed, 2 failed`；失败均为发布一致性断言，根因见 `../reports/root-cause.md`。
- 最小修正后失败用例复跑：`2 passed`。
- 最终全量 unit：`1134 passed in 27.88s`，exit code `0`。
- 目标 Ruff：exit code `0`，`All checks passed!`。
- `uv lock --check`：exit code `0`。
- `.factory/project.json`：`python -m json.tool` exit code `0`。
- `docs-stratego source validate`：exit code `0`，`pages=86 contracts=0`。
- `git diff --check`：exit code `0`。

## 构建产物

- `crawler4j_contracts-0.4.3-py3-none-any.whl`：SHA256 `8ddd6d3f29a9a1daeaf48113f0610ca98837570a6f6f7ff7c4df2eddcdc72f75`。
- `crawler4j_contracts-0.4.3.tar.gz`：SHA256 `419dbb14fee5185cee3750d46a982d6ba39498aa7d6ba8efa7a8a22977c5d49a`。
- `crawler4j_sdk-0.4.4-py3-none-any.whl`：SHA256 `f1445183e40e6a22ce5296740838ec25699a988bd27bd71bad148080e51cff90`。
- `crawler4j_sdk-0.4.4.tar.gz`：SHA256 `2218238f297eb6bd519c90eb9158061ccb6d81dcea7ca120804476736b961d48`。
- wheel 元数据确认 Contracts `Version: 0.4.3`；SDK `Version: 0.4.4` 且 `Requires-Dist: crawler4j-contracts<0.5.0,>=0.4.3`。
- Contracts / SDK `uv publish --dry-run` 均成功检查 wheel 与 sdist。

## 待补证据

- 按 Contracts -> SDK 顺序执行正式 `uv publish`。
- 每个包发布后通过 PyPI JSON API 验证版本和文件列表。

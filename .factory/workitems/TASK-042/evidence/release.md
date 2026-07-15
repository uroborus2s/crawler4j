# TASK-042 Contracts 0.4.4 / SDK 0.4.5 / Client 0.4.39 发布证据

- 日期：2026-07-15（Asia/Shanghai）
- 状态：PYPI_PUBLISHED_PENDING_REMOTE_PUSH
- 范围：Contracts / SDK 发布到 PyPI；客户端源码版本升级与 root build；Git 分支推送

## PyPI 发布前检查

- `crawler4j-contracts` 最新版本 `0.4.3`；目标 `0.4.4` JSON API 返回 HTTP 404，未占用。
- `crawler4j-sdk` 最新版本 `0.4.4`；目标 `0.4.5` JSON API 返回 HTTP 404，未占用。
- `crawler4j` 项目 JSON API 返回 HTTP 404；按现有正式流程不创建新的 PyPI 项目，只构建客户端 root wheel/sdist。

## 发布候选版本与依赖

- `crawler4j-contracts==0.4.4`
- `crawler4j-sdk==0.4.5`，wheel METADATA 依赖 `crawler4j-contracts>=0.4.4,<0.5.0`
- `crawler4j==0.4.39`，wheel METADATA 依赖 `crawler4j-contracts>=0.4.4,<0.5.0`
- `uv.lock` 已同步三包版本；`uv lock --check` 通过。

## 构建与产物

`uv run build crawler4j-contracts crawler4j-sdk crawler4j` 成功，产物 SHA256：

| 产物 | SHA256 |
|---|---|
| `crawler4j_contracts-0.4.4-py3-none-any.whl` | `3c0c07a860163e847eb357d5469c9c8c96c14e67d5c6ba30d51ce408a7b447ba` |
| `crawler4j_contracts-0.4.4.tar.gz` | `8649afa0f8626718f3a6bc88c5a61442cc653fde2954ace7c50b916bd5e1d2af` |
| `crawler4j_sdk-0.4.5-py3-none-any.whl` | `8d4090e24adfe111d5d02969d3e0ed906208f706f8205b526095418059b82806` |
| `crawler4j_sdk-0.4.5.tar.gz` | `59eb04c6c368a4e275af7701bc5caae1c91ea995daeb7b65bc4db552d12d9c66` |
| `crawler4j-0.4.39-py3-none-any.whl` | `691d3112bc27c51f7715734bb9718cf36a4fa19185c2b7245bbf48418184fbf9` |
| `crawler4j-0.4.39.tar.gz` | `376b3e1e44ed585c1599da0f0f3a06fc3e0d95b765e5f117baff1c9f2dacc627` |

Contracts 与 SDK 的 `uv run publish <package> --dry-run` 均成功，每个发布目标精确检查 wheel/sdist 两个文件。

## 发布前验证

- 版本/Contracts/SDK/打包聚焦回归：以下命令 exit `0`，`175 passed`：

  ```bash
  UV_CACHE_DIR=/tmp/crawler4j-uv-cache QT_QPA_PLATFORM=offscreen uv run --offline --no-sync pytest -q -p no:cacheprovider \
    packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py \
    packages/crawler4j/tests/unit/test_sdk/test_contracts_exports.py \
    packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py \
    packages/crawler4j/tests/unit/test_sdk/test_packaging_config.py \
    packages/crawler4j/tests/unit/test_sdk/test_cli_host_release.py \
    packages/crawler4j/tests/unit/test_core/test_system/test_version_service.py
  ```
- CR-022 最终 Core 定向基线：renderer `36 passed`、七文件 `202 passed`、SDK/MMS/UI `586 passed`；消费侧联调七文件 `262 passed`、页面 `9 passed`、`crawler4j check full` 与 scoped Ruff/Mypy 通过。
- 全量 unit：`1235 passed`，另有 13 项稳定的范围外环境基线：5 项 debug session 路径被沙箱拒绝，8 项 REM/proxy state DB 只读；与版本升级前 CR-022 基线一致，变更范围测试无新增失败。
- root sdist 污染修复：TDD RED/GREEN、打包回归 `63 passed`；重建 sdist 为 37,279,993 bytes / 529 entries，不含 `desktop` 或临时目录。证据：`root-sdist-contamination-fix-tdd.md`。
- `uv run ruff check .`、`uv lock --check`、`.factory/project.json` JSON、UI smoke、docs-stratego（`pages=87 contracts=0`）与 `git diff --check` 通过。

## PyPI 正式发布与在线验证

发布顺序严格为 Contracts -> SDK：

1. `uv run publish crawler4j-contracts` exit `0`，上传 0.4.4 wheel/sdist。
2. PyPI JSON API 返回 Contracts 0.4.4；两个在线 SHA256 与本地产物完全一致。
3. `uv run publish crawler4j-sdk` exit `0`，上传 0.4.5 wheel/sdist。
4. PyPI JSON API 返回 SDK 0.4.5；两个在线 SHA256 与本地产物完全一致；`Requires-Dist` 为 `crawler4j-contracts<0.5.0,>=0.4.4`。
5. 从 `/private/tmp` 执行隔离 PyPI 安装，输出 Contracts `0.4.4`、SDK `0.4.5`，且导入路径位于隔离 uv archive 的 `site-packages`，不是 workspace editable source。

PyPI 页面：

- `https://pypi.org/project/crawler4j-contracts/0.4.4/`
- `https://pypi.org/project/crawler4j-sdk/0.4.5/`

## 待补证据

- 最终 release evidence commit 与 `origin/0.4.0` 推送结果。

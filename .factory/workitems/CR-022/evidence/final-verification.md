# CR-022 Final Verification

## Targeted contract/runtime/renderer gate

七个目标文件：`199 passed in 4.50s`，exit code `0`。独立 reviewer 同集：`199 passed in 4.45s`，exit code `0`。

## Related suites

```bash
UV_CACHE_DIR=/tmp/crawler4j-uv-cache QT_QPA_PLATFORM=offscreen \
uv run pytest -q -p no:cacheprovider \
  packages/crawler4j/tests/unit/test_sdk \
  packages/crawler4j/tests/unit/test_core/test_mms \
  packages/crawler4j/tests/unit/test_ui
```

结果：`583 passed in 13.05s`，exit code `0`。

## Full unit gate and baseline distinction

```bash
UV_CACHE_DIR=/tmp/crawler4j-uv-cache QT_QPA_PLATFORM=offscreen \
uv run pytest packages/crawler4j/tests/unit -q -p no:cacheprovider
```

结果：`13 failed, 1231 passed in 28.67s`，exit code `1`。

13 项均为本变更范围外且已在修复前后稳定复现的环境/基线失败：

- 5 项 `test_core/test_debug/test_service.py`：沙箱禁止写入 `/Users/uroborus/Library/Application Support/Crawler4j/debug_sessions/...`，抛 `PermissionError: Operation not permitted`。
- 7 项 `test_core/test_rem/test_post_create_actions.py` 与 1 项 `test_core/test_rem/test_proxy_binding.py`：测试进程引用只读状态数据库，抛 `sqlite3.OperationalError: attempt to write a readonly database`。

失败文件、debug service 和 REM 实现均未被 CR-022 修改；所有 CR-022 目标与 SDK/MMS/UI 相关套件独立全绿。因此将这 13 项记录为无法归因于本变更的现有环境基线，不在本任务越权修改。

## Static, lock, docs and diff gates

- `UV_CACHE_DIR=/tmp/crawler4j-uv-cache uv run ruff check .`：`All checks passed!`，exit code `0`。
- `UV_CACHE_DIR=/tmp/crawler4j-uv-cache uv lock --check`：`Resolved 78 packages`，exit code `0`。
- `UV_CACHE_DIR=/tmp/crawler4j-uv-cache UV_TOOL_DIR=/tmp/crawler4j-uv-tools uvx --from docs-stratego docs-stratego source validate --repo-path .`：`pages=87 contracts=0`，exit code `0`。
- `git diff --check`：无输出，exit code `0`。

## Consumer integration evidence

消费模块维护方报告：本地 editable Contracts/SDK 下，`crud.form.layout={"columns":3,"gap":12}` 被 manifest lock 保留，`crawler4j check full` 通过，模块定向 `262 passed`；其只读 Core 复核在增量 review 修复前为七文件 `197 passed`、schema + renderer 子集 `81 passed`。该证据不替代上述 Core gate，本任务未修改消费模块。

## Scope and review

- 独立 review：`approved`，`98/100`，无 Critical/Important finding。
- Contracts `0.4.3`、SDK `0.4.4` 保持不变；未发布、未 push。
- diff 新增内容未加入消费模块、平台/设备模板、业务 create preset 或 handler effect 协议。

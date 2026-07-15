# CR-022 Shared Form Columns Final Verification

## Claim

CRUD Form 使用共享 label/input 物理列后，同逻辑列跨行对齐；内部 `6px` spacing 与声明式逻辑列 gap 分离；单列超大 gap 不会把输入控件推出 viewport；既有 Hosted UI Form 初始化、事件、reset、滚动和固定按钮行为不变。

## Targeted gate

- renderer 全文件：exit code `0`，`36 passed in 1.87s`。
- CR-022 七文件：exit code `0`，`202 passed in 5.01s`。
- SDK/MMS/UI 邻近回归：exit code `0`，`586 passed in 13.87s`。
- 独立 reviewer：renderer `36 passed`、七文件 `202 passed`、邻近 `586 passed`，结论 `approved`、`100/100`。

以上命令均为 `QT_QPA_PLATFORM=offscreen`、`-p no:cacheprovider` 的新鲜执行；`0 failed`、`0 errors`、`0 skipped`。

## Full unit gate and baseline distinction

```bash
UV_CACHE_DIR=/tmp/crawler4j-uv-cache QT_QPA_PLATFORM=offscreen \
uv run pytest packages/crawler4j/tests/unit -q -p no:cacheprovider
```

结果：exit code `1`，`13 failed, 1234 passed in 30.65s`。

13 项与修复前、首轮 CR-022 最终 gate 完全相同：

- 5 项 `test_core/test_debug/test_service.py`：沙箱禁止写入用户 Application Support 下的 debug session 目录，抛 `PermissionError: Operation not permitted`。
- 7 项 `test_core/test_rem/test_post_create_actions.py` 与 1 项 `test_core/test_rem/test_proxy_binding.py`：环境状态数据库只读，抛 `sqlite3.OperationalError: attempt to write a readonly database`。

失败文件和对应 Debug/REM 实现均未被本增量修改；renderer、MMS、SDK、UI 相关 gate 全绿。按用户要求将其保留为不可归因于 CR-022 的环境基线，不越权修改。

## Static, docs, lock and diff gates

- `UV_CACHE_DIR=/tmp/crawler4j-uv-cache uv run ruff check .`：exit code `0`，`All checks passed!`。
- `UV_CACHE_DIR=/tmp/crawler4j-uv-cache uv lock --check`：exit code `0`，`Resolved 78 packages`。
- `docs-stratego source validate --repo-path .`：exit code `0`，`pages=87 contracts=0`。
- `git diff --check`：exit code `0`，无输出。

## Scope and specialization gates

- 对产品源码、renderer 测试和正式文档 diff 的新增行扫描 `ctrip|Mac|Windows|create_preset`：无匹配（`rg` exit code `1` 表示空结果）。
- 变更路径扫描 `ctrip_crawler|packages/crawler4j-contracts|packages/crawler4j-sdk`：无匹配；Contracts/SDK/schema/版本均未修改。
- 未发布、未 push、未修改消费模块。

## Consumer read-only evidence

消费侧报告：renderer `35 passed`、当时 CR-022 七文件 `201 passed`、scoped Ruff 通过；消费模块 `crawler4j check full` 与页面 `9 tests` 通过，schema 无需变化。该结果早于新增的 gap-preservation test，因此计数比最终 Core gate 少 1；只作为下游兼容证据，不替代本仓 gate。

## Result

`passed_for_changed_scope_with_13_unrelated_environment_baseline_failures`。所有可归因于本增量的目标、邻近、静态、文档、lock、diff、scope 与独立 review gate 均通过。

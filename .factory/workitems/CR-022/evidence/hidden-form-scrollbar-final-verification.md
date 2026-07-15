# CR-022 Hidden Form Scrollbar Final Verification

## Claim

CRUD 长 Form 的水平与垂直原生滚动槽均不再显示；内部 `QScrollArea`、非零垂直滚动范围、Page Down 键盘滚动和程序化滚动仍有效，确认/取消按钮继续位于滚动区外。本增量不改变 schema、Contracts、SDK、字段事件、Form reset、初始化或提交契约。

## TDD

- RED：35 字段 renderer 用例新增垂直 `ScrollBarAlwaysOff` 断言后，实际策略为 `ScrollBarAsNeeded`，`1 failed`。
- GREEN：垂直策略改为 `ScrollBarAlwaysOff` 后，同一用例 `1 passed`；断言双向隐藏、非零垂直范围、Page Down 与程序化滚动均有效。
- renderer 全文件：`36 passed in 2.84s`。
- renderer 原有大 gap 用例依赖真实屏幕宽度，在当前宽屏环境中单独复现 `columns=2` 而不是固定预期 `1`；测试改为注入固定 `800x800` screen geometry，产品算法未改，随后 renderer 全绿。

## Regression gates

- CR-022 七文件：`202 passed in 5.72s`，exit code `0`。
- SDK/MMS/UI 邻近回归：`586 passed in 14.88s`，exit code `0`。
- 全量 unit：`13 failed, 1234 passed in 31.15s`，exit code `1`。13 项与本增量前登记的环境基线相同：5 项 debug service 因沙箱禁止写入用户 Application Support；7 项 REM post-create 与 1 项 proxy binding 因环境状态数据库只读。变更未涉及这些文件或路径。

## Static, docs and lock gates

- `uv run ruff check .`：`All checks passed!`，exit code `0`。
- `uv lock --check`：`Resolved 78 packages`，exit code `0`。
- `uvx --from docs-stratego docs-stratego source validate --repo-path .`：`pages=87 contracts=0`，exit code `0`。
- `git diff --check`：无输出，exit code `0`。

## Scope

- 产品代码仅修改 Core `ManagedPageRenderer` 的滚动条策略。
- 测试仅修改对应 renderer unit test；固定大 gap 用例的屏幕几何，消除显示器相关漂移。
- 只同步 CR-022 工作项、开发文档和 memory。
- 未修改 Contracts、SDK、消费模块、版本、lock、发布或远端状态。

## Independent review

- reviewer：`/root/cr022_independent_review`（`independent_subagent`，未参与实现，仅读取文件化输入包和当前 diff）。
- 结论：`approved`，`100/100`，无 Critical / Important / Minor finding。
- reviewer 独立验证：单项 `1 passed`、renderer `36 passed`、七文件 `202 passed`、邻近 `586 passed`，Ruff/lock/diff check 均通过；额外 Qt 探针验证 wheel event 可改变隐藏滚动条的内部 value。

## Result

`passed_for_changed_scope_with_13_unrelated_environment_baseline_failures`。

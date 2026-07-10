# CR-018 / TASK-036 Task 2 实现报告

## 状态

- Implementer status: `DONE`
- Work item state: `ready_for_review`
- Needs: `review`
- Ledger event: none（任务边界禁止修改 ledger）

## 产出

- `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py`
- `packages/crawler4j/src/ui/components/data_table.py`
- `packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py`
- `packages/crawler4j/tests/unit/test_ui/test_data_table.py`
- `.factory/workitems/CR-018/evidence/task-2.md`
- `.factory/workitems/CR-018/reports/task-2.md`

## 实现摘要

- Core 透传 DataTable 顶层选择模式，并将 bulk update 纳入既有 CRUD toolbar。
- bulk update 复用 `SkyDataTable.selected_rows()`、现有 update form、`_invoke_ui_action(_async)` 与既有成功回调机制。
- bulk 参数固定为 `primary_keys + payload`，保留主键类型和顺序并去重；缺主键整批拒绝。
- 单条 toolbar CRUD 仅允许单选；行内 CRUD 显式携带点击行，避免误用多选首行。
- `SkyDataTable.request_refresh()` 统一清选择，因此手动刷新、搜索/筛选/排序、分页和 action 成功刷新均不跨结果集保留选择。

## TDD 与调试记录

- RED: `5 failed, 33 passed`，失败点与新增行为一致。
- 首轮实现后为 `3 failed, 35 passed`；调查确认测试 fixture 提前持有的模块实例会被 action runtime 重载后淘汰，导致模块全局调用列表成为陈旧观察点，并非生产 action 未执行。
- 测试改在 bridge 边界记录 `action_name + params`，直接验证 Core 参数契约；生产实现未为该测试问题增加兜底。
- GREEN: `38 passed`。

## Self-review

- Scope: 只修改 task brief 允许的 6 个文件；未触碰 Contracts、SDK、数据库、业务模块、docs、memory 或 ledger。
- Correctness: 同步、event-loop 调度和直接异步路径均有覆盖；成功/失败选择与刷新语义分别断言。
- Regression: 既有 renderer/DataTable 单测与新增用例在同一命令下全部通过。
- Simplicity: 未新增抽象层、依赖或持久化路径；复用现有 toolbar、form、dialog 和 action runtime。
- Review boundary: 未自批 `approved`，未 commit。

## Concerns

- none

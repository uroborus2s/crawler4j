# TASK-038 独立评审输入

## 输入

- 需求：`.factory/workitems/CR-019/brief.md`
- 计划：`.factory/workitems/CR-019/plan.md`
- 任务：`.factory/workitems/CR-019/task-briefs/TASK-038.md`
- Evidence：`.factory/workitems/CR-019/evidence/TASK-038.md`
- Report：`.factory/workitems/CR-019/reports/TASK-038.md`

## 评审范围

- `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py`
- `packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py`
- `docs/03-developer-guide/v0.4.0/ui-and-data-table.md`

## 必查项

- `open_page` 是否只解析显式 params，且不落入 `crud.primary_key` 兜底。
- 未声明 `type` 的行按钮、CRUD 行按钮是否保持兼容。
- 导航是否避免调用同名 `ui_action` 和刷新源表。
- 测试是否锁定点击行而非当前选中行。
- 是否有范围外改动或不必要抽象。

当前证据：RED `1 failed`，GREEN `1 passed`；邻近回归 `73 passed`；Ruff 与 diff check 通过。未决问题：无。


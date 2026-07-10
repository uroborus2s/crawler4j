# TASK-038 行按钮 open_page 任务简报

## 工作项

- 工作项：`CR-019`
- 任务：`TASK-038`
- 状态：`ready_for_review`
- 上游计划：`.factory/workitems/CR-019/plan.md`
- 流水账：`.factory/workitems/CR-019/ledger.jsonl`

## 目标

让 Hosted UI DataTable actions 列的显式按钮使用当前行参数打开目标页，同时保持 CRUD 与默认 `ui_action` 行按钮兼容。

## 输入与边界

- 必读：需求简报、计划、renderer 相关方法与现有行按钮/整行导航测试。
- 允许修改：renderer、renderer 测试、0.4.0 UI 开发者文档、CR-019 evidence/report/review/ledger、任务摘要。
- 禁止修改：`SkyDataTable`、Contracts、SDK scanner、用户已有发布任务脏改动、版本号与发布文档。

## 实施与验证

1. 新增点击第二行详情按钮的 RED 测试；同时断言不执行同名 `ui_action`、不刷新源表。
2. 运行目标测试，确认因误分发到 `ui_action` 而失败。
3. 在 `_handle_table_row_action` 增加 `open_page` 分支并复用 `_handle_row_action`。
4. 运行目标测试、邻近回归、ruff 与 `git diff --check`。
5. 同步文档、evidence、report、ledger 和任务摘要，提交独立评审。

```bash
PYTHONDONTWRITEBYTECODE=1 uv run pytest -p no:cacheprovider -q packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py::test_managed_page_renderer_row_button_opens_page_with_clicked_row_params
```

期望：实现前失败、实现后通过；邻近回归零失败。

## 输出与完成口径

- Evidence：`.factory/workitems/CR-019/evidence/TASK-038.md`
- Report：`.factory/workitems/CR-019/reports/TASK-038.md`
- Review：`.factory/workitems/CR-019/reviews/TASK-038-review.md`
- 实现者只能进入 `ready_for_review`；`approved` 必须来自独立评审。


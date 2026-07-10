# 任务 2 简报：Core Renderer 多选批量编辑

## 工作项

- 工作项：`CR-018`
- 父任务：`TASK-036`
- 状态：`approved`
- 依赖：任务 1 schema 与 scanner 已通过定向测试
- 上游：`.factory/workitems/CR-018/brief.md`

## 目标

在 Core Renderer 中透传多选模式，新增批量编辑 toolbar、空白 update 表单和同步 / 异步 handler 调用，并保证单条动作不误作用于多选首行。

## 设计、接口、UI、测试

- 设计方案：复用 `SkyDataTable.selected_rows()`、现有 CRUD form 和 `_invoke_ui_action(_async)`；不修改数据库层。
- 接口：固定传 `{"primary_keys": [...], "payload": {...}}`，主键保序去重且保留原类型。
- UI：0 行批量按钮禁用、1+ 行启用；编辑 / 删除仅 1 行启用；行内动作显式使用点击行。
- 测试：先逐条覆盖选择模式、按钮 0/1/2 状态、主键提取、缺失主键、空值、成功 / 失败、同步 / 异步、行内动作和翻页 / 刷新清选择，再写 GREEN。

具体断言：

- Core 调用 params 只含 `primary_keys` 与 `payload`，不传整行；`context` 继续由 action runtime 注入。
- handler 存在且 `toolbar.bulk_update` 省略时批量按钮显示，显式 `False` 时隐藏；`render="row_actions"` 时批量按钮仍显示在 toolbar。
- 任一选中行缺少主键时 warning 指明字段且 handler 调用数为 0。
- 批量表单收到 `row=None`；可空文本空白值为 `None`，payload 原样透传。
- 成功回调清选择并只触发一次 refresh；失败时不清选择、不刷新并显示原始异常文本。
- 多选下行内编辑 / 删除使用点击行；toolbar 单条动作在多选时不可调用。
- 翻页或手动 `request_refresh()` 后选择为空。

## 允许修改

- `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py`
- `packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py`
- `packages/crawler4j/src/ui/components/data_table.py`（仅用于确保翻页 / 刷新清选择）
- `packages/crawler4j/tests/unit/test_ui/test_data_table.py`
- `.factory/workitems/CR-018/evidence/task-2.md`
- `.factory/workitems/CR-018/reports/task-2.md`

## 禁止修改

- Contracts、SDK scanner、数据库层、业务模块、正式文档和 memory。

## 验证命令

```bash
QT_QPA_PLATFORM=offscreen uv run pytest packages/crawler4j/tests/unit/test_ui/test_data_table.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py -q -p no:cacheprovider
uv run ruff check packages/crawler4j/src/core/mms/ui/managed_page_renderer.py packages/crawler4j/src/ui/components/data_table.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py packages/crawler4j/tests/unit/test_ui/test_data_table.py
```

期望：新增行为和既有 DataTable / Renderer 回归全部通过，ruff 无错误。

## 输出与状态

- 写 RED / GREEN 真实命令结果到 `evidence/task-2.md`。
- 写实现、文件和自检到 `reports/task-2.md`。
- 实现者最多返回 `ready_for_review`，不得自批 approved。

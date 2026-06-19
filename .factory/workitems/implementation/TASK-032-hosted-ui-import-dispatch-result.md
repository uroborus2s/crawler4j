# TASK-032 贯通 Hosted UI 导入分发与结果展示

- 状态：PLANNED
- 负责人：Codex
- 优先级：P1
- 估算：2.0 人/天
- 关联 ID：`TASK-032`, `CR-016`, `REQ-010`, `API-019`, `TC-060`

## 目标

- 让 Hosted UI renderer 能执行 toolbar actions。
- 让导入弹窗提交后的 payload 可分发给模块 `@ui_action` 或 workflow。
- 展示模块返回的批次结果并支持跳转明细页。

## 范围

- Renderer：页面 / 表格 toolbar action 分发。
- `@ui_action`：以 `import_payload` 参数接收导入数据。
- workflow：通过 ATM 调度并把 payload 写入 `ctx.runtime["import_payload"]`。
- 结果展示：展示 `batch_id/total_rows/staged_rows/failed_rows`，支持刷新和 `open_page` 跳转。

## 非目标

- 不在 UI 线程直接执行 workflow。
- 不定义模块业务落库规则。
- 不实现通用导入暂存表。

## 验收标准

- `open_import_dialog.submit.type="ui_action"` 能把 payload 交给指定 `@ui_action`。
- `open_import_dialog.submit.type="workflow"` 能启动受控 workflow 并传入运行态 payload。
- 模块返回批次汇总后，宿主展示结果。
- 返回或声明 `records_page_id="import_data_records"` 时，宿主能带 `batch_id/target_type` 跳转。

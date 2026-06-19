# TASK-032 贯通 Hosted UI 导入分发与结果展示

- 状态：DONE
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

## 实现记录

- 2026-06-19 `ManagedPageRenderer` 已渲染页面级和 `DataTable` toolbar，并统一分发 `ui_action`、`workflow`、`open_import_dialog`。
- `open_import_dialog.submit.type="ui_action"` 默认以 `import_payload` 参数调用模块 `@ui_action`，也支持 `payload_param` 改名。
- `open_import_dialog.submit.type="workflow"` 通过 `TaskService.create_job/start_job` 启动 batch/manual workflow，并把 payload 写入 `RunProfile.resource.acquisition.creation.params["import_payload"]`。
- `ExecutionRunner._build_runtime_payload()` 会把 `creation_params.import_payload` 提升到 `ctx.runtime["import_payload"]`，便于模块 workflow 读取。
- 模块返回 `batch_id/total_rows/staged_rows/failed_rows/target_type/records_page_id` 后，宿主展示批次摘要，并可跳转 `import_data_records`，参数为 `batch_id/target_type`。
- 验证：`test_managed_page_renderer.py` 覆盖 `@ui_action` 导入分发、批次结果跳转和 workflow 任务创建；`test_execution_runner.py` 覆盖 runtime payload 提升。

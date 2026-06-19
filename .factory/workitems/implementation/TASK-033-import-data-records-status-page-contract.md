# TASK-033 约定导入暂存明细与逐条状态展示

- 状态：DONE
- 负责人：Codex
- 优先级：P1
- 估算：1.0 人/天
- 关联 ID：`TASK-033`, `CR-016`, `REQ-010`, `API-019`, `TC-060`

## 目标

- 固化 `import_data_records` 页面约定。
- 让导入批次明细和后续从暂存表导入业务表的逐条状态可见。

## 范围

- 页面参数：`batch_id`、`target_type`。
- 状态口径：`pending`、`staged`、`validation_failed`、`imported`、`import_failed`、`skipped_duplicate`。
- 交互建议：批次筛选、失败原因、重试 / 导入业务表动作。
- 开发者文档：说明模块如何用 `@data_table` 和 `ctx.db` 实现批次表、明细表和状态更新。

## 非目标

- 不强制宿主提供统一物理表。
- 不替模块实现业务去重和业务落库。

## 验收标准

- 宿主跳转 `import_data_records` 时能带上批次参数。
- 开发者文档明确模块需要声明批次明细页和数据表。
- 从暂存表导入业务表后的逐条成功 / 失败 / 跳过状态有正式展示口径。

## 实现记录

- 2026-06-19 已固定宿主跳转约定：模块导入结果返回 `records_page_id="import_data_records"` 时，宿主以 `{"batch_id": batch_id, "target_type": target_type}` 打开目标页。
- 暂存明细页仍由模块用 `@page` / `DataTable` / `@data_table` / `ctx.db` 实现；宿主不强制提供统一物理表。
- 正式状态口径继续沿用 `pending/staged/validation_failed/imported/import_failed/skipped_duplicate`，用于批次明细页和后续“从暂存表导入业务表”的逐条结果展示。
- 验证：`test_managed_page_renderer_dispatches_table_toolbar_import_to_ui_action` 已覆盖导入汇总返回后的 `import_data_records` 跳转参数。

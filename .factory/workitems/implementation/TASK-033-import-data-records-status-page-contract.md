# TASK-033 约定导入暂存明细与逐条状态展示

- 状态：PLANNED
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

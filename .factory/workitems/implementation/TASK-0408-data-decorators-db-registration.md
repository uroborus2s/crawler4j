# TASK-0408 接入 data decorators 到 ctx.db 注册

- 状态：DONE
- 负责人：Codex
- 优先级：P0
- 估算：2.0 人/天
- 关联 ID：`TASK-0408`, `TASK-0400`, `REQ-0400`, `API-012`, `TC-0400-007`, `TC-0400-managed-dataset-count`

## 目标

- `@data_table` 生成 data resource。
- `@data_view` 生成 read-only view。
- 保留字段冲突在 SDK/Core 前置阻断。
- `custom_table` 支持在 integer `record_key_field` 上声明 `auto_increment=True`，并通过 `ctx.db.into(...).add(...)` 新增时省略 id。
- `managed_dataset` 支持 `where` 后 `count(*)` 统计过滤后的记录条数。

## 完成记录

- 2026-05-08：已完成 `@data_table/@data_view` 到 Core 数据注册链路；本轮补齐 `custom_table` 自增主键和 insert-only `add_records` 写入入口，新增记录可返回生成 id。
- 2026-05-09：已按边界补齐 `managed_dataset` 的 `ctx.db.from_(...).where(...).count(alias=...).execute()`；只开放单个 `count(*)`，`join`、`group_by` 和其它聚合仍拒绝。

# TASK-022 新增模块审计事件存储工具链

- 状态：DONE
- 负责人：Codex
- 优先级：P1
- 估算：1.0 人/天
- 关联 ID：`TASK-022`, `REQ-008`, `CR-008`, `NFR-004`

## 目标

- 为模块开发者提供与快照 dataset 分离的审计事件写入与查询能力。
- 保持现有 `module_datasets` 与 `core:data_table` 的快照语义稳定。
- 让宿主文档、测试和追踪资产能够明确区分快照数据与事件数据。

## 范围

- 在 `data.db` 中新增 `module_audit_events` 表与索引。
- 为 `ModuleDataStore` 增加事件追加与查询能力。
- 为 runtime capabilities 注册 `db.append_event`、`db.query_events`。
- 补齐持久层 / runtime / SDK 能力面的回归测试。
- 更新 PRD、需求分析、需求校验、API 设计、开发者指南、测试计划和 `.factory/memory/`。

## 非目标

- 不实现历史 `account_events` 自动迁移脚本。
- 不实现 retention / archive 执行器。
- 不把审计事件接入 `core:data_table` 的 create/update UI。

## 验收标准

- `module_audit_events` 可独立持久化 append-only 事件。
- `db.append_event` 可追加审计事件，不覆盖历史。
- `db.query_events` 支持按 `dataset / entity_key / event_type / run_id / time range` 查询。
- `clear_module_data()` 会同时清理模块快照数据、事件数据和数据表 schema。
- 正式文档、追踪矩阵和 `.factory/memory/` 已同步。

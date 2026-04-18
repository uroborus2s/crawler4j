# CR-008 模块快照数据与审计事件存储分层

- 状态：DONE
- 类型：CR
- 优先级：P1
- 估算：1.0 人/天
- 关联 ID：`CR-008`, `REQ-008`, `API-005`, `API-006`, `TASK-022`
- 提出日期：2026-04-18

## 变更动机

- 当前 `db.list_records` / `db.replace_records` 的真实语义是“读取快照 / 全量覆盖快照”。
- 模块开始出现 `account_events` 这类 append-only 审计事件数据，继续放在 `module_datasets.records_json` 中会带来写放大、历史膨胀和语义混淆。
- 宿主需要把“当前状态型数据”和“事件型历史数据”拆成两条正式契约，而不是继续让模块把事件历史伪装成普通 dataset。

## 变更范围

- 在 `data.db` 中新增 `module_audit_events` 存储模型。
- 在运行时工具面新增 `db.append_event`、`db.query_events`。
- 保持 `module_datasets`、`db.list_records`、`db.replace_records` 的快照语义不变。
- 更新 PRD、需求追踪、API 契约、开发者指南、测试计划和 `.factory/memory/`。

## 非目标

- 本轮不实现 retention / archive 策略。
- 本轮不为审计事件提供可编辑的 `core:data_table` UI。
- 本轮不按 `*_events` 后缀做隐式自动迁移或自动路由。

## 完成说明

- 宿主已新增 `module_audit_events` 表与查询索引。
- `ModuleDataStore` 已支持事件追加、过滤查询与模块级清理。
- ATM runtime capabilities 已注入 `db.append_event` / `db.query_events`。
- 文档已明确：快照型数据继续走 `module_datasets`，审计事件走 `module_audit_events`。

## 完成判定

- 审计事件写入不再依赖 `db.replace_records` 全量覆盖。
- 模块可通过统一 `ctx.tools.call(...)` 追加和查询事件。
- 正式文档、测试计划、追踪矩阵和 `.factory/memory/` 已同步。

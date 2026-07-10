# TASK-036 实现 managed_dataset 批量字段修改

- 状态：CORE_PACKAGES_RELEASED（overall review approved；业务模块接线另行完成）
- 负责人：Codex
- 优先级：P1
- 估算：2.5 人/天
- 关联 ID：`TASK-036`, `CR-018`, `REQ-012`, `NFR-012`, `API-021`, `TC-069`

## 目标

- 为 Hosted UI `DataTable` 提供当前页多选批量编辑能力，使模块 handler 能接收顺序稳定、去重后的主键数组和表单 payload。
- 让使用 `managed_dataset` 的业务模块通过现有 `ctx.db.update_where(...)` / batch 能力自行完成批量更新。

## 范围

- Contracts schema 与规范化。
- SDK v2 scanner 静态诊断。
- Core Renderer 批量编辑 toolbar、空白表单、同步 / 异步调用和选择状态。
- 单元测试、正式设计 / API / 测试 / 追踪文档与 `.factory/memory/` 同步。

## 验收标准

- `selection_mode=multi` 传递到 `SkyDataTable`；省略时为 `single`，非法值被 Contracts 拒绝。
- 批量按钮在 0 行时禁用、1 行及以上启用；单条编辑 / 删除仅在 1 行时启用。
- handler 固定收到 `primary_keys` 与 `payload`；主键保序去重，缺失主键时不调用。
- 批量表单不预填第一行；可空文本留空传 `None`。
- 同步 / 异步成功后清选择并刷新，失败时保留选择并展示业务错误。
- SDK 拒绝缺失 handler、错误签名、裸 `list` / `list[Any]`、裸 `dict` / `Mapping` / `Any`。

## 非目标

- 不实现跨页选择、批量删除、业务分组规则或 Core 直接写数据库。

## 交付状态

- Contracts / SDK 与 Core / UI 两个实现子任务均已通过独立 Spec + Quality Review。
- 正式设计、`API-021`、`TC-069`、实施 / 执行 / 追踪文档、work item evidence / report / review input 与相关 `.factory/memory/` 已同步。
- 合并目标集 `120 passed`，目标 Ruff / diff / JSON / docs 结构校验通过；全量 unit 有 2 个与本任务无关的版本 README 漂移失败。
- 独立整体 review 已 `approved`（99/100），通用实现已提交并由 Contracts 0.4.3 / SDK 0.4.4 对外发布；不声明具体业务模块 E2E 完成。

# CR-018 Hosted UI managed_dataset 批量字段修改

- 状态：HUMAN_APPROVED / READY_FOR_COMMIT（独立整体 review 99/100；保留范围外版本文档漂移 concern）
- 类型：CR
- 优先级：P1
- 估算：2.5 人/天
- 关联 ID：`CR-018`, `REQ-012`, `NFR-012`, `API-021`, `TASK-036`, `TC-069`
- 提出日期：2026-07-10
- 来源：`/Users/uroborus/PythonProject/ctrip_crawler/docs/04-project-development/04-design/core-hosted-datatable-multi-select-bulk-update-request.md`

## 变更动机

- 模块 Hosted UI 的 `managed_dataset` 业务表需要在当前页勾选一条或多条记录，并把选定字段一次修改为同一值。
- `SkyDataTable` 已支持多选和读取选中行，但 Hosted UI schema、CRUD toolbar 与 SDK scanner 尚未暴露通用批量编辑能力。
- Core 不应理解账号、任务分组或具体数据库更新规则；模块 handler 继续通过 `ctx.db` 完成业务校验与批量写入。

## 变更范围

- Contracts 增加 `DataTable.selection_mode`、`crud.bulk_update_handler` 与 `crud.toolbar.bulk_update`。
- SDK scanner 校验批量处理器引用、固定签名、具体主键数组类型和 payload 类型。
- Core Renderer 复用现有 `form.update_columns` 打开空白批量编辑表单，传递 `primary_keys` 与 `payload`。
- 单条编辑 / 删除只在恰好选中一行时可用；行内动作继续只作用于点击行。
- 成功后清除选择并刷新；失败保留页面和选择并显示原始业务错误。

## 非目标

- 不新增 Core 数据库批量更新 API，不让 Core 直接修改 `managed_dataset`。
- 不支持跨分页保留选择。
- 不新增第二套 toolbar 参数表单或 `bulk_update_columns`。
- 不把账号、手机号、任务分组或公共组语义放入 Core。

## 完成判定

- `TC-069` 覆盖 Contracts、SDK scanner、Core 同步 / 异步路径与多选 UI 状态。
- 旧页面省略新字段时继续保持单选和原 CRUD 行为。
- 目标 pytest、ruff、全量 unit 与 `git diff --check` 通过。

## 当前实现与 Gate

- Task 1 Contracts / SDK 已通过独立 Spec + Quality Review：`82 passed`，Quality `100/100`。
- Task 2 Core / UI 已通过独立 Spec + Quality Review：`38 passed`，Quality `98/100`。
- Task 3 合并目标集 `120 passed`，目标 Ruff、`git diff --check`、project JSON 与 docs-stratego 结构校验通过。
- 全量 unit 为 `1132 passed, 2 failed`；失败来自当前 HEAD 的 SDK / 应用版本与 README 漂移，不涉及 `CR-018` 目标文件，且本任务禁止修改版本。完整证据见 `.factory/workitems/CR-018/evidence/verification.md`。
- 独立整体 review 已 `approved`（99/100），用户已于 2026-07-10 明确确认进入 Contracts / SDK 版本升级和 PyPI 发布流程；当前通用实现可提交，但尚未发布，且未接入具体业务模块 E2E。

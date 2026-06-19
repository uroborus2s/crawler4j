# TASK-030 建立 Hosted UI toolbar 批量导入契约

- 状态：DONE
- 负责人：Codex
- 优先级：P1
- 估算：1.5 人/天
- 关联 ID：`TASK-030`, `CR-016`, `REQ-010`, `API-019`, `TC-060`

## 目标

- 为 Hosted UI 页面和 `DataTable` 增加 toolbar actions schema。
- 定义 `open_import_dialog`、`ui_action`、`workflow` 三类 toolbar 动作。
- 固化 import payload 和 import result 的 Contracts / SDK 校验边界。

## 范围

- Contracts：补 Hosted UI schema helper、import payload/result 类型约定和规范化逻辑。
- SDK：补 v2 scanner / manifest lock / `check full` 校验。
- Core：补 schema 读取和非法动作拒绝基础。
- 文档：同步开发者指南和设计契约。

## 非目标

- 不实现导入弹窗 UI。
- 不实现 Excel/CSV 解析。
- 不实现模块业务暂存表。

## 验收标准

- 页面和 `DataTable` 都能声明 toolbar actions。
- `open_import_dialog` 必须声明 `target_type` 和 `submit`。
- `submit.type` 仅允许 `ui_action` 或 `workflow`。
- SDK/Core 能拒绝未知动作类型、缺失目标、缺失提交动作和指向不存在的 `@ui_action`。
- 单元测试和 `ruff check` 通过。

## 实现记录

- 2026-06-19 已在 `crawler4j-contracts` 的 Hosted UI schema helper 中加入 `ToolbarSchema`、`ToolbarActionSchema`、`OpenImportDialogActionSchema`、`ImportDialogSubmitSchema`、`ImportDialogLimitsSchema`、`HostedImportPayload`、`HostedImportResult` 等契约。
- `normalize_page_schema()` 和内联 `DataTable` schema 已支持 `toolbar.actions[]` 规范化，并拒绝未知 action / 缺失 submit / 非法 source type / 非法限制值。
- SDK v2 scanner 已校验 toolbar action 指向的 `@ui_action` / `@workflow` 是否存在，并校验导入提交 `@ui_action` 必须接受 `(context, import_payload)` 或声明的 `payload_param`。
- 验证：`test_hosted_ui_card.py`、`test_contracts_exports.py`、`test_v2_scanner_diagnostics.py` 已覆盖 schema 与扫描诊断。

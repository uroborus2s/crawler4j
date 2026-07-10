# Task 1 Review Input

## 范围

- Task：Contracts 与 SDK bulk update 契约
- Brief：`.factory/workitems/CR-018/task-briefs/task-1-contracts-sdk.md`
- 需求：`.factory/workitems/CR-018/brief.md` 与用户指定的外部 bulk update request

## Diff

- Contracts：`hosted_ui.py` 新增 selection mode、bulk toolbar / handler 与组合校验。
- SDK：`v2_scanner.py` 新增 bulk 配置、引用、严格签名与类型诊断。
- Tests：`test_hosted_ui_card.py`、`test_v2_scanner_diagnostics.py`。

## Evidence

- `.factory/workitems/CR-018/evidence/task-1.md`
- RED：`24 failed, 51 passed`；补充边界 RED：`1 failed, 1 passed`。
- GREEN：`76 passed`；目标 ruff 与 diff check 通过。

## Spec Review 重点

- `selection_mode` 是否严格位于来源要求的 `DataTable` 顶层，而不是 `crud` 内。
- toolbar 省略 / False / True 缺 handler 语义是否正确。
- bulk handler 的固定参数名、类型诊断和旧 CRUD 兼容是否完整。
- `primary_keys` 的“具体元素类型”是否被测试和实现准确表达。

## 风险与未决

- 主线程预审怀疑当前 diff 把 `selection_mode` 加入了 `DataTableCrudSchema`，与来源示例的 DataTable 顶层字段不一致；需独立 reviewer 判定。
- 当前任务未覆盖 Core Renderer；该部分不应作为 task 1 缺口。

# Task 1 实现报告

Status: READY_FOR_REVIEW

## Implemented

- 扩展 DataTable/CRUD TypedDict 与 normalizer：DataTable 顶层加入 `selection_mode`，CRUD 加入 `bulk_update_handler`、`toolbar.bulk_update`。
- 所有 DataTable 的 `selection_mode` 省略时规范化为 `single`，只接受 `none/single/multi`；CRUD 内同名字段作为未知字段拒绝。
- 保留 `toolbar.bulk_update` 的“省略”与显式 `False` 差异，并校验批量 handler 所需的 `primary_key`、非空 `form.update_columns`。
- 扩展 `_validate_page_crud_handlers`，诊断批量 handler 配置、`@ui_action` 引用、严格 `(context, primary_keys, payload)` 签名与宽泛参数类型。
- `primary_keys` 仅接受恰好一个具体元素类型的 `list[...]` / `List[...]`；拒绝同模块 TypeVar 及 AST tuple 多参数，同时保留自定义具体类型。
- 保持既有 create/update/delete handler 的验证路径不变。

## RED/GREEN Tests

- RED：目标测试首次运行 exit code `1`，`24 failed, 51 passed`。
- 补充 RED：空 `selection_mode` 边界 exit code `1`，`1 failed, 1 passed`。
- GREEN：目标测试 exit code `0`，`76 passed`。
- Spec Review 项 1 RED：Contracts 文件 exit code `1`，`6 failed, 28 passed`；GREEN：`34 passed`。
- Spec Review 项 2 RED：scanner 定向测试 exit code `1`，`3 failed, 10 passed, 35 deselected`；GREEN：`13 passed, 35 deselected`。
- 最终 GREEN：目标测试 exit code `0`，`82 passed`。
- Lint：目标四文件 ruff exit code `0`，`All checks passed!`。

## Spec Review response

- Item 1（Important）：核实 DataTable 既有消费契约后确认反馈正确；已把 `selection_mode` 从 CRUD 完整迁移至 DataTable 顶层，并补无 CRUD 默认值回归测试。
- Item 2（Important）：核实 AST slice 与模块 TypeVar 行为后确认反馈正确；已拒绝 tuple slice 和同模块 TypeVar，同时用自定义 `AccountId` 正例防止误伤具体类型。

## Files changed

- `packages/crawler4j-contracts/src/crawler4j_contracts/hosted_ui.py`
- `packages/crawler4j-sdk/src/v2_scanner.py`
- `packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py`
- `packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py`
- `.factory/workitems/CR-018/evidence/task-1.md`
- `.factory/workitems/CR-018/reports/task-1.md`

## Evidence

- `.factory/workitems/CR-018/evidence/task-1.md`

## Report

- `.factory/workitems/CR-018/reports/task-1.md`

## Self-review

- 变更限制在任务允许的 Contracts、SDK scanner、目标测试及 task 1 证据/报告文件。
- 批量 handler 使用独立的首参 `context` 严格校验，未收紧既有 create/update/delete 首参行为。
- `primary_keys` 只允许恰好一个非 TypeVar 的具体元素类型，payload 复用既有宽泛容器拒绝边界。
- 本实现者未作 approved 结论；当前结果为 `ready_for_review`。

## Concerns

- 无 task 1 范围内已知阻塞；按上层明确边界未修改 docs、memory、ledger，Core/UI 集成不在本任务验证范围。

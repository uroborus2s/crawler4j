# CR-018 Task 1 Review Response

## Fixed

### CR-018-SPEC-001

Fixed. `selection_mode` 已从 CRUD 移到 DataTable 顶层；所有 DataTable 省略时规范化为 `single`，CRUD 内错误嵌套被拒绝。

Verified:

- Contracts RED：`6 failed, 28 passed`。
- Contracts GREEN：`34 passed`。
- 最终目标测试：`82 passed`。

### CR-018-SPEC-002

Fixed. `primary_keys` 现在只接受恰好一个非 TypeVar 的具体元素类型；模块 TypeVar 与多参数 `list/List` 被拒绝，`List[str]` / `List[int]` 和自定义具体类型继续通过。

Verified:

- Scanner RED：`3 failed, 10 passed, 35 deselected`。
- Scanner GREEN：`13 passed, 35 deselected`。
- 最终 ruff：`All checks passed!`。

## Re-review

- Spec Review：`APPROVED`。
- Quality Review：`approved`，`100 / 100`，无 Critical / Important / Minor。

### CR-018-OVERALL-001

Fixed. `API-021` 完整章节已移到连续完整的 `API-019` 表格之后、`API-009` 之前；契约内容未改变。

Verified:

- docs-stratego source validate：exit code `0`，`pages=86`。
- `git diff --check`：exit code `0`。
- 原整体 reviewer re-review：`approved`，`99 / 100`，`next_gate_status=pending_human_confirmation`。

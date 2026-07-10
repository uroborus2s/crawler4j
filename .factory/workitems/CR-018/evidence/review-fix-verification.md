# CR-018 Task 1 Review Fix Verification

- Contracts 修复：RED `6 failed, 28 passed` -> GREEN `34 passed`。
- Scanner 修复：RED `3 failed, 10 passed, 35 deselected` -> GREEN `13 passed, 35 deselected`。
- 合并目标测试：`82 passed in 0.27s`，exit code `0`。
- 目标 ruff：`All checks passed!`，exit code `0`。
- `git diff --check`：通过。
- Spec reviewer：`APPROVED`。
- Quality reviewer：`approved`，`100 / 100`。

## CR-018-OVERALL-001 整体 Review 修复验证（2026-07-10）

- 反馈核实：成立。`API-021` 标题原先出现在 `API-019` 表格的 `动作类型` 与 `导入来源` 两组行之间，导致后半段批量导入行在语义上归入 `API-021`。
- 修复范围：仅移动 `API-021` 完整章节到 `API-019` 最后一行 `关联项` 之后、`API-009` 标题之前；移除移动后遗留的表格内空行。未修改 API-021 契约内容。
- 区段归属检查：
  - `API-019` 标题位于第 64 行，连续表格结束于第 83 行 `REQ-010...TASK-034` 关联项。
  - `API-021` 标题位于第 85 行，独立表格结束于第 102 行 `REQ-012...TASK-036` 关联项。
  - `API-009` 标题位于第 104 行。
- `uvx --from docs-stratego docs-stratego source validate --repo-path .`：沙箱内首次 exit code `2`（uv cache 权限）；获准环境最终复验 exit code `0`，结果 `crawler4j: home_access=public pages=86 contracts=0 docs_root=.../crawler4j/docs`。
- `git diff --check`：exit code `0`，输出为空。
- 结论：`CR-018-OVERALL-001` 已按要求修复并验证，当前最多为 `ready_for_review`。

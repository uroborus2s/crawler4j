# 任务 3 简报：文档、证据与记忆收口

## 工作项

- 工作项：`CR-018`
- 父任务：`TASK-036`
- 状态：`approved`
- 依赖：任务 1、任务 2 已提供真实 RED / GREEN 与目标测试结果

## 目标

把通用 bulk update 契约、实现事实、`TC-069` 结果和追踪状态同步到正式文档、work item ledger 与 `.factory/memory/`，不复制业务模块规则。

## 设计、接口、UI、测试

- 设计方案：将外部来源压缩为本仓 Core / Contracts / SDK 通用设计。
- 接口：登记 `API-021`，与 `API-006` / `API-008` 的 owner 边界一致。
- UI：N/A；本任务只记录任务 2 已验证的 UI 事实。
- 测试：运行合并目标集、全量 unit、目标 ruff、diff check 和 JSON 校验，记录真实结果。

## 允许修改

- `docs/04-project-development/03-requirements/prd.md`
- `docs/04-project-development/04-design/hosted-ui-datatable-bulk-update-design.md`
- `docs/04-project-development/04-design/api-design.md`
- `docs/04-project-development/05-development-process/implementation-plan.md`
- `docs/04-project-development/05-development-process/execution-log.md`
- `docs/04-project-development/06-testing-verification/test-plan.md`
- `docs/04-project-development/10-traceability/requirements-matrix.md`
- `docs/04-project-development/10-traceability/interface-matrix.md`
- `docs/04-project-development/10-traceability/document-index.md`
- `.factory/workitems/CR-018/`
- `.factory/workitems/changes/CR-018-hosted-ui-managed-dataset-bulk-update.md`
- `.factory/workitems/implementation/TASK-036-managed-dataset-bulk-field-update.md`
- `.factory/memory/`

## 禁止修改

- Python 实现与测试、发布版本、外部 `ctrip_crawler` 仓库。

## 验证命令

```bash
QT_QPA_PLATFORM=offscreen uv run pytest packages/crawler4j/tests/unit -q -p no:cacheprovider
uv run ruff check packages/crawler4j-contracts/src/crawler4j_contracts/hosted_ui.py packages/crawler4j-sdk/src/v2_scanner.py packages/crawler4j/src/core/mms/ui/managed_page_renderer.py packages/crawler4j/src/ui/components/data_table.py packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py packages/crawler4j/tests/unit/test_ui/test_data_table.py
git diff --check
uv run python -m json.tool .factory/project.json
```

期望：所有命令 exit code 0；若全量测试有非本变更失败，必须记录精确失败并保持未完成状态。

## 输出与状态

- 写最终验证到 `evidence/verification.md`。
- 写实现汇总到 `reports/implementation.md`。
- 生成 `reviews/code-review-input.md`。
- 更新 ledger 与相关 memory，状态最多为 `ready_for_review`。

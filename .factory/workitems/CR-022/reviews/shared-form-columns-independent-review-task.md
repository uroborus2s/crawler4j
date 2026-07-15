# CR-022 Shared Form Columns Independent Review Task

你是独立 reviewer。不要读取实现者会话历史，只读取以下文件化输入包与当前 diff；你未参与本增量实现。

## Inputs

- Work item: `CR-022`
- Review type: incremental task-level Spec Review + Quality Review
- Requirements: `.factory/workitems/CR-022/brief.md` 的 `REQ-022-007`、`AC-022-015..018`、`NFR-022-VIS`
- Plan: `.factory/workitems/CR-022/plan.md` 的“任务 2A”
- Implementer report: `.factory/workitems/CR-022/reports/shared-form-columns-implementer-report.md`
- TDD evidence: `.factory/workitems/CR-022/evidence/shared-form-columns-tdd.md`
- Diff package: 当前 unstaged `git diff` 与新增的本 review input/report/evidence 文件
- Relevant implementation: `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py`
- Relevant tests: `packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py`
- Relevant docs: `docs/04-project-development/04-design/hosted-ui-form-field-events.md`、`module-hosted-ui-framework.md`、`docs/03-developer-guide/v0.4.0/ui-and-data-table.md`

## Job

1. 核对三逻辑列是否形成六个共享物理列，label/input 分别位于 `0/2/4` 与 `1/3/5`。
2. 核对标签以全角冒号结尾、右对齐且垂直居中，输入物理列 stretch 且 widget 横向扩展。
3. 核对同逻辑列多行共享 label 右边缘和 input 左边缘，并确认测试不是只验证实现细节而遗漏可见行为。
4. 核对默认单列、row-major、35 字段/滚动/固定按钮/屏幕约束，以及 create/update/default/on_change/reset 回归不变。
5. 核对本增量没有修改 Contracts schema、SDK、消费模块、版本或加入业务特化。
6. 核对 requirements、plan、evidence、docs 和 memory 同步。
7. 运行你认为必要的独立命令，并按 review rubric 输出 Critical / Important / Minor、review score 与 gate；reviewer 不得把任务标记为 done。

输出写入 `.factory/workitems/CR-022/reviews/shared-form-columns-independent-review.md`。

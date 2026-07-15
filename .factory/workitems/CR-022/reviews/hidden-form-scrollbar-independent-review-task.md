# CR-022 Hidden Form Scrollbar Independent Review Task

你是独立 reviewer。不要读取实现者会话历史，只读取以下文件化输入包与当前 diff；你未参与本增量实现。

## Inputs

- Work item: `CR-022`
- Review type: incremental task-level Spec Review + Quality Review
- Requirements: `.factory/workitems/CR-022/brief.md` 的 `REQ-022-008`、`AC-022-019`、`NFR-022-SCROLL`
- Plan: `.factory/workitems/CR-022/plan.md` 的“任务 2B”
- Implementer report: `.factory/workitems/CR-022/reports/hidden-form-scrollbar-implementer-report.md`
- Verification evidence: `.factory/workitems/CR-022/evidence/hidden-form-scrollbar-final-verification.md`
- Diff package: 当前 unstaged `git diff` 与新增 review package 文件
- Relevant implementation: `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py`
- Relevant tests: `packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py`
- Relevant docs: `docs/03-developer-guide/v0.4.0/ui-and-data-table.md`、`docs/04-project-development/04-design/hosted-ui-form-field-events.md`

## Job

1. 核对 CRUD 长 Form 的水平/垂直滚动槽是否均隐藏。
2. 核对隐藏策略是否仍保留非零滚动范围以及键盘/程序化滚动，不把“隐藏”误实现为“不可滚动”。
3. 核对确认/取消按钮继续位于滚动区外。
4. 核对 create/update/default/on_change/reset、多列布局和提交契约未变化。
5. 核对既有大 gap 测试的固定屏幕几何是否只是消除环境漂移，没有掩盖产品缺陷。
6. 核对未修改 Contracts、SDK、schema、消费模块、版本或加入业务特化。
7. 独立运行必要测试，按 rubric 输出 Critical / Important / Minor、review score 与 gate；不得把任务标记为 done。

输出写入 `.factory/workitems/CR-022/reviews/hidden-form-scrollbar-independent-review.md`。

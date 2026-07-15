# Independent Review Task

你是 CR-022 的独立 reviewer。不要读取实现者会话历史，只读取以下文件化输入与当前 diff。

## Inputs

- Work item: `CR-022`
- Review type: task-level Spec Review + Quality Review
- Requirements: `.factory/workitems/CR-022/brief.md`
- Task brief: `.factory/workitems/CR-022/task-briefs/TASK-041.md`
- Plan and final contract: `.factory/workitems/CR-022/plan.md`
- Implementer report: `.factory/workitems/CR-022/reports/TASK-041-implementer-report.md`
- Verification evidence: `.factory/workitems/CR-022/evidence/targeted-verification.md`
- Ledger: `.factory/workitems/CR-022/ledger.jsonl`
- Diff package: current unstaged `git diff` plus untracked files listed in the implementer report/work item
- Relevant architecture: `docs/04-project-development/04-design/hosted-ui-form-field-events.md`, `module-hosted-ui-framework.md`, `api-design.md`

## Job

1. 核对 AC-022-001..014 和职责边界。
2. 审计 handle 不可伪造性、module/page/session/form/TTL/close 绑定、错误 oracle 和敏感值日志。
3. 审计并发乱序、隔离 action context 和 handler failure 行为。
4. 核对 create default、update row 优先级、falsy exactness、reset state、默认单列、35 字段三列/12 行、滚动固定按钮和窄屏降列测试。
5. 核对 Contracts/SDK/Core/renderer/tool registry 契约一致性和未声明 `on_change` 的兼容性。
6. 核对文档、版本与本地联调说明。
7. 按 review rubric 输出 Critical / Important / Minor、真实命令结果、score 和 gate；不得把 approved 写成 done。

输出写入 `.factory/workitems/CR-022/reviews/TASK-041-independent-review.md`。

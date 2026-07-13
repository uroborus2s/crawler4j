# Independent Review Task

你是独立 reviewer。不要读取实现者会话历史，只重新读取以下文件化输入包和当前工作区差异。

## Inputs

- Work item：`CR-021`
- Review type：任务级 Spec Review + Quality Review
- Requirements：`.factory/workitems/CR-021/brief.md`
- Task brief：`.factory/workitems/CR-021/task-briefs/task-1-environment-management-ui.md`
- Root cause：`.factory/workitems/CR-021/reports/root-cause.md`
- Implementer report：`.factory/workitems/CR-021/reports/task-1-implementation.md`
- Verification evidence：`.factory/workitems/CR-021/evidence/completion-verification.md`
- Ledger：`.factory/workitems/CR-021/ledger.jsonl`
- Diff package：当前 `git diff -- .factory/memory .factory/workitems/CR-021 packages/crawler4j/src packages/crawler4j/tests`
- Architecture constraints：UI → Manager → Provider → VirtualBrowserClient；环境外部 ID 以 `Environment.external_id` / handle browser_id 为事实源；不允许 UI 直接调用厂商 API。

## Job

1. 核对全部已确认需求，尤其是当前池过滤语义、随机入口删除、清缓存只删 Cache/Code Cache 且不吞错误、external_id 列。
2. 核对架构、并发锁、错误传播、UI provider 可见性和测试充分性。
3. 核对验证证据与文档/memory 同步。
4. 可独立运行必要的聚焦测试，但不得修改实现代码。
5. 按 100 分 rubric 输出 Critical / Important / Minor。
6. 将结论写入 `.factory/workitems/CR-021/reviews/task-1-independent-review.md`。

## 必填元数据

- reviewer_type：`independent_subagent`
- reviewer_id：使用你的 canonical task name
- reviewer_independence_evidence：说明未参与实现、未继承会话历史、仅读取上述输入包与当前差异
- review_status：`approved` 或 `changes_requested`
- next_gate_status：通过时为 `pending_human_confirmation`，否则 `changes_requested`
- review_score：按 rubric 给分

Reviewer 不得把 work item 标记为 done，也不要修改 ledger；由主 agent 根据 review 结论同步。

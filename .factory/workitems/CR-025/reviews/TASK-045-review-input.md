# TASK-045 独立评审输入

- Work item：`CR-025`
- Task：`TASK-045`
- Review type：高风险跨层 Spec Review + Quality Review
- Requirements：`.factory/workitems/CR-025/brief.md`
- Plan：`.factory/workitems/CR-025/plan.md`
- Task brief：`.factory/workitems/CR-025/task-briefs/TASK-045.md`
- Implementer report：`.factory/workitems/CR-025/reports/TASK-045.md`
- Verification evidence：`.factory/workitems/CR-025/evidence/TASK-045.md`
- Ledger：`.factory/workitems/CR-025/ledger.jsonl`
- Diff package：当前 `git diff` 与未跟踪 `.factory/workitems/CR-025/**`

## 评审重点

1. sync/async/awaitable 是否单次调用，旧返回是否兼容。
2. context 是否来自同次候选计算并只传给选中 workflow；固定/创建/空候选语义是否明确。
3. JSON-safe/65536 字节边界、错误脱敏和候选异常语义是否正确。
4. 租约后是否继续复核宿主安全状态且不重跑 provider。
5. SDK scanner/manifest、Contracts/type hints、runtime surface 与文档是否一致。

Reviewer 只读，不修改实现、文档、memory、ledger、Git 或外部系统。

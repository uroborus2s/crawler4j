# TASK-044 独立评审输入

- Work item：`CR-024`
- Task：`TASK-044`
- Review type：任务级 Spec Review + Quality Review
- Requirements：`.factory/workitems/CR-024/brief.md`
- Task brief：`.factory/workitems/CR-024/task-briefs/TASK-044.md`
- Implementer report：`.factory/workitems/CR-024/reports/TASK-044.md`
- Verification evidence：`.factory/workitems/CR-024/evidence/TASK-044.md`
- Ledger：`.factory/workitems/CR-024/ledger.jsonl`
- Diff package：`git diff` 与当前未跟踪的 `examples/cheese_automation/**`

## 评审边界

- Reviewer 只读，不修改任何文件。
- 核对 REQ-017、REQ-018、REQ-019、NFR-015 与 AC-024-001 至 AC-024-005。
- 核对现有 `core-native-v2` 资源打包能力是否足以承载脚本，避免虚构 crawler4j 直接执行 Cheese 的能力。
- 核对测试是否证明 full 校验、workflow 脚本定位、官方 API 脚本契约和 ZIP 资源包含关系。
- 核对 README 是否明确真实设备 E2E 边界。

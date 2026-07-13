# TASK-040 独立评审输入

## 评审类型

任务级 Spec Review + Quality Review。

## 只读输入包

- 需求：`.factory/workitems/CR-020/brief.md`
- 任务简报：`.factory/workitems/CR-020/task-briefs/TASK-040.md`
- 实现报告：`.factory/workitems/CR-020/reports/TASK-040.md`
- 验证证据：`.factory/workitems/CR-020/evidence/TASK-040.md`
- 接口实测：`.factory/workitems/CR-020/evidence/virtualbrowser-cookie-api-probe.md`
- 工作项 ledger：`.factory/workitems/CR-020/ledger.jsonl`
- Diff：当前工作树中 CR-020 相关源文件、测试、文档和 memory 变更。

## 必查项

1. `cookies` 是否严格代表完整目标集合，未传 Cookie 是否会删除。
2. VirtualBrowser 请求/响应和 `expires/expirationDate` 是否符合实测证据。
3. 持久化、运行态、重启与同环境锁是否形成原子链。
4. stop/start 后 TaskContext page/context 和 browser tools 是否换代。
5. 工具是否只在 full surface 注册，是否泄漏 Provider API。
6. API Key 和 Cookie value 是否可能进入日志、异常或结果。
7. 测试是否覆盖额外 Cookie、空集合、幂等、失败、并发和 CDP 关闭等待。

## N/A

- UI：本任务不新增 UI，只扩展模块运行时工具面。
- SDK/Contracts：使用既有 `TaskContext.tools.call` 语义，不新增 scanner 或 manifest 契约。
- 其他 Provider：当前需求只要求 VirtualBrowser；BaseProvider 默认显式不支持。

# TASK-041 Hosted UI 公共字段 change 与 Form Reset

- 工作项：`CR-022`
- 状态：`implemented_validation_pending`
- 上游：`.factory/workitems/CR-022/{brief,plan}.md`
- 流水账：`.factory/workitems/CR-022/ledger.jsonl`

## 目标

跨 Contracts、SDK、Core runtime 与 renderer 交付统一字段 change 事件、安全 Form Handle 和通用 `ui.form.reset`，并以定向、相关全量、静态与安全负向测试证明职责边界和兼容性。

## 允许修改

- `packages/crawler4j-contracts/`
- `packages/crawler4j-sdk/src/v2_scanner.py`
- `packages/crawler4j/src/core/{atm/runtime_capabilities.py,mms/ui/}`
- 上述实现对应的 `packages/crawler4j/tests/`
- CR-022 必要正式文档、work item 和 memory 索引。

## 禁止修改

- 消费模块、平台/设备模板、发布配置和版本号。
- 业务默认值、模板分支、preset cases、handler effect 协议。
- 不属于本任务的用户改动。

## 实施与验证

1. 按 plan 任务 1 写 Contracts/SDK RED 并转绿。
2. 按 plan 任务 2 写 registry/runtime/renderer RED 并转绿。
3. 更新文档和证据，运行定向、邻近、全量、ruff、lock、diff 与特化扫描。
4. 独立 review 和新鲜验证通过后才能进入本地提交。

目标命令和期望结果以 `.factory/workitems/CR-022/plan.md` 为准；所有命令必须记录真实输出和 exit code。

# CR-018 / TASK-036 实现与收口报告

## 状态

- Status：`DONE_WITH_CONCERNS`
- Work item state：`ready_for_review`
- Verification：`partial`
- Needs：独立整体 review；范围外版本 README 漂移处理或风险接受
- Commit：未执行

## 交付摘要

- Contracts：DataTable 顶层 `selection_mode`、CRUD `bulk_update_handler` / `toolbar.bulk_update` 与配置归一化。
- SDK：bulk handler 引用、精确签名、具体主键列表和具体 payload 类型诊断。
- Core / UI：选择模式透传、批量 toolbar、单条 / 行内动作边界、保序类型敏感主键去重、同步 / 异步调用与查询前清选择。
- 正式文档：新增通用设计，更新 `REQ-012` / `NFR-012`、`API-021`、实施 / 执行、`TC-069` 与追踪矩阵。
- 工厂收口：更新 CR / TASK 卡、相关 memory、verification evidence、implementation report、review input 和 append-only ledger。

## 评审与验证

- Task 1 Spec + Quality：approved，`82 passed`，`100/100`。
- Task 2 Spec + Quality：approved，`38 passed`，`98/100`。
- Task 3 合并目标集：`120 passed`。
- Ruff、`git diff --check`、project JSON、docs-stratego：exit code `0`。
- 全量 unit：`1132 passed, 2 failed`；失败为当前 HEAD 的 SDK / 应用版本与 README 漂移，不属于 `CR-018`，且任务禁止修改版本。

## Scope 与边界

- 未修改 Python / 测试 / 版本以外的 Task 3 允许文件；Task 1 / 2 的 Python 与测试改动由其各自实现者完成。
- 未写入或复制具体业务模块的账号、分组、公共组或数据库规则。
- 未声明具体业务模块 handler 已接线、业务表已更新、真实站点 E2E 通过、人工确认或发布完成。
- 实现者未自批 `approved`，未提交 Git commit。

## Concerns

1. 全量 unit 非全绿：SDK `0.4.3` / README `0.4.2`、应用 `0.4.29` / 根 README 旧版本导致 2 个版本一致性测试失败。证据显示与 `CR-018` diff 无关；仍需由独立整体 reviewer 判断是否阻塞当前 gate。
2. 通用框架只验证 Core 到模块 handler 的参数边界；具体业务模块的校验、`ctx.db` 批量写入和 E2E 是后续模块工作。

# 软件开发流程

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** Tech Lead | 开发 | QA | 发布负责人
**上游输入：** `docs/04-project-development/03-requirements/` | `docs/04-project-development/04-design/` | `.factory/project.json`
**下游输出：** `implementation-plan.md` | `execution-log.md` | `docs/04-project-development/06-testing-verification/test-plan.md`
**关联 ID：** `TASK-016`, `REQ-005`, `NFR-004`
**最后更新：** 2026-04-02

## 1. 生命周期和输入输出

| 阶段 | 至少输入 | 至少输出 |
|---|---|---|
| 调研 / 需求 | 章程、输入证据、PRD | 已校验需求、风险和边界 |
| 设计 | 需求分析、技术画像 | 架构、模块边界、接口契约 |
| 实施 | 设计、实施方案、测试计划 | 代码、文档、验证结果、执行记录 |
| 发布 | 测试结论、版本规则、验收结论 | 发布说明、交付包、部署与运行文档 |
| 运维 / 演进 | 发布结果、运行事实、问题复盘 | 运行手册、演进计划、memory 同步 |

## 2. 实施阶段标准执行环

1. 先确认当前工作项和受影响范围。
2. 只读取完成当前动作所必需的设计、实现和文档事实。
3. 实施变更后，立即同步受影响的正式文档和 `.factory/memory/`。
4. 运行最小必要验证，再决定是否扩大回归范围。
5. 把输入、输出、未决问题和验证结果登记到 `execution-log.md`。
6. 涉及代码的事项必须经过 PR 闭环后再视为完成。

## 3. PR 与 Gate 规则

- 代码类工作默认执行 `factory-pr-start`、`factory-pr-review`、`factory-pr-merge`。
- 文档类工作即使不改代码，也必须满足“入口正确、索引同步、链接有效、memory 同步”。
- 进入发布前，至少复验测试计划、发布说明、验收检查清单和部署/运行文档。

## 4. 文档同步规则

| 变更类型 | 至少同步这些文档 |
|---|---|
| 导航或目录结构调整 | `docs/index.md`、`document-index.md`、`.factory/memory/doc-map.md` |
| 架构/接口变化 | `technical-selection.md`、`system-architecture.md`、`module-boundaries.md`、`api-design.md` |
| 实施或任务状态变化 | `implementation-plan.md`、`execution-log.md`、必要的测试/发布文档 |
| 发布与运维边界变化 | `release-notes.md`、`acceptance-checklist.md`、`delivery-package.md`、`deployment-guide.md`、`operations-runbook.md` |

## 5. 停止条件

- 当前事实不足以继续，需要真实环境、外部凭据或用户确认。
- 需要破坏性操作，但用户未授权。
- 发现正式文档、代码和验证结果三者之间存在明显冲突，必须先修事实漂移。

## 6. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-02 | 将占位页重写为正式软件开发流程文档 | Codex |

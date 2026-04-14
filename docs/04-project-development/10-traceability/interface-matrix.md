# 接口追踪矩阵

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 架构 | 开发 | QA | 发布负责人 | 运维
**上游输入：** `docs/04-project-development/04-design/api-design.md` | `requirements-matrix.md` | `docs/04-project-development/06-testing-verification/test-plan.md` | `docs/04-project-development/07-release-delivery/version-governance.md`
**下游输出：** `docs/04-project-development/07-release-delivery/acceptance-checklist.md` | `docs/04-project-development/08-operations-maintenance/operations-runbook.md`
**关联 ID：** `API-001`, `API-002`, `API-003`, `API-004`, `TASK-019`
**最后更新：** 2026-04-02

## 1. 接口责任矩阵

| 接口 ID | 契约内容 | 提供方 | 消费方 | 版本 / 来源 | 验证方式 | 运维责任 |
|---|---|---|---|---|---|---|
| `API-001` | Root App Entry Contract | Root app metadata | 维护者 / 打包流程 | `packages/crawler4j/pyproject.toml`、`src.ui.app:main` | workspace 入口检查、UI smoke、PyInstaller build | Core 维护者 |
| `API-002` | Module Runtime Contract | Core + Module runtime | 最终用户 / 模块维护者 | `module.yaml`、模块根 `__init__.py`、`ModuleAssembler` | 单元/集成测试、关键工作流验证；真实站点 E2E 仍待完成 | Core 维护者 |
| `API-003` | SDK / Contracts Package Contract | `crawler4j_sdk`、`crawler4j_contracts` | 模块开发者 | `packages/crawler4j-sdk/pyproject.toml`、`packages/crawler4j-contracts/pyproject.toml`、CLI 入口 | build、CLI help、脚手架测试 | SDK / Core 维护者 |
| `API-004` | Release Metadata Contract | Release metadata | 发布负责人 / 维护者 | `packages/crawler4j/pyproject.toml`、运行时版本服务、Git tag、子包版本 | 版本对照检查、release notes 校验 | 发布负责人 |

## 2. 当前接口风险

| 接口 | 风险 | 当前状态 |
|---|---|---|
| `API-002` | 真实站点 E2E 尚未完成，运行契约仍缺最终现场验证 | 未闭环 |
| `API-004` | 正式发布尚未切版，交付包仍需绑定实际发布批次 | 未闭环 |

## 3. 使用规则

- 当接口契约发生变化时，先改 `api-design.md`，再同步本矩阵。
- 需要判断“某个接口由谁负责、怎么验、出了问题谁接手”时，先看本矩阵，再进入实现或运维文档。

## 4. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-02 | 将占位页重写为正式接口责任矩阵 | Codex |

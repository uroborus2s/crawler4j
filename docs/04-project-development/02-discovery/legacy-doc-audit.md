# 旧文档审计与收敛策略

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 架构 | 开发 | QA | 发布负责人 | 文档维护者
**上游输入：** 现有 `docs/` 树 | 当前代码与已验证结果
**下游输出：** `docs/04-project-development/10-traceability/document-index.md` | `docs/index.md`
**关联 ID：** `TASK-006`, `TASK-009`, `TASK-010`, `REQ-005`
**最后更新：** 2026-03-28

## 1. 结论先行

crawler4j 当前的人类文档已经收敛为四大模块：

1. `docs/01-getting-started/`
   提供项目定位、文档地图和最小阅读顺序。
2. `docs/02-user-guide/`
   提供接手入口和协作者说明。
3. `docs/03-developer-guide/`
   提供开发者指南；在本项目中它就是 module 开发指南本体。
4. `docs/04-project-development/`
   提供治理、需求、设计、计划、测试、发布、运维与追踪等内部正式文档。

## 2. 当前分层策略

| 目录/入口 | 当前角色 | 处理策略 |
|---|---|---|
| `docs/01-getting-started/` | 入门层 | 提供阅读路径，不承载重复正文 |
| `docs/02-user-guide/` | 协作者 | 承载接手入口与协作者说明 |
| `docs/03-developer-guide/` | 模块开发者 / 做模块集成的 Core 成员 | 承载开发者指南本体 |
| `docs/04-project-development/` | 架构 / 开发 / QA / 发布 | 承载当前正式项目开发文档并持续演进 |
| 已退出正式入口的过渡目录 | `docs/project-process/`、`docs/model-development/` | 完成职责回收后删除，避免重复导航 |
| 已删除旧归档 | 旧 SRS、旧设计、旧测试、旧用户专题与历史辅助资料 | 不再保留，避免与当前事实冲突 |

## 3. 当前已清理的问题

| 问题 | 当前处理 |
|---|---|
| 顶层入口长期漂移，难以判断哪层才是正式入口 | 根 `docs/index.md` 统一回到四大模块目录树 |
| `reference-*` 容易被误读成当前事实 | 旧归档已整体删除 |
| “开发者指南”里同时混入 module 指南和 Core 维护入口 | 第三部分直接由 `docs/03-developer-guide/` 这套 module 指南构成；Core 维护入口迁到 `docs/04-project-development/08-operations-maintenance/core-maintainer-guide.md` |
| 旧 Quick Start 和用户说明仍占当前入口 | 已退出当前主路径，仅在归档层保留 |
| 空壳页、纯草稿页和 TODO 占位页继续污染目录 | 已删除无正文价值的脑暴页、空演进页和归档 TODO 页 |
| 已闭环任务的流水账仍留在正式目录 | 已删除重复的 WBS、任务分解和执行日志页，细粒度过程痕迹回收到 `.factory/` |

## 4. 冲突裁决规则

当前文档冲突时，按以下优先级裁决：

1. 当前代码与可重复验证结果
2. 当前过程文档与模块开发指南
## 5. 后续维护规则

- 不再保留会和当前事实并存的旧归档正文。
- 若旧结论仍然有效，应直接回写到当前文档，而不是保留第二份历史说明。
- 新增、删除或移动文档时，先执行 `factory-dispatch docs-index-refresh --project "."`，再更新根 `docs/index.md`、`docs/04-project-development/10-traceability/document-index.md` 和 `.factory/memory/doc-map.md`。

## 6. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-28 | 将旧编号目录与过渡入口迁回四大模块结构，并刷新索引口径 | Codex |
| 2026-03-26 | 建立旧文档审计与收敛策略 | Codex |

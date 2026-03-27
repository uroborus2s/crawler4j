# 旧文档审计与收敛策略

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 架构 | 开发 | QA | 发布负责人 | 文档维护者
**上游输入：** 现有 `docs/` 树 | 当前代码与已验证结果
**下游输出：** `docs/traceability/document-index.md` | `docs/index.md` | `docs/archive/`
**关联 ID：** `TASK-006`, `TASK-009`, `TASK-010`, `REQ-005`
**最后更新：** 2026-03-28

## 1. 结论先行

crawler4j 当前的人类文档已经收敛为三层：

1. `项目过程文档`
   入口在 `docs/project-process/`，正文事实主要分布在 `docs/00-governance/` 到 `docs/07-operations/`、`docs/09-evolution/` 和 `docs/traceability/`。
2. `Model 开发指南`
   入口在 `docs/08-handover/module-developer-guide/`，面向外部模块开发者。
3. `历史归档`
   统一放到 `docs/archive/`，只保留追溯价值，不再作为默认事实入口。

## 2. 当前分层策略

| 目录/入口 | 当前角色 | 处理策略 |
|---|---|---|
| `docs/project-process/` | Core 过程文档入口 | 面向 Core 团队的默认阅读面 |
| `docs/00-governance/` ~ `docs/07-operations/`、`docs/09-evolution/`、`docs/traceability/` | 当前正式过程文档 | 持续演进，和代码事实同步 |
| `docs/08-handover/module-developer-guide/` | 当前模块开发主入口 | 由 model 开发指南维护 |
| `docs/08-handover/index.md`、`docs/08-handover/user-guide.md` | 跨角色接手入口 | 只保留跳转和边界说明 |
| `docs/archive/reference-srs/` | 旧需求 / 架构 / 规格细节库 | 保留为深度参考 |
| `docs/archive/reference-design/` | 旧技术设计细节库 | 保留为深度参考 |
| `docs/archive/reference-tests/` | 旧测试设计细节库 | 保留为深度参考 |
| `docs/archive/reference-user-guide/` | 旧用户 / 运维专题文档 | 保留为历史参考 |
| `docs/archive/reference-module-dev/` | 旧模块开发辅助资料 | 保留素材与截图，不再当主入口 |
| `docs/archive/reference-sdk/`、`docs/archive/reference-architecture/` | 补充说明层 | 只在需要追历史上下文时引用 |

## 3. 当前已清理的问题

| 问题 | 当前处理 |
|---|---|
| 新旧文档混在同一主导航里 | 根 `docs/index.md` 改为“项目过程文档 / Model 开发指南 / 历史归档”三层入口 |
| `reference-*` 容易被误读成当前事实 | 已统一迁入 `docs/archive/` |
| 模块开发内容和 Core 过程文档互相污染 | 模块开发指南独立为目录化章节，Core 入口改由 `docs/project-process/` 负责 |
| 旧 Quick Start 和用户说明仍占当前入口 | 已退出当前主路径，仅在归档层保留 |

## 4. 冲突裁决规则

当“历史归档”和“当前代码 / 当前文档”冲突时，按以下优先级裁决：

1. 当前代码与可重复验证结果
2. 当前过程文档与模块开发指南
3. `docs/archive/` 历史资料

## 5. 后续维护规则

- 不再把新的当前事实写进 `docs/archive/`。
- 若某个归档结论仍然有效，应把结论回写到当前文档，再把归档保留为背景资料。
- 新增、删除或移动文档时，先更新所属目录 `index.md`，再更新根 `docs/index.md` 和 `docs/traceability/document-index.md`。

## 6. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-28 | 将文档体系重组为项目过程文档、Model 开发指南和历史归档三层 | Codex |
| 2026-03-26 | 建立旧文档审计与收敛策略 | Codex |

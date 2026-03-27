# 项目过程文档

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** Core 维护者 | 开发 | QA | 发布负责人  
**上游输入：** `docs/index.md` | 当前代码与已验证结果 | `.factory/project.json`  
**下游输出：** `docs/traceability/document-index.md` | 相关阶段文档与交接文档  
**最后更新：** 2026-03-28  

## 1. 这部分文档解决什么问题

本部分面向维护 `crawler4j` Core 仓库的人。它负责回答三类问题：

1. 当前代码到底实现了什么。
2. Core 团队应该按什么顺序阅读、开发、验证和发布。
3. 改动某个区域后，哪些正式文档和 `.factory/memory/` 必须同步。

本部分不承担外部模块作者培训职责。模块作者请直接阅读 [Model 开发指南入口](../model-development/index.md)。历史资料与旧专题文档统一放在 [历史归档](../archive/index.md)。

## 2. 推荐阅读顺序

1. [Core 接手与日常维护](./core-maintainer-guide.md)
2. [当前真实状态分析](../01-discovery/current-state-analysis.md)
3. [技术选型与工程规则](../03-solution/technical-selection.md)
4. [系统架构](../03-solution/system-architecture.md)
5. [模块边界](../03-solution/module-boundaries.md)
6. [实施方案](../04-delivery/implementation-plan.md)
7. [质量门与文档导航规则](../05-quality/quality-gates.md)
8. [版本治理规则](../06-release/version-governance.md)
9. [部署与运行说明](../07-operations/deployment-guide.md)
10. [文档索引](../traceability/document-index.md)

## 3. 当前结构

| 区域 | 主要内容 | 主要读者 |
|---|---|---|
| `docs/project-process/` | Core 维护入口、阅读路径、同步规则 | Core 维护者 / Tech Lead |
| `docs/00-governance/` ~ `docs/07-operations/` | 当前治理、设计、交付、质量、发布、运行事实 | 开发 / QA / 发布 |
| `docs/08-handover/user-guide.md` | 接手入口与跨角色跳转 | 新维护者 |
| `docs/model-development/index.md` | 模块开发指南独立入口 | 模块开发者 |
| `docs/archive/` | 旧 SRS、旧设计、旧测试、旧用户说明 | 需要追溯历史细节的读者 |
| `docs/traceability/` | 文档索引与需求追踪 | 架构 / QA / 文档维护者 |

## 4. 维护规则

- 当前事实以代码、可重复验证结果和当前过程文档为准。
- 旧专题文档只作为背景参考，不再作为默认阅读入口。
- 变更被接受后，同步代码、`docs/`、测试或验证记录，以及 `.factory/memory/`。
- 根 `docs/index.md` 只维护三层入口：项目过程文档、Model 开发指南、历史归档。
- 任何新增 Markdown 文档目录都必须补 `index.md`，并同步更新 `docs/traceability/document-index.md`。

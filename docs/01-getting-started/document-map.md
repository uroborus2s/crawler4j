# 文档地图

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 新维护者 | Core 开发 | 模块开发者 | QA
**上游输入：** `docs/index.md` | 当前正式文档树
**下游输出：** `docs/02-user-guide/user-guide.md` | `docs/03-developer-guide/index.md` | `docs/04-project-development/08-operations-maintenance/core-maintainer-guide.md`
**关联 ID：** `DOC-101`, `DOC-102`, `DOC-103`
**最后更新：** 2026-04-02

## 1. 四大模块及职责边界

| 模块 | 回答的问题 | 主要读者 |
|---|---|---|
| `docs/01-getting-started/` | 这是个什么项目，我应该先看什么 | 新维护者 / 协作者 |
| `docs/02-user-guide/` | 如何安装、配置、使用和管理宿主应用 | 宿主使用者 / 管理员 / 协作者 |
| `docs/03-developer-guide/` | 如何开发、调试、交付和迁移模块 | 模块开发者 / 做模块集成的 Core 成员 |
| `docs/04-project-development/` | 项目如何治理、设计、实施、验证、发布、运维和追踪 | Tech Lead / Dev / QA / 发布负责人 |

## 2. 3 分钟快速阅读路径

### Core 维护者

1. [接手入口](../02-user-guide/user-guide.md)
2. [Core 接手与日常维护](../04-project-development/08-operations-maintenance/core-maintainer-guide.md)
3. [当前真实状态分析](../04-project-development/02-discovery/current-state-analysis.md)
4. [技术选型与工程规则](../04-project-development/04-design/technical-selection.md)
5. [系统架构](../04-project-development/04-design/system-architecture.md)
6. [实施方案](../04-project-development/05-development-process/implementation-plan.md)
7. [执行记录](../04-project-development/05-development-process/execution-log.md)

### 模块开发者

1. [接手入口](../02-user-guide/user-guide.md)
2. [开发者指南总览](../03-developer-guide/index.md)
3. [01 概念与约束](../03-developer-guide/01-concepts/index.md)
4. [02 快速开始](../03-developer-guide/02-quickstart/index.md)
5. [03 项目结构与契约](../03-developer-guide/03-project-structure/index.md)
6. [04 模块开发](../03-developer-guide/04-development/index.md)
7. [06 交付与验收](../03-developer-guide/06-delivery/index.md)
8. [Shim 迁移](../03-developer-guide/08-migration/01-shim-migration.md)

### 发布 / 运维

1. [发布与交付概览](../04-project-development/07-release-delivery/index.md)
2. [验收检查清单](../04-project-development/07-release-delivery/acceptance-checklist.md)
3. [交付包清单](../04-project-development/07-release-delivery/delivery-package.md)
4. [部署与运行说明](../04-project-development/08-operations-maintenance/deployment-guide.md)
5. [运行手册](../04-project-development/08-operations-maintenance/operations-runbook.md)

### 宿主使用者 / 管理员

1. [接手入口](../02-user-guide/user-guide.md)
2. [安装说明](../02-user-guide/installation.md)
3. [配置说明](../02-user-guide/configuration.md)
4. [使用说明](../02-user-guide/usage.md)
5. [管理员指南](../02-user-guide/admin-guide.md)

## 3. 使用原则

- 先确定读者身份，再进入对应模块，不在多个目录之间来回跳读。
- `docs/02-user-guide/` 不解释实现细节，`docs/03-developer-guide/` 不承担发布与运维职责，`docs/04-project-development/` 不替代用户手册。
- 对实现事实有争议时，以当前代码、验证结果和 `docs/04-project-development/` 中的正式文档为准。

## 4. 维护规则

- 根 `docs/index.md` 只维护四大模块的目录树、页面路径和访问级别。
- 各目录 `index.md` 负责说明本目录解决什么问题、谁应该来这里看、推荐阅读顺序是什么。
- 新增、删除或移动 Markdown 页面后，要同步更新 `docs/04-project-development/10-traceability/document-index.md` 和 `.factory/memory/doc-map.md`。
- 不再保留 `docs/project-process/`、`docs/model-development/` 这类过渡顶层入口，避免再次偏离四大模块结构。

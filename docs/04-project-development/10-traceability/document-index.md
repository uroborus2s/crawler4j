# 文档索引

**项目名称：** 蛛行演略（crawler4j）
**负责人：** 当前仓库维护者
**最后更新：** 2026-03-31

## 1. 当前正式文档结构

当前正式的人类文档收敛为四大模块：

| 模块 | 作用 | 主要读者 |
|---|---|---|
| `docs/01-getting-started/` | 项目概览、快速开始、文档地图和入门路径 | 新维护者 / 协作者 |
| `docs/02-user-guide/` | 接手入口、安装、配置和使用说明 | 新维护者 / 协作者 |
| `docs/03-developer-guide/` | 开发者指南；在本项目中即 module 开发指南 | 模块开发者 / 做模块集成的 Core 成员 |
| `docs/04-project-development/` | 治理、需求、设计、计划、测试、发布、运维和追踪等正式内部文档 | Tech Lead / Dev / QA / 发布 |

## 2. 关键入口

| 目录/文档 | 作用 | 主要读者 |
|---|---|---|
| `docs/index.md` | 全站目录树、页面路径和访问权限的唯一声明入口 | 全体协作者 |
| `docs/01-getting-started/project-overview.md` | 说明项目定位、当前组成与进入方式 | 新维护者 / 协作者 |
| `docs/01-getting-started/quick-start.md` | 提供最小启动步骤、常用命令和继续阅读路径 | 新维护者 / 协作者 |
| `docs/01-getting-started/document-map.md` | 四大模块职责边界与推荐阅读顺序 | 新维护者 / 协作者 |
| `docs/02-user-guide/user-guide.md` | 跨角色接手入口 | 新维护者 / 协作者 |
| `docs/02-user-guide/installation.md` | 宿主安装方式、应用数据目录与安装校验 | 宿主使用者 / 协作者 |
| `docs/02-user-guide/configuration.md` | 系统设置、模块设置与执行配置说明 | 宿主使用者 / 协作者 |
| `docs/02-user-guide/usage.md` | 页面导航、正式安装与 DevLink 使用路径 | 宿主使用者 / 协作者 |
| `docs/03-developer-guide/index.md` | 开发者指南总览；即 module 开发指南入口 | 模块开发者 |
| `docs/04-project-development/08-operations-maintenance/core-maintainer-guide.md` | Core 接手、日常维护与同步规则 | Core 维护者 / 新成员 |
| `docs/04-project-development/02-discovery/` | 输入证据、现状分析、旧文档收敛策略 | 架构 / 开发 / QA |
| `docs/04-project-development/04-design/` | 当前架构、模块边界、接口契约和工程规则 | 架构 / 开发 |
| `docs/04-project-development/05-development-process/` | 当前实施计划与交付边界 | Tech Lead / Dev / QA |
| `docs/04-project-development/06-testing-verification/` | 测试计划、质量门、一致性审查 | QA / Dev / 发布 |
| `docs/04-project-development/07-release-delivery/` | 发布说明、版本治理 | 发布负责人 / Tech Lead |
| `docs/04-project-development/08-operations-maintenance/` | 部署与运行说明 | 运维 / Dev |
| `docs/04-project-development/10-traceability/` | 文档索引与需求追踪 | 架构 / QA / 文档维护者 |

## 3. 推荐阅读路径

### Core 维护者

1. [文档中心](../index.md)
2. [文档地图](../../01-getting-started/document-map.md)
3. [Core 接手与日常维护](../08-operations-maintenance/core-maintainer-guide.md)
4. [当前真实状态分析](../02-discovery/current-state-analysis.md)
5. [系统架构](../04-design/system-architecture.md)
6. [实施方案](../05-development-process/implementation-plan.md)
7. [质量门与文档导航规则](../06-testing-verification/quality-gates.md)

### 模块开发者

1. [接手入口](../../02-user-guide/user-guide.md)
2. [开发者指南总览](../../03-developer-guide/index.md)
3. [01 概念与约束](../../03-developer-guide/01-concepts/index.md)
4. [02 快速开始](../../03-developer-guide/02-quickstart/index.md)
5. [3.2 `module.yaml` 清单契约](../../03-developer-guide/03-project-structure/02-module-manifest.md)
6. [4.1 编写 TaskScript](../../03-developer-guide/04-development/01-taskscript.md)
7. [4.2 编写 Workflow](../../03-developer-guide/04-development/02-workflow.md)
8. [4.3 CLI 命令与 UI 配置](../../03-developer-guide/04-development/03-cli-and-ui.md)
9. [4.4 Core 能力清单](../../03-developer-guide/04-development/04-core-capabilities.md)
10. [4.5 Core 注入能力 API 参考](../../03-developer-guide/04-development/05-api-reference.md)
11. [4.6 模块开发最佳实践](../../03-developer-guide/04-development/06-best-practices.md)
12. [05 调试](../../03-developer-guide/05-debugging/index.md)
13. [06 交付与验收](../../03-developer-guide/06-delivery/index.md)

## 4. 维护规则

- 根 `docs/index.md` 只维护四大模块的目录树、页面路径和访问权限。
- 任何新增、删除或移动页面，都要先执行 `factory-dispatch docs-index-refresh --project "."`，再更新本文件和 `.factory/memory/doc-map.md`。
- `docs/project-process/` 与 `docs/model-development/` 不再作为正式入口保留。
- 当前事实以代码、当前文档和可重复验证结果为准。

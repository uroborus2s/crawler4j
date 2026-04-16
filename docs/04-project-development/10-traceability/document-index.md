# 文档索引

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 新维护者 | 模块开发者 | Tech Lead | QA | 发布负责人 | 运维
**上游输入：** `docs/index.md` | 当前正式文档树 | 文档治理整改结果
**下游输出：** `docs/01-getting-started/document-map.md` | `.factory/memory/doc-map.md` | 角色阅读路径
**关联 ID：** `DOC-106`, `TASK-014`, `TASK-019`, `TASK-020`
**最后更新：** 2026-04-08

## 1. 当前正式文档结构

当前正式的人类文档收敛为四大模块：

| 模块 | 作用 | 主要读者 |
|---|---|---|
| `docs/01-getting-started/` | 项目概览、快速开始、文档地图和入门路径 | 新维护者 / 协作者 |
| `docs/02-user-guide/` | 接手入口、安装、配置、使用说明和管理员指南 | 宿主使用者 / 管理员 / 协作者 |
| `docs/03-developer-guide/` | 开发者指南；在本项目中即 module 开发指南 | 模块开发者 / 做模块集成的 Core 成员 |
| `docs/04-project-development/` | 治理、需求、设计、计划、测试、发布、运维和追踪等正式内部文档 | Tech Lead / Dev / QA / 发布 |

## 2. 按角色快速阅读

### 新维护者

1. [根入口](../../index.md)
2. [文档地图](../../01-getting-started/document-map.md)
3. [接手入口](../../02-user-guide/user-guide.md)
4. [Core 接手与日常维护](../08-operations-maintenance/core-maintainer-guide.md)
5. [当前真实状态分析](../02-discovery/current-state-analysis.md)
6. [实施方案](../05-development-process/implementation-plan.md)

### 模块开发者

1. [开发者指南总览](../../03-developer-guide/index.md)
2. [01 概念与约束](../../03-developer-guide/01-concepts/index.md)
3. [02 快速开始](../../03-developer-guide/02-quickstart/index.md)
4. [03 项目结构与契约](../../03-developer-guide/03-project-structure/index.md)
5. [04 模块开发](../../03-developer-guide/04-development/index.md)
6. [06 交付与验收](../../03-developer-guide/06-delivery/index.md)

### 发布 / 运维

1. [发布与交付概览](../07-release-delivery/index.md)
2. [验收检查清单](../07-release-delivery/acceptance-checklist.md)
3. [交付包清单](../07-release-delivery/delivery-package.md)
4. [部署与运行说明](../08-operations-maintenance/deployment-guide.md)
5. [运行手册](../08-operations-maintenance/operations-runbook.md)

## 3. 阶段文档入口

| 阶段 | 关键入口 | 作用 |
|---|---|---|
| 治理与调研 | `01-governance/`、`02-discovery/` | 说明背景、范围、风险和现状证据 |
| 需求与设计 | `03-requirements/`、`04-design/` | 说明为什么做、怎么设计、接口和边界是什么 |
| 实施与验证 | `05-development-process/`、`06-testing-verification/` | 说明如何推进、怎么验证、最近执行了什么 |
| 发布与运维 | `07-release-delivery/`、`08-operations-maintenance/` | 说明什么时候能发、如何交付、如何运行和接手 |
| 追踪与演进 | `09-evolution/`、`10-traceability/` | 说明模式级改进、需求覆盖和接口责任 |

## 4. 维护规则

- 根 `docs/index.md` 是唯一的全站导航源；本文件负责“入口解释”和“按角色索引”，不重复维护整棵页面树。
- 任何新增、删除或移动页面，都要同步更新根 `docs/index.md`、本文件和 `.factory/memory/doc-map.md`。
- `docs/project-process/` 与 `docs/model-development/` 不再作为正式入口保留。
- 当前事实以代码、当前文档和可重复验证结果为准。

## 5. 最近同步

- 2026-04-15：`packages/crawler4j-sdk/README.md`、`docs/03-developer-guide/04-development/01-taskscript.md`、`04-core-capabilities.md`、`05-api-reference.md` 与相关设计文档已同步 `TaskContext.tools` 统一工具接口。
- 2026-04-08：`docs/03-developer-guide/04-development/03-cli-and-ui.md`、`docs/03-developer-guide/05-debugging/01-devlink-and-debug.md` 与 `docs/04-project-development/06-testing-verification/test-plan.md` 已同步 `core:data_table` 的 `declare_ui` / `create_handler` / `update_handler` 契约和 DevLink 调试刷新事实。

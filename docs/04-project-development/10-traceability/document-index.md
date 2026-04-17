# 文档索引

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 新维护者 | 模块开发者 | Tech Lead | QA | 发布负责人 | 运维
**上游输入：** `docs/index.md` | 当前正式文档树 | 文档治理整改结果
**下游输出：** `docs/01-getting-started/document-map.md` | `.factory/memory/doc-map.md` | 角色阅读路径
**关联 ID：** `DOC-106`, `TASK-014`, `TASK-019`, `TASK-020`
**最后更新：** 2026-04-17

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
2. [快速开始](../../03-developer-guide/quickstart.md)
3. [核心概念](../../03-developer-guide/core-concepts.md)
4. [模块结构](../../03-developer-guide/module-structure.md)
5. [构建模块](../../03-developer-guide/build-modules.md)
6. [交付模块](../../03-developer-guide/shipping.md)

### 发布 / 运维

1. [发布与交付概览](../07-release-delivery/index.md)
2. [验收检查清单](../07-release-delivery/acceptance-checklist.md)
3. [`ctrip` 真实站点 E2E 收口方案](../06-testing-verification/ctrip-real-site-e2e-closeout.md)
4. [交付包清单](../07-release-delivery/delivery-package.md)
5. [部署与运行说明](../08-operations-maintenance/deployment-guide.md)
6. [运行手册](../08-operations-maintenance/operations-runbook.md)

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

- 2026-04-17：`docs/04-project-development/06-testing-verification/` 新增 `ctrip-real-site-e2e-closeout.md`，把真实站点 E2E 的前置条件、Phase A/B/C 执行顺序、证据要求与放行条件收敛为单一正式入口；发布/运维阅读路径已同步纳入该页。
- 2026-04-17：`docs/03-developer-guide/` 已从旧多层目录重排为产品式平铺结构，首页改为正式开发者入口页，`Quick Start`、`Guide`、`Reference`、调试、交付与排障全部一级直达；旧迁移页与对应入口已下线。
- 2026-04-17：开发者指南中的 CLI 命令面已再次对齐到当前本地 `crawler4j-sdk` 实现，统一使用 `module/task/workflow/page/data-table/env-selector/config/package/release/host/check` 分组命令；文档不再固定 `crawler4j-sdk==某个版本`，`reference-sdk-and-cli.md` 的总表与最小安全顺序已补成完整可复制命令。
- 2026-04-17：`docs/03-developer-guide/` 已根据 6 个“小白模块开发者”子 agent 的两轮苛刻复核继续补强：新增 `--repo` 占位值说明、`module set default-workflow`、`ui:DashboardPage` / `ui/__init__.py` 导出关系、`TaskResult.data` / `run_subtask()` 真实语义、CLI 宿主桥接与宿主 UI 安装的互斥路径、DevLink/ATM 最短调试判据，以及 `core:data_table` / 调试 / 排障分叉清单；最终 6 个子 agent 全部给出 PASS。
- 2026-04-17：`docs/02-user-guide/configuration.md`、`docs/04-project-development/04-design/module-config-runtime-data-contract.md` 与开发者指南相关章节已统一模块配置 / 运行态 / 单次运行内状态 / 数据表边界；`core:data_table` schema / records 当前只读写 `data.db`，运行时代码不包含旧 `state.db.kv_store` 自动迁移逻辑。

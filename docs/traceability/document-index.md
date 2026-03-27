# 文档索引

**项目名称：** 蛛行演略（crawler4j）
**负责人：** 当前仓库维护者
**最后更新：** 2026-03-28

## 1. 当前正式文档结构

当前正式的人类文档分成两个主要阅读面，外加一个历史归档层：

| 入口 | 作用 | 主要读者 |
|---|---|---|
| `docs/project-process/` | Core 团队的过程文档入口 | Core 维护者 / 开发 / QA / 发布 |
| `docs/model-development/` | 模块开发独立入口 | 外部模块开发者 / 做模块集成的 Core 成员 |
| `docs/archive/` | 历史参考层，不作为默认事实入口 | 需要追溯旧设计和旧说明的读者 |

## 2. 项目过程文档目录

| 目录/文档 | 作用 | 主要读者 |
|---|---|---|
| `docs/project-process/index.md` | Core 阅读路径与维护边界 | Core 维护者 |
| `docs/project-process/core-maintainer-guide.md` | 接手、日常维护、同步规则 | Core 维护者 / 新成员 |
| `docs/00-governance/` | 项目边界、治理规则 | 管理者 / Tech Lead |
| `docs/01-discovery/` | 输入证据、现状分析、旧文档收敛策略 | 架构 / 开发 / QA |
| `docs/02-requirements/` | 当前需求、分析、校验 | 产品 / 架构 / 开发 / QA |
| `docs/03-solution/` | 当前架构、模块边界、接口契约和工程规则 | 架构 / 开发 |
| `docs/04-delivery/` | 实施计划、任务拆解、执行节奏 | Tech Lead / Dev / QA |
| `docs/05-quality/` | 测试计划、质量门、一致性审查 | QA / Dev / 发布 |
| `docs/06-release/` | 发布说明、版本治理 | 发布负责人 / Tech Lead |
| `docs/07-operations/` | 部署与运行说明 | 运维 / Dev |
| `docs/08-handover/index.md`、`docs/08-handover/user-guide.md` | 跨角色接手入口 | 新维护者 / 协作者 |
| `docs/09-evolution/` | 演进与复盘入口 | 文档维护者 / Tech Lead |
| `docs/traceability/` | 文档索引与需求追踪 | 架构 / QA / 文档维护者 |

## 3. Model 开发指南目录

| 目录/文档 | 作用 |
|---|---|
| `docs/model-development/index.md` | 模块开发独立入口与阅读路径 |
| `docs/08-handover/module-developer-guide/index.md` | 模块开发总览 |
| `docs/08-handover/module-developer-guide/01-concepts/` | 系统地图与真实约束 |
| `docs/08-handover/module-developer-guide/02-quickstart/` | 环境准备与首个模块 |
| `docs/08-handover/module-developer-guide/03-project-structure/` | 结构、入口与 `module.yaml` |
| `docs/08-handover/module-developer-guide/04-development/` | TaskScript、Workflow、CLI 与 UI |
| `docs/08-handover/module-developer-guide/05-debugging/` | DevLink 与调试链路 |
| `docs/08-handover/module-developer-guide/06-delivery/` | zip 安装与验收清单 |
| `docs/08-handover/module-developer-guide/07-troubleshooting/` | 常见坑位与排错 |

## 4. 历史归档映射

| 历史归档 | 当前承接位置 |
|---|---|
| `docs/archive/reference-srs/` | `docs/02-requirements/` + `docs/03-solution/` |
| `docs/archive/reference-design/` | `docs/03-solution/` |
| `docs/archive/reference-architecture/` | `docs/03-solution/system-architecture.md` |
| `docs/archive/reference-sdk/` | `docs/03-solution/api-design.md` + 模块开发指南 |
| `docs/archive/reference-tests/` | `docs/05-quality/test-plan.md` |
| `docs/archive/reference-user-guide/` | `docs/06-release/` + `docs/07-operations/` + `docs/08-handover/user-guide.md` |
| `docs/archive/reference-module-dev/` | `docs/model-development/index.md` |

## 5. 推荐阅读路径

### Core 维护者

1. [文档中心](../index.md)
2. [项目过程文档总览](../project-process/index.md)
3. [Core 接手与日常维护](../project-process/core-maintainer-guide.md)
4. [当前真实状态分析](../01-discovery/current-state-analysis.md)
5. [系统架构](../03-solution/system-architecture.md)
6. [实施方案](../04-delivery/implementation-plan.md)
7. [质量门与文档导航规则](../05-quality/quality-gates.md)

### 模块开发者

1. [Model 开发指南入口](../model-development/index.md)
2. [模块开发指南总览](../08-handover/module-developer-guide/index.md)
3. [01 概念与约束](../08-handover/module-developer-guide/01-concepts/index.md)
4. [02 快速开始](../08-handover/module-developer-guide/02-quickstart/index.md)
5. [05 调试](../08-handover/module-developer-guide/05-debugging/index.md)
6. [06 交付与验收](../08-handover/module-developer-guide/06-delivery/index.md)

## 6. 维护规则

- 根 `docs/index.md` 必须维持“项目过程文档 / Model 开发指南 / 历史归档”三层入口。
- 任何新增、删除或移动页面，都要先更新所属目录 `index.md`，再更新本文件。
- 当前事实优先级高于历史归档；归档只用于补充背景与追溯旧结论。

# 文档地图

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 新维护者 | Core 开发 | 模块开发者 | QA
**最后更新：** 2026-03-28

## 1. 四大模块

| 模块 | 作用 | 主要读者 |
|---|---|---|
| `docs/01-getting-started/` | 提供项目定位、文档地图和最小阅读路径 | 新维护者 / 协作者 |
| `docs/02-user-guide/` | 提供接手入口和协作者说明 | 新维护者 / 协作者 |
| `docs/03-developer-guide/` | 提供开发者指南；在本项目中它就是 module 开发指南本体 | 模块开发者 / 做模块集成的 Core 成员 |
| `docs/04-project-development/` | 提供治理、需求、设计、计划、测试、发布、运维和追踪等正式内部文档 | Tech Lead / Dev / QA / 发布负责人 |

## 2. 推荐阅读顺序

### Core 维护者

1. [Core 接手与日常维护](../04-project-development/08-operations-maintenance/core-maintainer-guide.md)
2. [当前真实状态分析](../04-project-development/02-discovery/current-state-analysis.md)
3. [技术选型与工程规则](../04-project-development/04-design/technical-selection.md)
4. [系统架构](../04-project-development/04-design/system-architecture.md)
5. [实施方案](../04-project-development/05-development-process/implementation-plan.md)
6. [质量门与文档导航规则](../04-project-development/06-testing-verification/quality-gates.md)
7. [文档索引](../04-project-development/10-traceability/document-index.md)

### 模块开发者

1. [接手入口](../02-user-guide/user-guide.md)
2. [开发者指南总览](../03-developer-guide/index.md)
3. [01 概念与约束](../03-developer-guide/01-concepts/index.md)
4. [02 快速开始](../03-developer-guide/02-quickstart/index.md)
5. [04 模块开发](../03-developer-guide/04-development/index.md)
6. [06 交付与验收](../03-developer-guide/06-delivery/index.md)

## 3. 维护规则

- 根 `docs/index.md` 只维护四大模块的目录树、页面路径和访问级别。
- 各目录 `index.md` 由 `factory-dispatch docs-index-refresh --project "."` 刷新，不再单独维护自定义导航。
- 新增、删除或移动 Markdown 页面后，要同步更新 `docs/04-project-development/10-traceability/document-index.md` 和 `.factory/memory/doc-map.md`。
- 不再保留 `docs/project-process/`、`docs/model-development/` 这类过渡顶层入口，避免再次偏离四大模块结构。

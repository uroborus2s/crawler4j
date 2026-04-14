# 开发者指南总览

**项目名称：** 蛛行演略（crawler4j）
**文档状态：** 已批准
**负责人：** 当前仓库维护者
**主要读者：** 模块开发者 | Core 集成人员
**上游输入：** `docs/02-user-guide/user-guide.md` | `docs/04-project-development/04-design/technical-selection.md` | `docs/04-project-development/04-design/api-design.md`
**下游输出：** `docs/03-developer-guide/*` | `docs/04-project-development/06-testing-verification/test-plan.md`
**关联 ID：** `DOC-104`, `REQ-003`, `REQ-006`
**最后更新：** 2026-04-08

## 1. 本目录解决什么问题

本目录只解决“如何开发、调试、交付和迁移模块”这件事。
它不重复解释项目治理、发布流程和运维职责，这些内容统一回到 `docs/04-project-development/`。

当前内容以 `crawler4j-sdk 1.1.x` 为准，模块侧统一通过 `ctx.tools.call(...)` 访问宿主扩展能力；旧 `DataService`、`ctx.db.storage / accounts / tasks` 和专用 `ctx.db` 字段写法都已移除。
当前 `core:data_table:<view_id>` 页面也已进入正式契约：宿主会在页面刷新时重新执行模块根导出的 `declare_ui`，并可继续路由 `create_handler` / `update_handler` 到模块本地同步 hook。

## 2. 第一天阅读包

1. [01 概念与约束](01-concepts/index.md)
2. [02 快速开始](02-quickstart/index.md)
3. [03 项目结构与契约](03-project-structure/index.md)
4. [04 模块开发](04-development/index.md)
5. [05 调试](05-debugging/index.md)
6. [06 交付与验收](06-delivery/index.md)

## 3. 按任务定位

| 目标 | 先看哪里 | 再看哪里 |
|---|---|---|
| 创建新模块 | `02-quickstart/` | `03-project-structure/` |
| 理解 `module.yaml`、入口和目录结构 | `03-project-structure/` | `04-development/` |
| 编写 TaskScript / Workflow / UI | `04-development/` | `05-debugging/` |
| 做 DevLink 联调 | `05-debugging/01-devlink-and-debug.md` | `07-troubleshooting/01-common-pitfalls.md` |
| 打包并做 zip 安装验收 | `06-delivery/` | `02-user-guide/usage.md` |
| 升级旧模块到最新薄壳入口 | `08-migration/01-shim-migration.md` | `04-development/03-cli-and-ui.md` |

## 4. 阅读纪律

- 先读章节概览页，再进入正文页，不要直接跳到单个 API 片段。
- 实现边界、宿主入口和发布事实以 `docs/04-project-development/04-design/` 为准。
- 发现“开发指南写法”和当前 SDK/Contracts 行为不一致时，先修正式文档，再继续交付。

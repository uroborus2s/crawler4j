# 开发者指南 0.4.0

这一版只面向 `crawler4j 0.4.0` / `core-native-v2` 模块。

> 版本绑定：0.4.x SDK、0.4.x Contracts 和 Core 0.4.0 是同一条破坏性升级线，只服务 `core-native-v2`。0.4.x SDK 不兼容 0.3.x 的命令、模板或开发模式；维护 0.3.x 模块必须切回 0.3.x SDK / Contracts。

主路径只有一条：

- 用装饰器声明运行能力
- 由 SDK 扫描并生成 manifest lock
- 由 Core 在每个 task/env 启动时创建独立对象图
- workflow 只接收宿主注入对象
- 页面操作使用 `@page_action` 纯函数
- 数据表和命名查询使用 `@data_table` / `@data_query`

0.4.0 新模块只按本目录的装饰器路径编写。历史契约只在迁移和排障页面作为旧概念出现，不作为新版 SDK 的兼容入口。

## 推荐阅读顺序

1. [核心概念](./core-concepts.md)
2. [模块结构](./module-structure.md)
3. [装饰器与对象装配](./decorators-and-object-assembly.md)
4. [数据契约](./data-contracts.md)
5. [快速开始](./quickstart.md)
6. [UI 与数据表](./ui-and-data-table.md)
7. [构建模块](./build-modules.md)
8. [调试](./debugging.md)
9. [交付](./shipping.md)
10. [从 v0.3.0 迁移](./migration-from-v0.3.0.md)
11. [排障](./troubleshooting.md)
12. [SDK 与 CLI 参考](./reference-sdk-and-cli.md)
13. [Core 能力参考](./reference-core-capabilities.md)

## 记住这些边界

- `module.yaml.runtime_api` 写 `core-native-v2`
- 模块运行时代码只依赖 `crawler4j-contracts`
- `crawler4j-sdk` 只负责 CLI、模板、扫描、校验、manifest lock 和打包辅助
- 0.4.x SDK 不提供 0.3.x 开发命令；不要在 0.4.0 模块里使用 `task create`、`env-selector create`、`hook create` 或 `data resource/view/seed create`
- Core 是唯一运行时 owner
- workflow 不接收 `parameters`
- 普通参数只属于 `@component(parameters=...)` 的对象创建
- Core 为每个 task/env 创建独立对象图，不共享业务对象实例
- 数据库唯一入口仍是 `ctx.db`
- `ctx.tools.call("db.*")` 不是正式能力
- `created_at`、`updated_at`、`create_at`、`update_at` 是阻断诊断字段，不要声明为模块业务列

如果你维护的是 0.3.x 稳定模块，请读 `../v0.3.0/` 并使用 0.3.x SDK / Contracts，不要把本目录的 0.4.x 工具链套回稳定版。

## v1 到 v2 声明方式对照

| 能力 | 0.3.x / `core-native-v1` | 0.4.0 / `core-native-v2` |
|---|---|---|
| 任务 | `tasks/*.py` 导出 `TASK` / `execute` | `tasks/*.py` 承载 `@page_action` 纯函数 |
| 工作流 | `workflows/*.py` 导出 `WORKFLOW` / `run` | `@workflow` 类，构造函数只接收注入对象 |
| Workflow 参数 | `module.yaml.workflows[].parameters[]` | 移到具体 `@component(parameters=...)` |
| 数据表 / 查询 | `module.yaml.data` + `data/sql` | `@data_table` / `@data_query` + manifest lock |
| 页面 | `pages/*.py` 导出 `PAGE` / handler | 页面仍由宿主 schema 渲染，页面动作接入 `@page_action` |
| Hook / 环境选择器 | `hooks/`、`env_selectors/` 固定导出 | 0.4.x SDK 不提供旧命令；如需等价能力必须走 0.4.0 专属 API 设计 |

# 开发者指南 0.4.0

这一版面向 `core-native-v2` 开发版模块。

> 状态：设计预览。当前源码中的 SDK CLI、Core scanner、Contracts 导出和宿主安装链仍以 `core-native-v1` 为可执行主线；本目录中的 v2 命令、装饰器和验收步骤是 0.4.0 目标契约，不是当前可直接运行的操作手册。

主路径只有一条：

- 用装饰器声明运行能力
- 由 SDK 扫描并生成 manifest lock
- 由 Core 在每个 task/env 启动时创建独立对象图
- workflow 只接收宿主注入对象
- 页面操作使用 `@page_action` 纯函数
- 数据表和命名查询使用 `@data_table` / `@data_query`

0.4.0 新模块发布后只按本目录的装饰器路径编写。历史契约只在迁移和排障页面作为旧概念出现。

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
- Core 是唯一运行时 owner
- workflow 不接收 `parameters`
- 普通参数只属于 `@component(parameters=...)` 的对象创建
- Core 为每个 task/env 创建独立对象图，不共享业务对象实例
- 数据库唯一入口仍是 `ctx.db`
- `ctx.tools.call("db.*")` 不是正式能力
- `created_at`、`updated_at`、`create_at`、`update_at` 是阻断诊断字段，不要声明为模块业务列

如果你维护的是 0.3.x 稳定模块，请读 `../v0.3.0/`，不要把本目录的开发版契约套回稳定版。

## 当前不可执行边界

在 v2 实现落地前，下面内容均为目标行为：

- `crawler4j module init --runtime-api core-native-v2`
- `crawler4j interface/component/page-action/manifest/migrate ...`
- DevLink 直接加载 `core-native-v2` 模块
- ZIP 安装和升级 `core-native-v2` 模块
- `crawler4j-contracts` 直接导出 v2 装饰器
- Hosted UI 按钮直接声明 `page_action` 动作

当前可执行开发仍使用 [0.3.0 稳定指南](../v0.3.0/index.md)。

## v1 到 v2 声明方式对照

| 能力 | 0.3.x / `core-native-v1` | 0.4.0 目标 / `core-native-v2` |
|---|---|---|
| 任务 | `tasks/*.py` 导出 `TASK` / `execute` | `tasks/*.py` 承载 `@page_action` 纯函数 |
| 工作流 | `workflows/*.py` 导出 `WORKFLOW` / `run` | `@workflow` 类，构造函数只接收注入对象 |
| Workflow 参数 | `module.yaml.workflows[].parameters[]` | 移到具体 `@component(parameters=...)` |
| 数据表 / 查询 | `module.yaml.data` + `data/sql` | `@data_table` / `@data_query` + manifest lock |
| 页面 | `pages/*.py` 导出 `PAGE` / handler | 暂沿用 `PAGE` / handler，页面动作可接入 `@page_action` |
| Hook / 环境选择器 | `hooks/`、`env_selectors/` 固定导出 | 暂沿用固定导出；后续若装饰器化需单独设计 |

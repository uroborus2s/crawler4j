# crawler4j 模块开发者指南

为 `crawler4j` 构建轻量、可调试、可交付的业务模块。

`crawler4j` 已经通过 SDK 和 Core 抽象好了配置、任务、工作流、环境、调试、托管数据表和交付链路。模块开发者不需要再搭一套自己的平台。你的工作只有一个: 用最少的抽象，把业务流程写清楚。

模块里的持久数据现在至少要按两条语义来理解:

- 当前快照继续走 `db.list_records` / `db.replace_records` 和 `core:data_table`
- append-only 历史优先走独立审计事件通道，不再混进快照 dataset 或数据表 CRUD

## 快速入口

### 5 分钟上手

- [快速开始](quickstart.md)

### 开始开发模块

- [核心概念](core-concepts.md)
- [模块结构](module-structure.md)
- [构建模块](build-modules.md)
- [UI 与数据表](ui-and-data-table.md)

### 调试、交付与排错

- [调试模块](debugging.md)
- [交付模块](shipping.md)
- [常见问题](troubleshooting.md)

### 查手册

- [SDK 与 CLI 参考](reference-sdk-and-cli.md)
- [Core 能力参考](reference-core-capabilities.md)

## 命令与版本口径

这份指南只写当前可用命令，不再在示例里固定 `crawler4j-sdk==某个版本`。

- 获取最新 CLI:
  `uvx --from crawler4j-sdk crawler4j --help`
- 在模块项目里执行命令:
  `uv run crawler4j ...`
- 独立模块项目里的事实源:
  `crawler4j --help`
- 只有在 `crawler4j` Core 源码仓核对实现细节时，才回看
  `packages/crawler4j-sdk/src/cli/commands.py`

如果你在别处看到旧平铺命令、旧目录说明或过期版本号，不要跟着抄，统一以本章和当前 CLI 帮助输出为准。

## 这份指南适合谁

这份文档只服务两类读者:

1. 第一次写 `crawler4j` 模块的开发者
2. 需要快速查 CLI、SDK、Core 约束和交付方式的熟手

如果你是宿主使用者或维护者，优先回到用户指南或项目开发文档，不要从这里开始。

## 推荐阅读路径

### 第一次开发模块

1. [快速开始](quickstart.md)
2. [核心概念](core-concepts.md)
3. [模块结构](module-structure.md)
4. [构建模块](build-modules.md)
5. [UI 与数据表](ui-and-data-table.md)
6. [调试模块](debugging.md)
7. [交付模块](shipping.md)

### 已经会写模块，只想查手册

1. [SDK 与 CLI 参考](reference-sdk-and-cli.md)
2. [Core 能力参考](reference-core-capabilities.md)
3. [常见问题](troubleshooting.md)

## 主题导航

| 你要做什么 | 直接看哪里 |
|---|---|
| 从零创建第一个模块 | [快速开始](quickstart.md) |
| 理解模块到底是什么 | [核心概念](core-concepts.md) |
| 搞清楚目录、入口和 `module.yaml` | [模块结构](module-structure.md) |
| 写 task 和 workflow | [构建模块](build-modules.md) |
| 写页面或托管数据表 | [UI 与数据表](ui-and-data-table.md) |
| 搞清快照数据和审计历史怎么分工 | [核心概念](core-concepts.md) / [Core 能力参考](reference-core-capabilities.md) / [UI 与数据表](ui-and-data-table.md) |
| 用 DevLink / ATM 调试 | [调试模块](debugging.md) |
| 打 ZIP、安装、验收 | [交付模块](shipping.md) |
| 查 CLI 命令和 SDK 类型 | [SDK 与 CLI 参考](reference-sdk-and-cli.md) |
| 查 `db.*`、`ui.*`、`env.*` | [Core 能力参考](reference-core-capabilities.md) |
| 查高频踩坑 | [常见问题](troubleshooting.md) |

## 开发原则

这一套文档只有一个立场:

- 模块是轻量业务应用，不是二次框架
- 相同逻辑先抽到 task
- task 内部如果还有重复，再抽一层纯函数就够了
- 重约束、轻抽象，比“架构看起来高级”更重要

如果你准备好了，直接从 [快速开始](quickstart.md) 开始。

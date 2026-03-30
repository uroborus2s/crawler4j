# 项目概览

蛛行演略（`crawler4j`）当前是一个基于 Python 的桌面自动化宿主平台。它不是单一的“脚本仓库”或“模块模板仓库”，而是一个同时包含桌面 Host、Core 运行时、模块 SDK、共享契约和正式文档树的完整工作区。

## 1. 这个仓库解决什么问题

当前项目的核心目标是：

- 提供一个可运行的 PyQt 桌面宿主，用来管理环境、模块、策略和自动化作业。
- 提供 `crawler4j_sdk` 与 `crawler4j_contracts`，让模块作者按统一契约开发、调试和交付模块。
- 通过 DevLink 和 zip 安装两条链路，把“本地开发”和“正式交付”区分开。

如果只记一条，可以这样理解：

> `crawler4j` 负责承载和运行模块，模块作者交付的是符合契约的模块目录或 zip 包。

## 2. 当前仓库由哪些部分组成

| 目录/模块 | 作用 |
|---|---|
| `src/` | 桌面应用与 Core 运行时，真实入口是 `src.ui.app:main` |
| `crawler4j_sdk/` | 模块开发 SDK 与 CLI |
| `crawler4j_contracts/` | Core 与模块共享的数据结构和协议 |
| `modules/` | 当前仅保留占位说明，不再作为正式模块交付目录 |
| `docs/` | 当前正式的人类文档树 |
| `.factory/` | 软件工厂过程、记忆与追踪资产 |

## 3. 当前已经验证过的能力

基于当前仓库状态，下面这些能力已经被本地验证过：

- 根应用可以通过 `uv run start` 启动，入口与 `src.ui.app:main` 已对齐。
- `crawler4j_sdk` CLI 可以在仓内正常调用，`uv run python -m crawler4j_sdk.cli.commands --help` 已通过。
- 默认质量门 `uv run pytest -q`、`uv run ruff check .`、UI smoke 和 Root / SDK / Contracts build 已有通过记录。
- 外部模块可以通过 zip 安装到应用数据目录，并被模块管理加载。
- DevLink 调试链、模块设置持久化、模块状态持久化、自定义页面 trust gate 等关键 MMS 能力已经落地。

## 4. 进入项目前要先接受的边界

- 当前真实模块来源是应用数据目录下的安装模块和 DevLink，不是仓库根的 `modules/` 目录。
- 正式模块交付链路认的是 zip 包，不是 wheel。
- 模块最终运行在宿主 `crawler4j` 的 Python 环境里，不会自动继承模块项目自己的依赖。
- 当前主要剩余风险不是基础启动，而是 `ctrip` 真实站点 E2E 仍未完整回放。

## 5. 推荐阅读顺序

### 想先判断项目是否适合你

1. [快速开始](./quick-start.md)
2. [文档地图](./document-map.md)

### 想接手或维护宿主应用

1. [接手入口](../02-user-guide/user-guide.md)
2. [Core 接手与日常维护](../04-project-development/08-operations-maintenance/core-maintainer-guide.md)
3. [当前真实状态分析](../04-project-development/02-discovery/current-state-analysis.md)
4. [系统架构](../04-project-development/04-design/system-architecture.md)

### 想开发或联调模块

1. [接手入口](../02-user-guide/user-guide.md)
2. [开发者指南总览](../03-developer-guide/index.md)
3. [开发前准备](../03-developer-guide/02-quickstart/01-environment-setup.md)
4. [创建第一个模块](../03-developer-guide/02-quickstart/02-create-first-module.md)

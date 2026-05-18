# 模块边界

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 维护者  
**上游输入：** `system-architecture.md` | 当前代码布局  
**下游输出：** `api-design.md` | `docs/04-project-development/05-development-process/implementation-plan.md`
**关联 ID：** `MOD-001`, `MOD-002`, `MOD-003`, `MOD-004`, `MOD-005`  
**最后更新：** 2026-04-27

## `MOD-001` Root Desktop App

| 项目 | 内容 |
|---|---|
| 目录 | `packages/crawler4j/src/ui/`, `packages/crawler4j/pyproject.toml` |
| 职责 | 应用入口、主窗口、UI 组件、用户操作壳层 |
| 对外接口 | `src.ui.app:main` |
| 依赖 | `packages/crawler4j/src/core/`, PyQt6, qasync |
| 不负责 | 业务模块实现、外部模块脚手架、SDK 分发 |

## `MOD-002` Core Runtime Services

| 项目 | 内容 |
|---|---|
| 目录 | `packages/crawler4j/src/core/` |
| 职责 | 调度、模块管理、环境管理、持久化、调试、系统服务 |
| 对外接口 | 内部 Python API，由 UI 与模块运行时调用 |
| 依赖 | Playwright, SQLAlchemy, APScheduler |
| 不负责 | 模块业务逻辑本身 |

## `MOD-003` External Modules & Runtime Surface

| 项目 | 内容 |
|---|---|
| 目录 | `packages/crawler4j/modules/README.md`（仓内占位）、`<app-data>/modules`（正式安装）、DevLink 源码目录（开发调试） |
| 职责 | 定义模块根目录、`module.yaml`（含只读 `config_defaults` 初始化模板）、根 `__init__.py`、装饰器声明与宿主管理 UI 声明的运行边界 |
| 对外接口 | `interfaces/*.py` / `objects/*.py` / `workflows/*.py` / `tasks/*.py` / `data/*.py` / `pages/*.py` 的 v2 装饰器声明 |
| 依赖 | `crawler4j_contracts`, Core runtime |
| 不负责 | Core 基础设施、SDK 公共契约、宿主内部 `PyQt6` 组件实现 |

当前边界事实：

- 仓库不再保留 builtin business modules，`packages/crawler4j/modules/` 仅保留占位说明。
- 正式安装模块位于应用数据目录，开发调试模块通过 DevLink 指向源码目录。
- 模块项目自己的 `pyproject.toml` 不会被宿主应用自动安装到运行时环境中。

当前最小演进边界：

- 根 `__init__.py` 只保留普通 Python 包入口，不再承载宿主入口、`run()` 或兼容桥。
- interface、component、workflow、page action、data、page 由 Core 直接扫描固定目录并生成 v2 runtime descriptor，不再由 SDK 统一入口组装器提供。
- 模块级可变行为放在 `interfaces/`、`objects/`、`workflows/`、`tasks/`、`data/`、`pages/`，不再要求模块作者维护 `module_runtime.py`。
- 模块 UI 不再导出 `QWidget` 或 `ui:*` 页面类；模块只能通过 `pages/*.py` / `pages/<group>/*.py` 中的 `@page(...)` 声明 Hosted UI。
- 宿主允许模块使用的公开 UI 面固定为最小化 UI 框架 V1，而不是开放任意 `PyQt6` 组件能力。
- 旧模块不再作为新契约的兼容目标；升级时统一按最新模板重新初始化模块骨架。

## `MOD-004` SDK 与 Contracts

| 项目 | 内容 |
|---|---|
| 目录 | `packages/crawler4j-sdk/`, `packages/crawler4j-contracts/` |
| 职责 | `crawler4j-contracts` 提供 `TaskContext` / `TaskResult` / `TaskOutcome` / `WorkflowLifecycleInfo` / `ToolsCapability` / `DatabaseClient`、v2 装饰器与 `object_param` / `object_inject` 注解 helper 等运行时契约；`crawler4j-sdk` 提供 CLI、脚手架、校验与打包发布辅助 |
| 对外接口 | `crawler4j` CLI, Python 包 API |
| 依赖 | `crawler4j-contracts`, aiohttp, pyyaml |
| 不负责 | Root app UI、宿主运行时治理与模块业务语义 |

## `MOD-005` Docs 与 Release Surface

| 项目 | 内容 |
|---|---|
| 目录 | `docs/`, `packages/crawler4j/crawler4j.spec`, `dist/`, `build/` |
| 职责 | Markdown 文档、打包说明、历史发布产物、发布元信息 |
| 对外接口 | wheel/sdist, app bundle, markdown docs |
| 依赖 | PyInstaller, package metadata |
| 不负责 | Core 业务逻辑 |

## 禁止耦合关系

- 模块业务逻辑不得长期依赖已删除或仓库中不存在的路径。
- 发布配置不得引用不存在的入口或资源路径。
- 版本号不得分别在多个文件中独立漂移而没有统一规则。

## 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-27 | 刷新 SDK / Contracts 边界：运行时代码只依赖 contracts，SDK 不再承载 `TaskScript` / `TaskFlow`、ModuleAssembler 或资源池 helper | Codex |
| 2026-04-30 | 补记 v2 对象装配注解 helper：对象依赖和 component 参数可从类属性 / `__init__` 参数注解归一到运行时元数据 | Codex |
| 2026-04-22 | 补记模块 UI 边界：模块不再直接导出 `PyQt6` 页面，只能声明宿主管理页与宿主数据表 | Codex |
| 2026-03-26 | 建立当前代码边界摘要 | Codex |
| 2026-03-31 | 登记模块根入口自动托管的目标边界 | Codex |

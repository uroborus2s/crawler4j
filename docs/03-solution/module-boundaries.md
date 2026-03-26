# 模块边界

**项目名称：** crawler4j  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 维护者  
**上游输入：** `system-architecture.md` | 当前代码布局  
**下游输出：** `api-design.md` | `docs/04-delivery/task-breakdown.md`  
**关联 ID：** `MOD-001`, `MOD-002`, `MOD-003`, `MOD-004`, `MOD-005`  
**最后更新：** 2026-03-26  

## `MOD-001` Root Desktop App

| 项目 | 内容 |
|---|---|
| 目录 | `src/ui/`, `src/__version__.py` |
| 职责 | 应用入口、主窗口、UI 组件、用户操作壳层 |
| 对外接口 | `src.ui.app:main` |
| 依赖 | `src/core/`, PyQt6, qasync |
| 不负责 | 业务模块实现、外部模块脚手架、SDK 分发 |

## `MOD-002` Core Runtime Services

| 项目 | 内容 |
|---|---|
| 目录 | `src/core/` |
| 职责 | 调度、模块管理、环境管理、持久化、调试、系统服务 |
| 对外接口 | 内部 Python API，由 UI 与模块运行时调用 |
| 依赖 | Playwright, SQLAlchemy, APScheduler |
| 不负责 | 模块业务逻辑本身 |

## `MOD-003` Builtin Modules

| 项目 | 内容 |
|---|---|
| 目录 | `modules/` |
| 职责 | 提供 builtin module 的 `module.yaml`、task script、workflow、hooks |
| 对外接口 | `run(context)` 与模块 hooks |
| 依赖 | `crawler4j_sdk`, Core runtime |
| 不负责 | Core 基础设施、SDK 公共契约 |

当前边界风险：

- `modules/ctrip` 已进入新模块形态，但仍包含对旧 `src.automation.*` 的耦合引用。

## `MOD-004` SDK 与 Contracts

| 项目 | 内容 |
|---|---|
| 目录 | `crawler4j_sdk/`, `crawler4j_contracts/` |
| 职责 | 提供 TaskScript / TaskFlow / TaskContext / TaskResult 等开发契约与 CLI |
| 对外接口 | `crawler4j` CLI, Python 包 API |
| 依赖 | `crawler4j-contracts`, aiohttp, pyyaml |
| 不负责 | Root app UI、内置模块业务流程 |

## `MOD-005` Docs 与 Release Surface

| 项目 | 内容 |
|---|---|
| 目录 | `docs/`, `crawler4j.spec`, `dist/`, `build/` |
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
| 2026-03-26 | 建立当前代码边界摘要 | Codex |

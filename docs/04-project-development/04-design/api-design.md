# 接口与契约设计

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 模块开发者  
**上游输入：** `system-architecture.md` | `module-boundaries.md` | 现有 SDK / Contracts / module manifests  
**下游输出：** `docs/04-project-development/05-development-process/implementation-plan.md` | `docs/04-project-development/06-testing-verification/test-plan.md`
**关联 ID：** `API-001`, `API-002`, `API-003`, `API-004`, `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-006`, `REQ-007`, `BUG-013`, `CR-005`  
**最后更新：** 2026-04-16

## `API-001` Root App Entry Contract

| 项目 | 内容 |
|---|---|
| 目标 | 启动桌面应用 |
| 当前真实入口 | `src.ui.app:main` |
| 当前开发入口 | workspace 根执行 `uv run python -m src.ui.app` |
| 当前状态 | 已对齐，需持续回归验证 |
| 关联项 | `BUG-001`, `TASK-002` |

## `API-002` Module Runtime Contract

| 项目 | 内容 |
|---|---|
| Manifest 文件 | `module.yaml` |
| 宿主入口文件 | 模块根 `__init__.py` |
| 必需入口 | `run(context)` |
| 可选 hooks | `prepare_env`, `init_env`, `before_run`, `on_success`, `on_failure`, `on_timeout`, `on_cleanup` |
| 当前实现 | 根 `__init__.py` 已收敛为稳定薄壳，默认入口组装逻辑由 `ModuleAssembler` 提供 |
| Core 扩展入口 | `context.tools.call("<namespace>.<action>", **kwargs)` |
| 生命周期规则 | `on_cleanup` 是终态清理 hook；只要任务已建立 `TaskContext` 并进入终态就会执行，不以环境是否 `destroy` 为前提；环境动作结果通过 `context.runtime["env_action"]` 暴露 |
| 默认工作流解析 | `context.config.workflow` -> `module_runtime.DEFAULT_WORKFLOW` -> `module.yaml.workflows[0].name` |
| 发现错误可见性 | `ModuleAssembler` 发现 `tasks/` / `workflows/` import 失败时，必须记录 import 目标、异常类型与 traceback；若当前请求命中失败条目，`run()` 需附带 discovery hint，而不是只报泛化的“not found” |
| `core:data_table` UI 契约 | 页面创建/刷新时先同步调用根模块 `declare_ui(context)`；若 schema 声明 `create_handler` / `update_handler`，通用页新增/编辑继续路由到同名同步本地 hook |
| `TaskSignal` UI 契约 | `TaskSignal.wait_for_confirmation(..., payload={"confirmation": ...})` 会把完整 `signal` 快照持久化到任务记录，并发布 `task.signal` 事件；ATM 详情页按 `payload.confirmation` 渲染结构化确认面板，若缺少该块则退回展示 `message` 与 payload 键值 |
| DevLink 调试语义 | 模块来源为 `DevLink` 时，详情页数据表刷新会以 `devel_mode=true` 重建本地 hook 上下文，便于联调最新 UI 声明 |
| DevLink 普通执行语义 | ATM 普通执行 `DevLink` 模块时，也会注入 `devel_mode=true`；`ModuleService` 对同一个 `TaskContext` 只在首次加载时强制 reload 一次，后续 hook / `run()` 复用同次执行内已加载模块 |
| 升级策略 | 旧模块统一按最新模板重新初始化；不再为旧式完整 `__init__.py` 模板提供兼容承诺 |
| 当前风险 | 真实站点 E2E 仍未覆盖；动态加载的模块扩展点仍需依赖回归测试保持稳定 |
| 关联项 | `TASK-003`, `TASK-013` |

## `API-003` SDK / Contracts Package Contract

| 项目 | 内容 |
|---|---|
| SDK 包名 | `crawler4j-sdk` |
| Contracts 包名 | `crawler4j-contracts` |
| CLI 入口 | `crawler4j_sdk.cli.commands:main` |
| 当前能力 | `ModuleAssembler` 已作为统一模块入口组装 helper 落地；`TaskContext` 已收敛为 `tools` 统一扩展入口；`TaskSignal` 已成为模块到 ATM 的正式流程信号；CLI 已支持 `init-model --defaults`、`new` 与 `list` |
| 当前状态 | 本地 build 成功，help 可运行；模块入口自动托管、重初始化路径与集成测试已完成 |
| 关联项 | `REQ-003`, `REQ-006` |

## `API-004` Release Metadata Contract

| 项目 | 内容 |
|---|---|
| 根应用版本事实源 | `packages/crawler4j/pyproject.toml` |
| 运行时版本读取 | `packages/crawler4j/src/core/system/version_service.py` 从包元数据或 `packages/crawler4j/pyproject.toml` 解析 |
| 最近正式发布 | Git tag |
| 子包版本 | `packages/crawler4j-sdk/pyproject.toml`, `packages/crawler4j-contracts/pyproject.toml` |
| 发布文档 | `docs/04-project-development/07-release-delivery/version-governance.md`, `docs/04-project-development/07-release-delivery/release-notes.md` |
| 当前状态 | 已收口：当前工作区版本与最近正式发布已被明确区分 |
| 关联项 | `CR-001`, `TASK-004` |

## 设计结论

- 本项目的关键“接口”不是 HTTP API，而是运行入口、模块契约、SDK/Contracts 包接口和发布元数据接口。
- 当前版本治理规则已经明确：根应用 `pyproject.toml`、运行时版本读取、最新正式 tag 和子包版本线各自职责清晰。

## 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-26 | 初始接口与契约设计摘要 | Codex |
| 2026-03-31 | 增补模块根入口自动托管的契约演进设计 | Codex |
| 2026-04-08 | 补记 `core:data_table` 的本地 UI hook 契约与 DevLink 刷新调试语义 | Codex |
| 2026-04-15 | 将 Core 扩展能力收敛到 `TaskContext.tools` 统一工具接口 | Codex |
| 2026-04-15 | 固化 `on_cleanup` 终态规则，并补记 `TaskSignal` 为正式流程信号 | Codex |
| 2026-04-16 | 补记 `TaskSignal.wait_for_confirmation` 的结构化确认面板协议、任务快照持久化与 `task.signal` 事件 | Codex |
| 2026-04-16 | 补记 `ModuleAssembler` 发现错误可见性，以及 DevLink 普通执行的一次性 reload 语义 | Codex |

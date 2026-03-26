# 接口与契约设计

**项目名称：** crawler4j  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 模块开发者  
**上游输入：** `system-architecture.md` | `module-boundaries.md` | 现有 SDK / Contracts / module manifests  
**下游输出：** `docs/04-delivery/task-breakdown.md` | `docs/05-quality/test-plan.md`  
**关联 ID：** `API-001`, `API-002`, `API-003`, `API-004`, `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`  
**最后更新：** 2026-03-26  

## `API-001` Root App Entry Contract

| 项目 | 内容 |
|---|---|
| 目标 | 启动桌面应用 |
| 当前真实入口 | `src.ui.app:main` |
| 当前声明入口 | `[project.scripts].start = src.ui.app:main` |
| 当前状态 | 已对齐，需持续回归验证 |
| 关联项 | `BUG-001`, `TASK-002` |

## `API-002` Module Runtime Contract

| 项目 | 内容 |
|---|---|
| Manifest 文件 | `module.yaml` |
| 必需入口 | `run(context)` |
| 可选 hooks | `prepare_env`, `init_env`, `before_run`, `on_success`, `on_failure`, `on_timeout`, `on_cleanup` |
| 当前风险 | 真实站点 E2E 仍未覆盖，MMS 高阶设置与 UI 扩展能力尚未完全闭环 |
| 关联项 | `TASK-003`, `CR-003` |

## `API-003` SDK / Contracts Package Contract

| 项目 | 内容 |
|---|---|
| SDK 包名 | `crawler4j-sdk` |
| Contracts 包名 | `crawler4j-contracts` |
| CLI 入口 | `crawler4j_sdk.cli.commands:main` |
| 当前状态 | 本地 build 成功，help 可运行 |
| 关联项 | `REQ-003` |

## `API-004` Release Metadata Contract

| 项目 | 内容 |
|---|---|
| 根应用版本事实源 | 根 `pyproject.toml` |
| 运行时版本镜像 | `src/__version__.py`，必须与根版本完全一致 |
| 最近正式发布 | Git tag |
| 子包版本 | `crawler4j_sdk/pyproject.toml`, `crawler4j_contracts/pyproject.toml` |
| 发布文档 | `docs/06-release/version-governance.md`, `docs/06-release/release-notes.md` |
| 当前状态 | 已收口：当前工作区版本与最近正式发布已被明确区分 |
| 关联项 | `CR-001`, `TASK-004` |

## 设计结论

- 本项目的关键“接口”不是 HTTP API，而是运行入口、模块契约、SDK/Contracts 包接口和发布元数据接口。
- 当前版本治理规则已经明确：根工作区版本、运行时镜像、最新正式 tag 和子包版本线各自职责清晰。

## 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-03-26 | 初始接口与契约设计摘要 | Codex |

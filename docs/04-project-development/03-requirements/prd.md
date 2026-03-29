# 产品需求文档（PRD）

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 开发 | QA | 架构 | 发布负责人  
**上游输入：** `docs/04-project-development/02-discovery/input.md` | `docs/04-project-development/02-discovery/current-state-analysis.md` | `docs/04-project-development/01-governance/project-charter.md`  
**下游输出：** `docs/04-project-development/04-design/` | `docs/04-project-development/05-development-process/` | `docs/04-project-development/06-testing-verification/test-plan.md`  
**关联 ID：** `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`, `NFR-001`, `NFR-002`, `NFR-003`, `NFR-004`  
**最后更新：** 2026-03-26  

## 1. 背景与目标

### 背景

- 项目已经实现并有历史发布产物，但当前缺少统一的软件工厂治理基线。
- 当前最主要的问题不是“有没有代码”，而是“能否准确地判断什么真的可运行、可发布、可继续演进”。

### 业务目标

- 为桌面自动化平台提供可验证的运行、构建、文档与模块开发链路。
- 将历史仓库纳入软件工厂阶段化治理。
- 为下一批修复和迭代建立可追踪工作项。

### 成功指标

| 指标 | 目标值 | 观测方式 |
|---|---|---|
| 核心验证链路可复现 | 达成 | 测试、UI smoke、源码构建均有记录 |
| 入口与版本治理清晰 | 达成 | 关闭 `BUG-001`、`CR-001` 后复验 |
| 模块关键流程可恢复 | 达成 | `TASK-003` 完成后复验 |

## 2. 用户与场景

| 用户角色 | 场景 | 核心诉求 |
|---|---|---|
| 最终使用者 | 启动桌面应用并执行自动化任务 | 应用能启动，模块可运行 |
| 模块开发者 | 使用 SDK CLI 创建和维护模块 | SDK/Contracts/CLI 可用、契约清晰 |
| 维护者 | 构建、验证、发布项目 | 版本、入口、文档、工作项一致 |

## 3. 功能需求

### `REQ-001` 桌面 Core 可启动并初始化基础运行环境

- 优先级：P0
- 描述：系统必须提供可验证的桌面应用入口，完成数据库、日志、核心服务和 UI 壳的初始化。
- 用户故事：作为维护者，我希望应用入口与发布配置一致，以便能可靠启动和打包桌面应用。
- 前置条件：Python 3.12、依赖已通过 `uv sync` 安装
- 业务规则：入口路径、脚本声明、打包规格必须保持一致
- 依赖项：`src/ui/app.py`, `pyproject.toml`, `crawler4j.spec`
- 排除范围：本次不引入新的 GUI 功能

验收标准：

- [ ] `UAT-001` 根应用声明入口与真实入口一致
- [ ] `UAT-002` 手工启动与打包链路使用同一入口

### `REQ-002` Core 必须能够加载模块并执行目标工作流

- 优先级：P0
- 描述：MMS、ATM、REM、TSM 必须能按模块契约运行任务与工作流。
- 用户故事：作为最终使用者或模块作者，我希望外部安装模块或 DevLink 模块可以执行其声明的工作流，以便完成自动化任务与真实调试。
- 前置条件：模块目录包含 `module.yaml` 与对应实现
- 业务规则：模块不应依赖已删除的旧路径
- 依赖项：`modules/README.md`, `src/core/mms/`, `src/core/atm/`, `src/core/debug/`
- 排除范围：不要求本次新增模块

验收标准：

- [ ] `UAT-003` `ctrip` 登录工作流可执行
- [ ] `UAT-004` `ctrip labor_workflow` 不再依赖 `src.automation.*`

### `REQ-003` 项目必须提供可用的 SDK / Contracts / CLI 开发链路

- 优先级：P1
- 描述：SDK 与 Contracts 必须可构建，CLI 必须可以展示帮助并生成模块脚手架。
- 用户故事：作为模块开发者，我希望 SDK 与 CLI 可靠，以便我能创建或维护模块项目。
- 前置条件：`crawler4j_sdk/` 与 `crawler4j_contracts/` 可独立构建
- 业务规则：SDK 版本与 Contracts 兼容范围需明确
- 依赖项：子包 `pyproject.toml`, `crawler4j_sdk/cli/commands.py`
- 排除范围：不要求本次发布到外部仓库

验收标准：

- [x] `UAT-005` SDK 本地 build 成功
- [x] `UAT-006` Contracts 本地 build 成功
- [x] `UAT-007` SDK CLI help 可运行

### `REQ-004` 项目必须具备可追溯的发布与文档链路

- 优先级：P0
- 描述：版本号、Tag、发布说明、构建命令和文档说明必须可对齐。
- 用户故事：作为发布负责人，我希望所有发布信号一致，以便能判断当前到底发布了什么。
- 前置条件：存在统一的版本事实源与 release 说明
- 业务规则：构建成功不等于可运行，必须补充入口和 smoke 验证
- 依赖项：`pyproject.toml`, `src/__version__.py`, Git tag, `docs/04-project-development/07-release-delivery/version-governance.md`, `docs/04-project-development/07-release-delivery/release-notes.md`
- 排除范围：不要求本次直接上线新版本

验收标准：

- [x] `UAT-008` 根版本与运行时版本一致，且 release notes 明确区分当前工作区版本与最近正式 tag
- [x] `UAT-009` 发布说明明确区分 app / sdk / contracts

### `REQ-005` 项目必须在软件工厂内有可持续推进的治理基线

- 优先级：P0
- 描述：项目必须有阶段化文档、工厂元数据与可执行工作项。
- 用户故事：作为维护者，我希望后续工作按阶段和 workitem 运行，而不是继续散落在口头和 commit 中。
- 前置条件：`AGENTS.md`, `GEMINI.md`, `.factory/`, 编号文档存在
- 业务规则：后续变更应同步代码、文档、测试和 `.factory/memory/`
- 依赖项：本次基线补齐结果
- 排除范围：不要求一次性补齐所有高级治理产物

验收标准：

- [x] `UAT-010` 工厂文档与 `.factory/` 基线已创建
- [x] `UAT-011` 首批 `BUG` / `CR` / `TASK` 已创建

## 4. 非功能需求

### `NFR-001` 工具链一致性

- 指标：统一使用 Python 3.12 + `uv`
- 约束：所有核心命令通过 `uv` 运行
- 验证方式：本地验证命令记录

### `NFR-002` 发布一致性

- 指标：版本、入口、打包规格一致
- 约束：脚本入口与 PyInstaller 入口必须复用同一事实源
- 验证方式：关闭 `BUG-001` 与 `CR-001` 后复验

### `NFR-003` 质量门

- 指标：`pytest`、文档入口核对、构建产物验证应稳定通过
- 约束：lint 与文档导航都需收敛为可执行规则，不能长期漂移
- 验证方式：`uv run pytest -q`, `uv run python scripts/smoke_test_ui.py`, `uv run ruff check .`

### `NFR-004` 可维护性

- 指标：核心边界、运行方式、首批工作项与风险可被新接手者理解
- 约束：正式事实源必须落在 `docs/` 与 `.factory/`
- 验证方式：阶段文档与 workitems 完整存在

## 5. 关键流程

1. 维护者通过 `uv` 同步环境并运行测试、文档、build 验证
2. Core 通过 UI 或模块服务加载模块并执行工作流
3. 发布前通过版本、入口、文档与构建结果进行闭环校验
4. 后续迭代通过 `BUG` / `CR` / `TASK` 驱动进入实现阶段

## 6. 风险、假设与待确认问题

### 风险

- 根项目发布入口失真，当前 wheel 可构建但脚本不可运行
- `ctrip` 真实站点完整业务 E2E 尚未回放
- 现有 lint 失败表明代码与脚本质量边界没有稳定定义

### 假设

- 当前维护者接受以本地验证结果而非历史文档口径作为阶段事实
- 首批迭代优先处理发布入口、关键工作流和版本治理，而非新增业务功能

### 待确认

- 后续是否要将 GUI smoke / 打包 smoke 纳入 CI
- 是否要为 `ctrip` 模块补充真实端到端可重复验证环境

## 7. 版本与变更

| 版本 | 日期 | 变更内容 | 关联 `CR` |
|---|---|---|---|
| v1.0 | 2026-03-26 | 基于当前仓库真实状态重建工厂 PRD |  |

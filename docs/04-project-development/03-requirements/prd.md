# 产品需求文档（PRD）

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 开发 | QA | 架构 | 发布负责人  
**上游输入：** `docs/04-project-development/02-discovery/input.md` | `docs/04-project-development/02-discovery/current-state-analysis.md` | `docs/04-project-development/01-governance/project-charter.md`  
**下游输出：** `docs/04-project-development/04-design/` | `docs/04-project-development/05-development-process/` | `docs/04-project-development/06-testing-verification/test-plan.md`  
**关联 ID：** `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`, `REQ-006`, `REQ-007`, `REQ-008`, `REQ-009`, `NFR-001`, `NFR-002`, `NFR-003`, `NFR-004`
**最后更新：** 2026-04-19

## 1. 背景与目标

### 背景

- 项目已经实现并有历史发布产物，但当前缺少统一的软件工厂治理基线。
- 当前最主要的问题不是“有没有代码”，而是“能否准确地判断什么真的可运行、可发布、可继续演进”。

### 业务目标

- 为桌面自动化平台提供可验证的运行、构建、文档与模块开发链路。
- 将历史仓库纳入软件工厂阶段化治理。
- 为下一批修复和迭代建立可追踪工作项。
- 降低模块根入口契约的维护成本，让新模块不再手工维护根 `__init__.py`。
- 让固定环境池的 Service Job 在资源不足时进入稳定候场，而不是制造反复失败与重建噪声。

### 成功指标

| 指标 | 目标值 | 观测方式 |
|---|---|---|
| 核心验证链路可复现 | 达成 | 测试、UI smoke、源码构建均有记录 |
| 入口与版本治理清晰 | 达成 | 关闭 `BUG-001`、`CR-001` 后复验 |
| 模块关键流程可恢复 | 达成 | `TASK-003` 完成后复验 |
| 模块根入口维护成本降低 | 达成 | 新脚手架生成的模块无需手工维护根 `__init__.py` |
| 固定环境池服务不再因容量不足形成假失败风暴 | 本地达成 | `REQ-009` 已完成等待队列、FIFO 补位、资源池隔离与等待席位自动超时收口的本地回归 |

## 2. 用户与场景

| 用户角色 | 场景 | 核心诉求 |
|---|---|---|
| 最终使用者 | 启动桌面应用并执行自动化任务 | 应用能启动，模块可运行 |
| 模块开发者 | 使用 SDK CLI 创建和维护模块 | SDK/Contracts/CLI 可用、契约清晰、根入口不需要反复手改 |
| 维护者 | 构建、验证、发布项目 | 版本、入口、文档、工作项一致 |

## 3. 功能需求

### `REQ-001` 桌面 Core 可启动并初始化基础运行环境

- 优先级：P0
- 描述：系统必须提供可验证的桌面应用入口，完成数据库、日志、核心服务和 UI 壳的初始化。
- 用户故事：作为维护者，我希望应用入口与发布配置一致，以便能可靠启动和打包桌面应用。
- 前置条件：Python 3.12、依赖已通过 `uv sync --all-packages` 安装
- 业务规则：入口路径、脚本声明、打包规格必须保持一致
- 依赖项：`packages/crawler4j/src/ui/app.py`, `packages/crawler4j/pyproject.toml`, `packages/crawler4j/crawler4j.spec`
- 排除范围：本次不引入新的 GUI 功能

验收标准：

- [ ] `UAT-001` 根应用声明入口与真实入口一致
- [ ] `UAT-002` 手工启动与打包链路使用同一入口

### `REQ-002` Core 必须能够加载模块并执行目标工作流

- 优先级：P0
- 描述：MMS、ATM、REM 与 Job RunProfile 必须能按模块契约运行任务与工作流。
- 用户故事：作为最终使用者或模块作者，我希望外部安装模块或 DevLink 模块可以执行其声明的工作流，以便完成自动化任务与真实调试。
- 前置条件：模块目录包含 `module.yaml` 与对应实现
- 业务规则：模块不应依赖已删除的旧路径
- 依赖项：`packages/crawler4j/modules/README.md`, `packages/crawler4j/src/core/mms/`, `packages/crawler4j/src/core/atm/`, `packages/crawler4j/src/core/debug/`
- 排除范围：不要求本次新增模块

验收标准：

- [ ] `UAT-003` `ctrip` 登录工作流可执行
- [x] `UAT-004` `ctrip labor_workflow` 不再依赖 `src.automation.*`

### `REQ-003` 项目必须提供可用的 SDK / Contracts / CLI 开发链路

- 优先级：P1
- 描述：SDK 与 Contracts 必须可构建，CLI 必须可以展示帮助并生成模块脚手架。
- 用户故事：作为模块开发者，我希望 SDK 与 CLI 可靠，以便我能创建或维护模块项目。
- 前置条件：`packages/crawler4j-sdk/` 与 `packages/crawler4j-contracts/` 可独立构建
- 业务规则：SDK 与 Contracts 的版本基线需明确
- 依赖项：子包 `pyproject.toml`, `packages/crawler4j-sdk/src/cli/commands.py`
- 排除范围：不要求本次发布到外部仓库

验收标准：

- [x] `UAT-005` SDK 本地 build 成功
- [x] `UAT-006` Contracts 本地 build 成功
- [x] `UAT-007` SDK CLI help 可运行

### `REQ-006` 模块根入口应可由工具托管而无需开发者手工维护

- 优先级：P1
- 描述：新生成的模块根 `__init__.py` 应收敛为稳定薄壳，默认运行时组装逻辑由 SDK 统一提供，开发者无需在常规开发中手工维护根入口文件。
- 用户故事：作为模块开发者，我希望模块根入口由工具托管，以便我在新增任务、工作流或调整默认运行方式时，不需要再手改根 `__init__.py`。
- 前置条件：模块目录仍包含 `module.yaml` 与根 `__init__.py`
- 业务规则：必须保持当前 Core 仍通过根 `__init__.py` 加载模块；旧模块升级路径统一为按最新方式重新初始化，不再为旧模板提供兼容承诺
- 依赖项：`packages/crawler4j-sdk/src/cli/templates.py`, `packages/crawler4j-sdk/src/cli/commands.py`, `packages/crawler4j/src/core/mms/service.py`, 模块开发者指南
- 排除范围：本轮不要求保留旧式完整 `__init__.py` 模板；不要求 Core 改为直接按 manifest 入口加载

验收标准：

- [ ] `UAT-012` `module init` 生成的新模块根 `__init__.py` 为固定薄壳，而不是内联完整调度逻辑
- [ ] `UAT-013` 默认任务/工作流分发逻辑可由 SDK helper 提供，不再要求写在模块根 `__init__.py`
- [ ] `UAT-014` 模块级自定义 hooks 或默认工作流可在独立文件中声明，而不是必须写在根 `__init__.py`
- [ ] `UAT-015` 模块升级说明明确要求按最新模板重新初始化，而不是继续维护旧式根入口

### `REQ-007` ATM 必须能够根据信号展示结构化确认内容并等待客户端确认

- 优先级：P1
- 描述：当模块通过 `TaskSignal.wait_for_confirmation(...)` 发出等待确认信号时，Core 必须持久化该信号，桌面客户端必须能够读取并展示结构化确认内容，并在用户确认成功或失败后继续完成任务终态处理。
- 用户故事：作为 ATM 使用者，我希望当模块要求人工复核时，客户端能直接弹出带结构化信息的确认面板，以便我不需要翻日志或读原始 JSON 就能做出确认。
- 前置条件：模块已发出 `wait_for_confirmation` 信号，且 `payload` 可选包含结构化展示说明。
- 业务规则：
  - `wait_for_confirmation` 仍只允许 `keep_alive` 语义保留环境，等待期间不进入终态 hooks。
  - `payload.confirmation` 作为正式 UI 展示协议，至少支持 `title`、`description`、`fields`、`confirm_text`、`reject_text`。
  - 若模块未提供 `payload.confirmation`，客户端应回退为展示 `message` 和原始 payload 的键值内容。
  - 用户确认成功或失败后，ATM 继续走既有 `confirm_task_success/confirm_task_failure` 链路，不新增第二套确认入口。
- 依赖项：`packages/crawler4j/src/core/atm/{execution_runner,dispatcher,repository,ui/task_detail_dialog.py}`、`packages/crawler4j/src/core/foundation/event_bus.py`
- 排除范围：本轮不实现跨进程/重启后的等待确认恢复执行；不扩展为任意自定义表单提交通道。

验收标准：

- [x] `UAT-016` `TaskSignal.wait_for_confirmation` 的结构化内容可随任务状态一起持久化并重新读取
- [x] `UAT-017` ATM 详情页在收到等待确认信号时会弹出结构化确认面板
- [x] `UAT-018` 用户在确认面板中选择成功或失败后，会调用既有确认服务完成任务收尾

### `REQ-008` 宿主必须为模块提供独立的审计事件持久化能力

- 优先级：P1
- 描述：宿主必须在快照型 dataset 之外，为模块提供 append-only 的审计事件写入与查询能力，用于记录账号状态流转、运行留痕和其他历史轨迹。
- 用户故事：作为模块开发者，我希望宿主提供与快照数据分离的事件型存储能力，以便记录审计历史，而不是把事件流伪装成普通 dataset 全量覆盖写回。
- 前置条件：模块通过 `TaskContext.db` 调用宿主数据能力。
- 业务规则：
  - 快照型数据继续通过 `ctx.db.from_` / `ctx.db.into(...).replace` 落到 `data.db.module_datasets` 或受控自定义表。
  - 审计事件通过 `ctx.db.audit(...).append/query` 落到独立的 `data.db.module_audit_events`。
  - 模块写入的审计事件为 append-only；本轮不提供模块侧的更新/删除接口。
  - `core:data_table` 仍只服务快照型 dataset，不承担审计事件编辑。
  - retention / archive 暂不纳入本轮实现范围。
- 依赖项：`packages/crawler4j/src/core/persistence/{database.py,module_data_store.py}`, `packages/crawler4j/src/core/atm/runtime_capabilities.py`, `packages/crawler4j-sdk/README.md`, 模块开发者指南
- 排除范围：本轮不实现旧 `account_events` 自动迁移脚本；不新增通用审计查询 UI。

验收标准：

- [x] `UAT-019` 模块调用 `ctx.db.audit(...).append` 时，宿主会为目标模块和 dataset 新增 1 条独立事件记录，而不是重写整包历史 JSON
- [x] `UAT-020` 模块调用 `ctx.db.audit(...).query` 时，可按 `dataset / entity_key / event_type / run_id / time range` 查询事件，并按时间顺序返回结果
- [x] `UAT-021` 快照型 dataset 继续通过 `ctx.db.from_` / `ctx.db.into(...).replace` 读写，审计事件不会污染 `module_datasets`
- [x] `UAT-022` 新增事件能力后，模块仍通过统一的 `ctx.db` 能力面访问宿主，不需要直连数据库
- [x] `UAT-023` 宿主清理模块数据时，会同时清理该模块的快照数据、审计事件和托管数据表 schema

### `REQ-009` ATM 必须支持固定环境池 Service Job 的等待队列与模块资源池分配

- 优先级：P1
- 描述：对于使用固定环境池的 Service Job，宿主必须把“暂时没有可用环境”建模为正式等待状态，而不是直接失败；宿主只应在“当前模块 + 当前资源池 + 资格有效”的环境集合里分配环境，并按队列语义维持目标并发。
- 用户故事：作为服务运营者或模块开发者，我希望当目标并发大于当前可用环境数时，系统能稳定表现为“运行中 + 等待中”，以便固定环境池服务不会因为资源暂时不足而不断失败和重建。
- 前置条件：任务以固定环境池 Service Job 方式运行，模块已向宿主同步当前资源池资格。
- 业务规则：
  - 固定环境池场景下，“当前轮没拿到环境”属于等待，不属于失败。
  - 目标并发按服务席位表达，业务口径统一为 `运行中 + 等待中 = 目标并发`。
  - 宿主只从“当前模块 + 当前资源池 + `eligible=true`”的环境集合里叫号，不从全局环境池盲抢。
  - 容量扩张时按 FIFO 连续补位；容量收缩时停止继续补位，但不抢占已在运行中的任务。
  - 黑号或风控失效环境必须先停发号，再按业务策略销毁或保留人工处理。
- 依赖项：`packages/crawler4j/src/core/atm/`, `packages/crawler4j/src/core/rem/`, `packages/crawler4j-sdk/`, `docs/04-project-development/04-design/atm-resource-pool-queue-design.md`
- 排除范围：本轮不实现优先级队列、多租户抢占策略、模块自写等待轮询或在通用 `Environment` 上新增强绑定 `module_id`

验收标准：

- [ ] `UAT-024` 给定目标并发 10、当前可用工位 2，当宿主调和固定环境池 Service Job，则系统稳定表现为“运行中 2、等待中 8”，且不会制造 8 个反复失败实例
- [ ] `UAT-025` 给定当前状态为“运行中 2、等待中 8”，当同一资源池可用工位从 2 增长到 5，则宿主会一次性补位 3 个，结果表现为“运行中 5、等待中 5”
- [ ] `UAT-026` 给定环境列表中同时存在其他模块或其他资源池的工位，当宿主为当前固定环境池 Service Job 分配环境，则只会从“当前模块 + 当前资源池 + 资格有效”的候选中分配
- [ ] `UAT-027` 给定某个工位被标记为黑号或不可接单，当宿主后续调和等待席位，则该工位不会再被叫号；若随后环境被销毁，对应资格卡片会自动消失
- [ ] `UAT-028` 给定等待时间超过明确上限，当宿主结束该等待席位，则失败原因收敛为“等待环境超时”类错误，而不是“环境选择返回 none”

当前实现备注：

- V1 已本地实现并验证队列语义、FIFO 补位、资源池隔离、资格卡片、等待席位自动超时收口与 SDK helper
- `UAT-028` 当前实现的错误文案为 `等待环境池工位超时: <pool> (<seconds>s)`，语义已从“环境选择返回 none”收敛为等待超时类错误

### `REQ-004` 项目必须具备可追溯的发布与文档链路

- 优先级：P0
- 描述：版本号、Tag、发布说明、构建命令和文档说明必须可对齐。
- 用户故事：作为发布负责人，我希望所有发布信号一致，以便能判断当前到底发布了什么。
- 前置条件：存在统一的版本事实源与 release 说明
- 业务规则：构建成功不等于可运行，必须补充入口和 smoke 验证
- 依赖项：`packages/crawler4j/pyproject.toml`, `packages/crawler4j/src/core/system/version_service.py`, Git tag, `docs/04-project-development/07-release-delivery/version-governance.md`, `docs/04-project-development/07-release-delivery/release-notes.md`
- 排除范围：不要求本次直接上线新版本

验收标准：

- [x] `UAT-008` 根版本由 `packages/crawler4j/pyproject.toml` 单点声明，且 release notes 明确区分当前工作区版本与最近正式 tag
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
- 模块根入口切换为单一新模板后，旧模块升级需要一次性重初始化和业务文件迁移

### 假设

- 当前维护者接受以本地验证结果而非历史文档口径作为阶段事实
- 首批迭代优先处理发布入口、关键工作流和版本治理，而非新增业务功能
- 模块级通用分发逻辑可以集中沉淀到 SDK，而不需要每个模块重复维护一份
- 旧模块作者可以接受“按最新模板重新初始化”作为唯一升级路径

### 待确认

- 后续是否要将 GUI smoke / 打包 smoke 纳入 CI
- 是否要为 `ctrip` 模块补充真实端到端可重复验证环境
- 是否需要额外提供“重初始化迁移清单”而不是自动迁移命令

## 7. 版本与变更

| 版本 | 日期 | 变更内容 | 关联 `CR` |
|---|---|---|---|
| v1.0 | 2026-03-26 | 基于当前仓库真实状态重建工厂 PRD |  |
| v1.1 | 2026-03-31 | 新增 `REQ-006`，登记模块根入口自动托管的最小改造需求 |  |
| v1.2 | 2026-04-16 | 新增 `REQ-007`，登记信号驱动的结构化确认面板与客户端确认闭环 | `CR-004` |
| v1.3 | 2026-04-18 | 新增 `REQ-008`，登记模块快照数据与审计事件分层存储契约 | `CR-008` |

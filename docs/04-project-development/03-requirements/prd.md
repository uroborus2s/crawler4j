# 产品需求文档（PRD）

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 开发 | QA | 架构 | 发布负责人  
**上游输入：** `docs/04-project-development/02-discovery/input.md` | `docs/04-project-development/02-discovery/current-state-analysis.md` | `docs/04-project-development/01-governance/project-charter.md`  
**下游输出：** `docs/04-project-development/04-design/` | `docs/04-project-development/05-development-process/` | `docs/04-project-development/06-testing-verification/test-plan.md`  
**关联 ID：** `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-005`, `REQ-006`, `REQ-007`, `REQ-008`, `REQ-009`, `REQ-010`, `NFR-001`, `NFR-002`, `NFR-003`, `NFR-004`, `NFR-010`
**最后更新：** 2026-06-19

## 1. 背景与目标

### 背景

- 项目已经实现并有历史发布产物，但当前缺少统一的软件工厂治理基线。
- 当前最主要的问题不是“有没有代码”，而是“能否准确地判断什么真的可运行、可发布、可继续演进”。

### 业务目标

- 为桌面自动化平台提供可验证的运行、构建、文档与模块开发链路。
- 将历史仓库纳入软件工厂阶段化治理。
- 为下一批修复和迭代建立可追踪工作项。
- 降低模块根入口契约的维护成本，让新模块不再手工维护根 `__init__.py`。
- 让环境候选 Service Job 在候选环境暂时不足时进入稳定候场，而不是制造反复失败与重建噪声。

### 成功指标

| 指标 | 目标值 | 观测方式 |
|---|---|---|
| 核心验证链路可复现 | 达成 | 测试、UI smoke、源码构建均有记录 |
| 入口与版本治理清晰 | 达成 | 关闭 `BUG-001`、`CR-001` 后复验 |
| 模块关键流程可恢复 | 达成 | `TASK-003` 完成后复验 |
| 模块根入口维护成本降低 | 达成 | 新脚手架生成的模块无需手工维护根 `__init__.py` |
| 环境候选服务不再因候选容量不足形成假失败风暴 | 本地达成 | `REQ-009` 已完成候选纯函数、等待队列、FIFO 补位、模块环境授权与等待席位自动超时收口的本地回归 |
| Hosted UI 批量导入入口一致且安全 | 本地达成 | `REQ-010` 已完成 toolbar 按钮、宿主导入弹窗、标准 payload、批次结果和敏感字段脱敏验证；真实业务模块 E2E 与发布证据仍待后续收口 |

## 2. 用户与场景

| 用户角色 | 场景 | 核心诉求 |
|---|---|---|
| 最终使用者 | 启动桌面应用并执行自动化任务 | 应用能启动，模块可运行 |
| 模块开发者 | 使用 SDK CLI 创建和维护模块 | SDK/Contracts/CLI 可用、契约清晰、根入口不需要反复手改 |
| 运营 / 现场支持 | 在 Hosted UI 中批量导入账号、Cookie 或其它业务数据 | 能用 Excel/CSV/剪贴板快速导入，并能看到批次结果和逐条失败原因 |
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
- 描述：新生成的模块根 `__init__.py` 应收敛为稳定薄壳，默认根入口模板由 SDK CLI 生成，开发者无需在常规开发中手工维护根入口文件。
- 用户故事：作为模块开发者，我希望模块根入口由工具托管，以便我在新增任务、工作流或调整默认运行方式时，不需要再手改根 `__init__.py`。
- 前置条件：模块目录仍包含 `module.yaml` 与根 `__init__.py`
- 业务规则：必须保持当前 Core 仍通过根 `__init__.py` 加载模块；旧模块升级路径统一为按最新方式重新初始化，不再为旧模板提供兼容承诺
- 依赖项：`packages/crawler4j-sdk/src/cli/templates.py`, `packages/crawler4j-sdk/src/cli/commands.py`, `packages/crawler4j/src/core/mms/service.py`, 模块开发者指南
- 排除范围：本轮不要求保留旧式完整 `__init__.py` 模板；不要求 Core 改为直接按 manifest 入口加载

验收标准：

- [ ] `UAT-012` `module init` 生成的新模块根 `__init__.py` 为固定薄壳，而不是内联完整调度逻辑
- [ ] `UAT-013` 默认任务/工作流分发逻辑由 Core 扫描 `tasks/` / `workflows/` 承载，不再要求写在模块根 `__init__.py`
- [ ] `UAT-014` 默认工作流、页面动作、环境候选和清理候选可在独立文件中声明，而不是必须写在根 `__init__.py`；0.4.0 不提供模块级自定义生命周期 hooks
- [ ] `UAT-015` 模块升级说明明确要求按最新模板重新初始化，而不是继续维护旧式根入口

### `REQ-007` ATM 生命周期与环境处置必须由宿主统一管理

- 优先级：P1
- 描述：模块运行时代码不得发出流程控制或环境处置指令；Core 必须统一处理 workflow/object 收尾、任务终态环境回收和后续环境清理。
- 用户故事：作为 ATM 使用者，我希望任务被中止、失败或成功结束后环境处置口径一致，并能在环境管理页集中删除孤岛或废弃环境，避免模块代码绕过宿主安全门。
- 前置条件：运行模板已选定固定环境、候选环境或创建环境模式；模块按 0.4.0 装饰器契约声明 workflow、component 和数据表。
- 业务规则：
  - workflow 只能通过 `TaskResult` 表达成功或失败，不提供模块侧信号确认入口。
  - workflow/component 如需运行前准备，可选实现 `setup(ctx, workflow)`；如需收尾，可选实现 `cleanup(ctx, outcome)`；旧 `aclose()` / `close()` 不作为宿主生命周期契约。
  - 任务终态和用户中止后的环境统一回收，不在中止弹窗或运行结果中提供保留/删除策略。
  - 创建环境后宿主立即写入 `host.env_claim(pending)`；终态通过 `env_binding_field` 扫描模块业务表并标记 `claimed/abandoned`。
  - 环境删除只通过环境管理页 `清理环境` 执行，候选来源包括孤岛环境、未认领环境、owner 缺失环境和同模块 `@env_cleanup_candidates` 返回的业务废弃环境。
- 依赖项：`packages/crawler4j/src/core/atm/{execution_runner,dispatcher,repository,ui/task_list_widget.py}`、`packages/crawler4j/src/core/rem/{env_claims.py,cleanup_service.py}`、`packages/crawler4j-contracts/src/{context.py,result.py,lifecycle.py}`
- 排除范围：本轮不恢复人工等待确认状态机；不允许模块发出环境保留、回收或删除指令。

验收标准：

- [x] `UAT-016` Contracts 不再导出 `TaskSignal` / `EnvAction`，SDK scanner 会阻断模块导入这些宿主控制对象
- [x] `UAT-017` `workflow.run(ctx)` 前会按对象图组合顺序调用可选 `setup(ctx, workflow)`；任务终态、setup 异常、运行异常、超时和用户中止都会调用对象 `cleanup(ctx, outcome)` 后统一回收环境
- [x] `UAT-018` 环境管理页 `清理环境` 能统一预览并删除孤岛、未认领、owner 缺失和模块业务废弃环境

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

### `REQ-009` ATM 必须支持环境候选 Service Job 的等待队列与模块候选分配

- 优先级：P1
- 描述：对于使用 `@env_candidates` 的 Service Job，宿主必须把“暂时没有可用候选环境”建模为正式等待状态，而不是直接失败；宿主只应从当前模块声明的候选函数返回集合中分配已授权、就绪且未租约占用的浏览器环境，并按队列语义维持目标并发。
- 用户故事：作为服务运营者或模块开发者，我希望当目标并发大于当前可用候选环境数时，系统能稳定表现为“运行中 + 等待中”，以便服务不会因为账号状态、黑号或环境容量暂时不足而不断失败和重建。
- 前置条件：任务以 Service Job 方式运行，`AcquisitionConfig.mode=select`，运行模板引用当前模块 `candidates/*.py` 中已声明的 `@env_candidates` 同步纯函数。
- 业务规则：
  - 候选环境场景下，“当前轮没拿到环境”属于等待，不属于失败。
  - 目标并发按服务席位表达，业务口径统一为 `运行中 + 等待中 = 目标并发`。
  - 宿主实时执行候选纯函数，候选函数可直接返回 env id 列表或 `EnvCandidates` 链式查询。
  - 宿主只从“当前模块候选集合 + 已绑定当前模块 + `READY` + 浏览器 + 无租约”的环境集合里叫号，不从全局环境池盲抢。
  - 容量扩张时按 FIFO 连续补位；容量收缩时停止继续补位，但不抢占已在运行中的任务。
  - 黑号、风控失效、会员等级、注册时间等业务状态必须写入模块业务数据表，并由候选纯函数实时过滤。
- 依赖项：`packages/crawler4j/src/core/atm/`, `packages/crawler4j/src/core/rem/`, `packages/crawler4j-sdk/`, `docs/04-project-development/04-design/atm-resource-pool-queue-design.md`
- 排除范围：本轮不实现优先级队列、多租户抢占策略、模块自写等待轮询、资源池同步快照或 `selector_name/env_selector/resource_pool` 兼容路径。

验收标准：

- [x] `UAT-024` 给定目标并发 10、当前可用候选 2，当宿主调和候选 Service Job，则系统稳定表现为“运行中 2、等待中 8”，且不会制造 8 个反复失败实例
- [x] `UAT-025` 给定当前状态为“运行中 2、等待中 8”，当同一候选函数可用环境从 2 增长到 5，则宿主会按 FIFO 补位 3 个，结果表现为“运行中 5、等待中 5”
- [x] `UAT-026` 给定环境列表中同时存在其他模块已绑定环境，当宿主为当前候选 Service Job 分配环境，则只会从当前模块已授权候选中分配
- [x] `UAT-027` 给定某个账号被标记为黑号或不可接单，当候选函数实时过滤该账号对应环境，则宿主后续调和等待席位不会再叫号该环境
- [ ] `UAT-028` 给定等待时间超过明确上限，当宿主结束该等待席位，则失败原因收敛为“等待环境超时”类错误，而不是“环境选择返回 none”

当前实现备注：

- 0.4.0 当前实现已切到 `candidates/` + `@env_candidates` 纯函数候选方案，资源池同步快照和宿主资源池工具已移除。
- `UAT-028` 当前实现的错误文案为 `等待环境候选超时: <candidates> (<seconds>s)`，语义已从“环境选择返回 none”收敛为等待超时类错误。

### `REQ-010` Hosted UI 必须支持宿主托管的批量导入能力

- 优先级：P1
- 描述：宿主必须为 Hosted UI 页面和表格提供可声明的自定义 toolbar 按钮，并提供宿主导入弹窗读取 Excel/CSV 文件、剪贴板文本和可选手工录入内容。模块只能接收宿主解析后的结构化 import payload，不直接读取本地文件。
- 用户故事：作为运营或现场支持人员，我希望在模块 Hosted UI 的账号表、Cookie 表或其它业务表中直接批量导入数据，以便不用逐条手工录入，并能看到每个批次和每一行的成功 / 失败状态。
- 前置条件：模块已通过 `@page(...)` 声明 Hosted UI 页面，并通过 `@ui_action` 或 workflow 实现导入处理逻辑；宿主已加载模块 v2 runtime descriptor。
- 业务规则：
  - 页面级和 `DataTable` 工具栏都可以声明自定义按钮。
  - 工具栏按钮可以调用模块 `@ui_action`、调度 workflow，或打开宿主导入弹窗。
  - 宿主导入弹窗必须支持 `.xlsx` / `.csv` 文件上传和剪贴板批量粘贴；手工 JSON / 表格行录入为可选增强。
  - 宿主负责读取文件、解析表头和行数据、限制文件大小与最大行数、处理解析错误和日志脱敏。
  - 模块不得接收本地文件路径、文件句柄或原始二进制内容。
  - 宿主传给模块的 import payload 固定包含 `source_type`、`source_name`、`target_type` 和 `rows[]`，每行包含 `source_row_no`、`business_key`、`payload`、`raw_payload`。
  - 模块返回批次汇总后，宿主必须展示 `batch_id`、总行数、成功写入暂存表行数和失败行数，并可跳转到 `import_data_records` 页面查看该批次。
  - 从暂存表导入业务表的后续动作必须能展示逐条成功 / 失败状态。
- 依赖项：`packages/crawler4j-contracts/src/crawler4j_contracts/hosted_ui.py`, `packages/crawler4j-sdk/src/v2_scanner.py`, `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py`, `packages/crawler4j/src/core/mms/ui/module_ui_runtime.py`, `packages/crawler4j/src/ui/components/data_table.py`, `docs/04-project-development/04-design/hosted-ui-batch-import-design.md`
- 排除范围：V1 不支持任意文件类型、不让模块读取本地文件、不实现通用业务去重规则、不强制宿主提供统一业务暂存物理表。

验收标准：

- [x] `UAT-029` 给定模块页面 schema 声明页面级 toolbar 导入按钮，当宿主渲染页面，则页面工具栏出现对应按钮并保留声明的 `target_type` 和提交动作。
- [x] `UAT-030` 给定模块 `DataTable` 声明表格 toolbar 导入按钮，当宿主渲染表格，则表格工具栏出现对应按钮，并可按 schema 触发 `@ui_action`、workflow 或宿主导入弹窗。
- [x] `UAT-031` 给定用户上传 `.xlsx` 或 `.csv` 文件，当文件类型、大小和行数都在限制内，则宿主解析为行数据；当超出限制或文件类型不允许，则提交前阻断并显示原因。
- [x] `UAT-032` 给定用户从剪贴板粘贴批量表格文本，当文本可按表头和行解析，则宿主生成与文件导入一致的 import payload。
- [x] `UAT-033` 给定宿主打开导入弹窗并完成解析，当用户提交，则模块收到只包含结构化 JSON-compatible 数据的 payload，不包含本地文件路径、文件句柄或原始二进制内容。
- [x] `UAT-034` 给定 payload 行中包含手机号、邮箱、账号名等去重键，当 schema 或模块约定提供映射，则每行 `business_key` 可被填充并用于模块侧去重。
- [x] `UAT-035` 给定模块返回 `batch_id/total_rows/staged_rows/failed_rows`，当宿主收到结果，则展示导入汇总并提供跳转 `import_data_records` 批次明细页的入口。
- [x] `UAT-036` 给定用户在暂存批次页执行“从暂存表导入业务表”，当处理完成，则宿主页面可展示每条记录的成功、失败、跳过重复或校验失败状态。
- [x] `UAT-037` 给定导入字段包含 `token/cookie/password/secret/authorization/credential/passwd` 等敏感名称，当宿主记录日志、错误摘要或任务消息，则对应值不得明文输出。

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

### `NFR-010` 批量导入安全与容量限制

- 指标：默认单文件不超过 10 MB，默认单次不超过 5000 行；敏感字段在宿主日志中 100% 脱敏。
- 约束：宿主只允许 `.xlsx` / `.csv` 文件导入；模块只能接收解析后的结构化 payload；不得把 token、cookie、密码类字段明文写入宿主日志。
- 验证方式：导入弹窗限制单测、解析边界单测、日志脱敏单测、Hosted UI 分发回归。

## 5. 关键流程

1. 维护者通过 `uv` 同步环境并运行测试、文档、build 验证
2. Core 通过 UI 或模块服务加载模块并执行工作流
3. 发布前通过版本、入口、文档与构建结果进行闭环校验
4. 后续迭代通过 `BUG` / `CR` / `TASK` 驱动进入实现阶段
5. Hosted UI 批量导入由宿主读取来源数据并生成 import payload，模块只处理结构化行数据和业务落库

## 6. 风险、假设与待确认问题

### 风险

- 根项目发布入口失真，当前 wheel 可构建但脚本不可运行
- `ctrip` 真实站点完整业务 E2E 尚未回放
- 现有 lint 失败表明代码与脚本质量边界没有稳定定义
- 模块根入口切换为单一新模板后，旧模块升级需要一次性重初始化和业务文件迁移
- 批量导入若缺少宿主统一限制和脱敏，可能把大文件、错误文件类型或 token/cookie/password 明文带入日志与运行链路

### 假设

- 当前维护者接受以本地验证结果而非历史文档口径作为阶段事实
- 首批迭代优先处理发布入口、关键工作流和版本治理，而非新增业务功能
- 模块级通用分发逻辑可以集中沉淀到 SDK，而不需要每个模块重复维护一份
- 旧模块作者可以接受“按最新模板重新初始化”作为唯一升级路径
- 模块作者可以接受“宿主读取文件、模块只收结构化 payload”的安全边界

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
| v1.4 | 2026-06-19 | 新增 `REQ-010` / `NFR-010`，登记 Hosted UI 宿主托管批量导入能力 | `CR-016` |
| v1.5 | 2026-06-19 | 完成 `REQ-010` / `NFR-010` 本地实现与 `TC-060` 验证，Hosted UI 批量导入进入回归维护和真实业务模块接入阶段 | `CR-016` |

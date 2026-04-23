# 接口与契约设计

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 模块开发者  
**上游输入：** `system-architecture.md` | `module-boundaries.md` | 现有 SDK / Contracts / module manifests  
**下游输出：** `docs/04-project-development/05-development-process/implementation-plan.md` | `docs/04-project-development/06-testing-verification/test-plan.md`
**关联 ID：** `API-001`, `API-002`, `API-003`, `API-004`, `API-005`, `API-006`, `API-007`, `API-008`, `API-009`, `REQ-001`, `REQ-002`, `REQ-003`, `REQ-004`, `REQ-006`, `REQ-007`, `REQ-008`, `REQ-009`, `BUG-013`, `CR-005`, `CR-008`, `CR-009`, `CR-010`, `CR-011`, `CR-012`, `CR-014`, `TASK-024`, `TASK-026`, `TASK-028`
**最后更新：** 2026-04-23

## `API-001` Root App Entry Contract

| 项目 | 内容 |
|---|---|
| 目标 | 启动桌面应用 |
| 当前真实入口 | `src.ui.app:main` |
| 当前开发入口 | workspace 根执行 `uv run python -m src.ui.app` |
| 打包态前置动作 | Windows 打包态在 GUI 初始化前先执行 Velopack `App().run()`；内嵌 debug worker / debugpy adapter 子进程必须先短路，不参与宿主自更新 bootstrap |
| 当前状态 | 已对齐，需持续回归验证 |
| 关联项 | `BUG-001`, `TASK-002` |

## `API-002` Module Runtime Contract

| 项目 | 内容 |
|---|---|
| Manifest 文件 | `module.yaml`（可附带 `config_defaults` 初始化模板） |
| 宿主入口文件 | 模块根 `__init__.py` |
| 必需入口 | `run(context)` |
| 标准运行时文件 | `module_runtime.py` |
| 可选 hooks | `prepare_env`, `init_env`, `before_run`, `on_success`, `on_failure`, `on_timeout`, `on_cleanup` |
| 环境选择器 | 通过 `@env_selector(...)` 在 `module_runtime.py` 中声明，供 ATM “选择环境”模式调用 |
| 当前实现 | 根 `__init__.py` 已收敛为稳定薄壳，默认入口组装逻辑由 `ModuleAssembler` 提供；选择环境不再接受规则树，只接受模块回调 |
| Core 扩展入口 | `context.tools.call("<namespace>.<action>", **kwargs)` |
| 生命周期规则 | `on_cleanup` 是终态清理 hook；对已建立 `TaskContext` 的任务，ATM 会先执行 `on_cleanup`，再执行环境关闭/删除；cleanup 期间 `context.runtime["env_action"]` 先暴露计划动作（`success=None`），环境动作完成后再写回最终结果；若任务在环境申请/启动阶段就失败，不保证会进入 `on_cleanup`；手动中止运行中任务时，ATM 会主动 cancel 当前模块协程，`TaskContext.wait()` / `run_subtask()` 会尽快抛出 `asyncio.CancelledError` 以配合收口；`on_success` / `on_failure` / `on_timeout` / `on_cleanup` 与环境动作均受宿主超时保护，避免终态收尾把任务永久卡在 `running`；其中 `on_cleanup` 当前默认最大执行时间为 `120s`，其余终态 hook 与环境动作保持更短超时 |
| 默认工作流解析 | `context.runtime["workflow"]` -> `module_runtime.DEFAULT_WORKFLOW` -> `module.yaml.workflows[0].name` |
| 发现错误可见性 | `ModuleAssembler` 发现 `tasks/` / `workflows/` import 失败时，必须记录 import 目标、异常类型与 traceback；若当前请求命中失败条目，`run()` 需附带 discovery hint，而不是只报泛化的“not found” |
| Hosted UI 契约 | 页面创建/刷新时先同步调用根模块 `declare_ui(context)`；页面只通过 `ui.declare_page` 声明，`DataTable` 仅作为页面内组件，页面数据由 `load_handler` / `query_handler` 返回纯结构化对象 |
| `TaskSignal` UI 契约 | `TaskSignal.wait_for_confirmation(..., payload={"confirmation": ...})` 会把完整 `signal` 快照持久化到任务记录，并发布 `task.signal` 事件；ATM 详情页按 `payload.confirmation` 渲染结构化确认面板，若缺少该块则退回展示 `message` 与 payload 键值 |
| DevLink 调试语义 | 模块来源为 `DevLink` 时，详情页数据表刷新会以 `devel_mode=true` 重建本地 hook 上下文，便于联调最新 UI 声明 |
| DevLink 普通执行语义 | ATM 普通执行 `DevLink` 模块时，也会注入 `devel_mode=true`；`ModuleService` 对同一个 `TaskContext` 只在首次加载时强制 reload 一次，后续 hook / `run()` 复用同次执行内已加载模块 |
| 升级策略 | 旧模块统一按最新模板重新初始化；不再为旧式完整 `__init__.py` 模板提供兼容承诺 |
| 当前风险 | 真实站点 E2E 仍未覆盖；动态加载的模块扩展点仍需依赖回归测试保持稳定 |
| 关联项 | `TASK-003`, `TASK-013` |

## `API-008` Hosted Module UI Contract（V1 已实现）

| 项目 | 内容 |
|---|---|
| 目标 | 模块 UI 不再直接导出 `PyQt6` 页面，而是声明宿主管理页 schema，由宿主统一渲染 |
| Manifest 形态 | `ui_extension.pages[]`，每页只声明 `id`、`label`、`icon` |
| 模块 UI 声明入口 | `module_runtime.py` 中的 `declare_ui(context)` |
| 新能力入口 | `context.tools.call("ui.declare_page", ...)` |
| 宿主公开控件 | `Page`、`Section`、`Text`、`Button`、`DataTable` |
| `DataTable` V1 范围 | 页面内复合组件；数据源只支持 `binding`、`rows`、`query_handler`；字段类型最少支持 `text`、`number`、`int`、`bool`、`select` |
| 宿主动作范围 | `Button.action` 第一版只开放 `reload`、`open_page` |
| 明确删除 | `micro_app`、`ui:*`、代码型页面脚手架、trust gate / allowlist / `trusted`、`entry`、`core:data_table`、`ui.declare_data_table` |
| 设计输入 | `module-hosted-ui-framework.md` |
| 当前验证基线 | Core / SDK / integration / acceptance 已跑通 hosted page V1 定向回归；模块详情页、CLI 和 schema gate 已统一到新契约 |
| 当前状态 | 已本地实现并通过定向验证；PR 收口与真实业务模块接入验证待继续推进 |
| 关联项 | `CR-011`, `TASK-025` |

## `API-009` Module Entity Table View Contract

| 项目 | 内容 |
|---|---|
| 目标 | 在模块 `custom_table` 实体表之上提供 manifest 驱动的数据库视图和命名查询能力 |
| 新事实源 | `module.yaml.data.views[]`、`module.yaml.data.queries[]`、`data.db.module_db_views` |
| 注册入口 | `module.yaml.data` + `data/sql/views/*.sql` + `data/sql/queries/*.sql` |
| 查询接口 | `ctx.tools.call("db.run_query", ...)`、`ctx.tools.call("db.query_view", ...)` |
| SQL 契约 | 模块只能执行宿主已注册的 `SELECT/WITH SELECT` SQL；源表通过 `{{resource:<resource_id>}}` 占位引用；禁止未注册 SQL |
| UI 接入 | 模块页面通过内联 `DataTable(query_handler)` 调用 `db.query_view` / `db.run_query`，宿主只负责表格交互与渲染 |
| 生命周期 | 宿主在模块加载/安装时校验、同步、建表、建视图、导种子，并在卸载时统一清理 |
| 当前状态 | 已切到 manifest 驱动契约；旧 `db.declare_db_view` 运行时声明口已退出正式协议 |
| 关联文档 | `module-entity-table-view-design.md` |
| 关联项 | `CR-014`, `TASK-028` |

## `API-005` Module Config / Runtime / Data Contract

| 项目 | 内容 |
|---|---|
| 静态清单 | `module.yaml`，承载模块发现、UI / workflow 声明，以及只读初始化模板 `config_defaults` |
| 持久配置 | `config.db.module_config_entries`；模块运行时只通过 `ctx.get_config()` / `ctx.config` 读取 |
| 配置编辑格式 | 模块详情页 `配置` 标签统一使用 YAML 编辑，但数据库仍是事实源 |
| 配置初始化规则 | 仅首次加载模块时按 `module.yaml.config_defaults` 初始化一次；后续升级不自动覆盖，手动恢复默认需用户确认 |
| 运行态元数据 | `ctx.runtime`；当前固定承载 `workflow`、`execution_params`、`job_params`、`params`、`devel_mode`、`creation_params`、`env_action` |
| 运行中共享内存 | `ctx.state`；仅用于当前一次任务 / workflow 运行内共享变量 |
| 页面 schema | `data.db.module_pages`，统一通过 `ui.declare_page` / `ui.get_page` 访问 |
| 快照型业务数据 | `module.yaml.data.resources[]` 统一声明 `managed_dataset` / `custom_table`；其中 `managed_dataset` 实际落在 `data.db.module_datasets`（V3：`record_key` / `run_status` / `record_status`）+ `data.db.module_dataset_manifests`，`custom_table` 落在受控实体表 `module_name_resource_id`，并由 `schema_version` / `schema_json` / `indexes_json` 描述真实列结构；业务数据统一通过 `db.get_record` / `db.list_records` / `db.replace_records` 访问 |
| 事件型业务数据 | `data.db.module_audit_events`，统一通过 `db.append_event` / `db.query_events` 访问 |
| 短期状态与锁 | `state.db.kv_store`；只承载轻量状态与锁，不再作为正式业务表存储 |
| 当前实现说明 | `db.list_records` / `db.replace_records` 已按资源 `storage_mode` 路由；`custom_table` 现为 schema 驱动的受控实体表，不再写入统一 `record_json` 容器。卸载时宿主会按 `cleanup_policy` 统一删除托管记录、删除/保留自定义物理表并在客户端列出高风险清理清单；当前运行时代码仍不包含旧 `state.db.kv_store` 模块表数据自动迁移逻辑，旧数据需要显式迁移或人工导入 |
| 关联文档 | `module-config-runtime-data-contract.md` |
| 关联项 | `CR-003`, `CR-012`, `TASK-026` |

## `API-006` Module Audit Event Contract

| 项目 | 内容 |
|---|---|
| 存储表 | `data.db.module_audit_events` |
| 写入接口 | `ctx.tools.call("db.append_event", ...)` |
| 查询接口 | `ctx.tools.call("db.query_events", ...)` |
| 数据语义 | append-only 审计事件，不再按整包 JSON 覆盖历史 |
| 支持字段 | `dataset`, `event_type`, `entity_key`, `run_id`, `previous_status`, `next_status`, `result`, `reason`, `payload`, `created_at` |
| 查询维度 | `dataset / entity_key / event_type / run_id / time range / limit / offset / order` |
| UI 边界 | Hosted UI 只负责渲染页面和表格组件，不承担审计事件编辑语义 |
| 当前范围 | 已提供独立存储与查询能力；retention / archive / 自动迁移脚本暂未纳入 |
| 关联文档 | `module-config-runtime-data-contract.md`, `reference-core-capabilities.md` |
| 关联项 | `REQ-008`, `CR-008` |

## `API-003` SDK / Contracts Package Contract

| 项目 | 内容 |
|---|---|
| SDK 包名 | `crawler4j-sdk` |
| Contracts 包名 | `crawler4j-contracts` |
| CLI 入口 | `crawler4j_sdk.cli.commands:main` |
| 当前能力 | `ModuleAssembler` 已作为统一模块入口组装 helper 落地；`TaskContext` 已收敛为 `tools` 统一扩展入口；`TaskSignal` 已成为模块到 ATM 的正式流程信号；CLI 已重构为 `module / task / workflow / page / env-selector / config / package / release / host / check` 分组体系 |
| 当前状态 | 本地 build 成功，help 可运行；模块入口自动托管、重初始化路径与集成测试已完成 |
| 关联项 | `REQ-003`, `REQ-006` |

## `API-004` Release Metadata Contract

| 项目 | 内容 |
|---|---|
| 根应用版本事实源 | `packages/crawler4j/pyproject.toml` |
| 运行时版本读取 | `packages/crawler4j/src/core/system/version_service.py` 从包元数据或 `packages/crawler4j/pyproject.toml` 解析 |
| 最近正式发布 | Git tag |
| 子包版本 | `packages/crawler4j-sdk/pyproject.toml`, `packages/crawler4j-contracts/pyproject.toml` |
| Windows 发布元数据 | `scripts/package_windows_release.py` 负责把 `feed_url / pack_id / channel` 收口到 Windows 宿主目录内的 `crawler4j.update.json`，供 Velopack 运行时读取 |
| 桌面更新后端 | macOS 打包态走 Sparkle；Windows 打包安装态走 Velopack；统一对 UI 暴露为 `UpdateService` |
| 发布文档 | `docs/04-project-development/07-release-delivery/version-governance.md`, `docs/04-project-development/07-release-delivery/release-notes.md` |
| 当前状态 | 已收口：当前工作区版本与最近正式发布已被明确区分 |
| 关联项 | `CR-001`, `TASK-004` |

## `API-007` Fixed-Pool Service Queue Contract（V1 已实现，本地验证通过）

| 项目 | 内容 |
|---|---|
| 适用场景 | 固定环境池 + Service Job 保活并发，不再适合“拿不到环境就失败”的运行模式 |
| 目标语义 | `运行中 + 等待中 = 目标并发`；资源不足属于正常等待，不属于失败 |
| 进入队列前提 | 只有 `JobType.SERVICE + AcquisitionConfig.mode=select + resource_pool 非空` 时才进入固定池等待语义；`selector_name` 可选，但 `selector_name` 和 `resource_pool` 不能同时为空 |
| 资源池定位 | 宿主只在“当前模块 + 当前资源池 + `eligible=true` + `READY` + 无租约占用”的环境集合里分配环境 |
| 卡片存储 | 宿主内部 `env_metadata`；建议 `namespace=scheduler.resource_pool`，key 由宿主按“根模块名归一化 + pool_name”拼接，例如 `demo.foo` -> `demo:<pool>` |
| 卡片字段 | 至少包含 `module_name`、`pool_name`、`eligible`、`reason`、`exclusive`、`updated_at` |
| 模块开发者职责 | 通过 SDK helper 维护资源池资格卡片，并提供全量重建；不负责排队、轮询和补位 |
| 宿主职责 | FIFO 等待队列、容量变化补位、环境租约治理、终态收口 |
| 当前 V1 形态 | `AcquisitionConfig.resource_pool` + `env.bind_resource_pool` / `env.mark_resource_pool_eligible` / `env.mark_resource_pool_ineligible` / `env.remove_resource_pool` / `env.replace_resource_pool_snapshot` + Service Job `PENDING` 等待补位 |
| `replace_resource_pool_snapshot` 语义 | `entries` 是当前资源池的完整权威列表；未出现的环境卡片会被删除，不是增量 patch |
| 容量变化触发 | 环境释放、新环境可分配、异常/暂停环境恢复、模块更新资格卡片；控制器启动时还会先做 bootstrap 调和，作业激活/更新时会定向调和，另有运行在主 async loop 上的轻量异步巡检兜底 |
| 环境占用规则 | 占用不移出资源池；资源池归属和运行中占用分离 |
| 黑号规则 | 先把环境标成 `eligible=false` 并写入原因，再按业务策略销毁或保留待人工处理 |
| 选择器分层 | `resource_pool` 做宿主级粗筛；若配置了 `selector_name`，宿主只把当前池内候选交给它做细粒度选择；若 `selector_name` 为空，则不会调用 `select_env`，宿主直接取当前池内第一个可分配候选；这对从旧 selector 模块迁移来说是显式行为变化，不是无害默认，且当前实现不承诺额外业务排序 |
| selector 作者入口 | `selector_name` 指向 `module_runtime.py` 里通过 `@env_selector(...)` 声明的 selector；运行时 `select_env(...)` 是框架包装壳，不是模块作者另写的新 hook |
| 队列模式下无命中语义 | 只有 `resource_pool` 非空路径里，当前轮没命中才回到等待；没有 `resource_pool` 的旧选择模式里，`selector` 返回 `None` 仍然直接失败 |
| 候选竞争语义 | 固定池候选如果在 `get_env` / 租约阶段被其他任务先抢走，或候选在快照之后被资源池卡片改成不可发号，当前任务回到等待席位，不直接记失败；只有 selector 选了候选集外环境或其他真实异常才进入失败收口 |
| 等待状态口径 | 固定池等待会复用底层 `TaskStatus.PENDING`；UI 展示为 `等待环境`，等待中的 `task.message` 为 `等待环境池工位: <pool>` |
| 等待超时口径 | `wait_timeout` 同时用于环境租约获取与固定环境池 `PENDING` 等待席位收口；固定池等待从第一次写下 `waiting_since` 开始计时，`wait_timeout=0` 时当前不会自动超时收口；当前实现不会单独用它中断 `select_env(...)` 本身；失败文案为 `等待环境池工位超时: <pool> (<seconds>s)`，且与 `execution.timeout` 分离 |
| `KEEP_ALIVE` 环境口径 | `KEEP_ALIVE` 只表示保留现场，不表示重新回池；保留后的 `RUNNING` 环境不会被固定池当成可发号工位 |
| `exclusive` 当前语义 | V1 只把它写进资格卡片；当前分配器不依据它改变调度路径，不应把它当成路由开关 |
| `env_id` 口径 | helper 使用的 `env_id` 是宿主 `environments.id` 主键；`prepare_env` 阶段的 `TaskContext.env_id` 当前固定为 `0`，不应用于写资源池卡片 |

## 设计结论

- 本项目的关键“接口”不是 HTTP API，而是运行入口、模块契约、SDK/Contracts 包接口和发布元数据接口。
- 模块开发时还必须把“配置 / 运行态 / 单次运行内内存 / 业务数据 / 短期状态”视为不同契约，不能混用。
- 当前版本治理规则已经明确：根应用 `pyproject.toml`、运行时版本读取、最新正式 tag 和子包版本线各自职责清晰。

## 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-22 | 将 `API-008` 从“设计已定未落地”更新为 hosted page V1 已本地实现：`ui_extension.pages[]`、`ui.declare_page`、宿主页渲染器与 SDK CLI 已同步完成 | Codex |
| 2026-04-22 | 新增 `API-008`，登记模块宿主管理页与最小化 UI 框架的目标契约 | Codex |
| 2026-04-22 | 补记 root app 在 Windows 打包态的 Velopack 启动前置动作，并将 Windows `crawler4j.update.json` 与统一 `UpdateService` 后端分派纳入发布元数据契约 | Codex |
| 2026-03-26 | 初始接口与契约设计摘要 | Codex |
| 2026-03-31 | 增补模块根入口自动托管的契约演进设计 | Codex |
| 2026-04-08 | 补记 Hosted UI 本地声明 hook 与 DevLink 刷新调试语义 | Codex |
| 2026-04-15 | 将 Core 扩展能力收敛到 `TaskContext.tools` 统一工具接口 | Codex |
| 2026-04-15 | 固化 `on_cleanup` 终态规则，并补记 `TaskSignal` 为正式流程信号 | Codex |
| 2026-04-16 | 补记 `TaskSignal.wait_for_confirmation` 的结构化确认面板协议、任务快照持久化与 `task.signal` 事件 | Codex |
| 2026-04-16 | 补记 `ModuleAssembler` 发现错误可见性，以及 DevLink 普通执行的一次性 reload 语义 | Codex |
| 2026-04-17 | 增补 `API-005`，收口模块配置、运行态、共享内存与数据表契约 | Codex |
| 2026-04-18 | 新增 `API-006`，将模块快照数据与审计事件拆成两条正式持久化契约 | Codex |
| 2026-04-19 | 新增 `API-007`，收口固定环境池 Service Job 的等待队列与资源池资格卡片契约 | Codex |
| 2026-04-19 | `API-007` V1 落地：宿主等待席位、资源池资格 helper 与运行模板 `resource_pool` 契约已实现 | Codex |
| 2026-04-21 | 刷新 `API-005` 的文档元数据，确认 `module_datasets` 逐行持久化已进入正式契约口径，并补记 `module_dataset_manifests` 负责 dataset 级元数据 | Codex |
| 2026-04-23 | 刷新 `API-005`：新增 `module_data_resources`、`managed_dataset/custom_table` 两种存储模式、`module_datasets` V3 记录状态字段与 `db.declare_data_resource` 契约，并补记卸载清理策略 | Codex |
| 2026-04-23 | 新增 `API-009`，正式登记模块实体表视图与分析查询能力设计 | Codex |

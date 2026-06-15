# 模块配置、运行态与数据契约

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 模块开发者  
**关联 ID：** `API-005`, `API-006`, `API-008`, `API-009`, `API-010`
**最后更新：** 2026-04-30

## 1. 设计目标

本契约用于统一模块开发者在运行时面对的六类核心对象：

1. 配置
2. 运行态元数据
3. 单次运行内共享内存
4. 页面 schema
5. 模块数据资源 / 只读数据库视图
6. 短期状态

目标不是再引入多套抽象，而是把当前已经落地的事实源固定下来，避免模块作者继续在 `module.yaml`、模块目录、自定义 YAML、`ctx.runtime`、`ctx.state`、旧 `ctx.tools.call("db.*")` 和 UI schema 之间混用。

## 2. 统一分层

| 类别 | 事实源 | 模块读取方式 | 模块写入方式 | 说明 |
|---|---|---|---|---|
| 静态清单 | `module.yaml` | 宿主扫描和装配 | 禁止 | 放模块名、版本、升级源，以及一次性初始化模板 `config_defaults`；运行能力、页面和环境候选不再写入清单 |
| 持久配置 | `config.db.module_config_entries` | `ctx.get_config()` / `ctx.config` | 禁止 | 宿主统一维护；模块运行时只读 |
| 运行态元数据 | `ctx.runtime` | `ctx.runtime[...]` | 禁止 | 由 ATM / Debug / Core 注入 |
| 单次运行内共享内存 | `ctx.state` | `ctx.state[...]` | 允许 | 只在当前一次任务 / 工作流执行期间有效 |
| 页面 schema | `pages/*.py` / `pages/<group>/*.py` 中的 `@page(...)` 与页面 handler | 宿主通过 v2 runtime descriptor 读取 | 禁止在运行时代码里动态声明 | 宿主管理页面 schema；模块只声明 Hosted UI 页面，不再声明独立数据表页；正式 Hosted UI 刷新链路不再依赖 `data.db.module_pages` |
| UI 操作 | `pages/*.py` / `pages/<group>/*.py` 中的 `@ui_action(...)` | 宿主通过 v2 runtime descriptor 读取 | 不执行浏览器自动化，不调用 `ctx.run_page_action(...)` | Hosted UI 按钮、CRUD、刷新、导出等用户命令入口；可通过 `ctx.db` 读写模块数据 |
| 页面动作 | `tasks/*.py` 中的 `@page_action(...)` | workflow/component 通过 `ctx.run_page_action(...)` 调用 | 不作为 Hosted UI 用户入口，不嵌套调用另一个 `@page_action` | 浏览器页面自动化步骤；公共步骤应抽到 helper、browser adapter 或 use case |
| 模块数据资源 | `@data_table` + `data.db.module_data_resources` + `data.db.module_datasets` / 模块自定义物理表 | `ctx.db.from_("resource_id")` | `ctx.db.into("resource_id").replace/upsert/update_where/delete_where(...)` 或 `ctx.db.batch().execute()` | `managed_dataset` 适合低频稳定快照，`custom_table` 适合并发更新、计算或明细表 |
| 模块审计事件 | `data.db.module_audit_events` | `ctx.db.audit("dataset").query(...)` | `ctx.db.audit("dataset").append(...)` | append-only 历史事件，不进入 `module_datasets` |
| 只读数据库视图 | `@data_view` + `data.db.module_db_views` | `ctx.db.from_("view_id")` | 禁止 | 基于 `custom_table` 的只读 read model；由宿主创建真实 SQLite view |
| 短期状态 | `ctx.state` | `ctx.state[...]` | `ctx.state[...] = ...` | 仅当前一次任务 / workflow 内有效，不落正式业务库 |

`ctx.captured_data` 不再作为正式契约存在。临时小状态统一放 `ctx.state`，任务输出统一放 `TaskResult.data`，需要跨运行持久化的数据统一走 `ctx.db`。

## 3. 配置契约

- `module.yaml` 是唯一模块清单，可额外声明只读默认模板 `config_defaults`，但不是可变配置存储。
- 模块可变配置统一持久化到 `config.db.module_config_entries`。
- 模块运行时代码只能通过 `ctx.get_config()` 或 `ctx.config` 读取配置。
- 模块不得自行读取宿主配置数据库。
- 除 `module.yaml.config_defaults` 外，不再承认模块目录里的第二套配置事实源，例如 `module.settings.yml`、`strategy.yaml`、`config_schema.json`。
- 宿主模块详情页的“配置”标签只承担配置编辑入口：前端使用 QScintilla YAML 编辑器提供行号、折叠、语法高亮与校验错误标记；保存前统一调用独立 YAML 验证层，要求顶层为 YAML 映射对象并拒绝重复键，保存后再规范化为块格式 YAML 展示。

### 3.1 环境选择与候选声明

- 选择已有环境的运行模板支持两种方式：固定 `AcquisitionConfig.env_id`，或引用模块 `candidates/*.py` 中声明的 `@env_candidates`。
- 固定 `env_id` 是默认交互，用于用户明确指定某个环境执行；执行链不会进入候选等待队列。
- 宿主客户端的固定环境下拉只展示当前模块可用环境：`READY`、浏览器类型、无租约，且 `host.env_claim.owner_module` 为空或等于当前模块。
- 环境候选必须在 `candidates/*.py` 中声明，入口是 `@env_candidates(name=...)` 同步纯函数。
- `AcquisitionConfig.candidates` 只能引用当前模块已经声明过的候选函数。
- 候选函数可以直接返回 env id 列表，也可以返回 `EnvCandidates` 链式查询对象。
- 模块内账号状态、黑号状态、注册时间、会员等级等过滤条件必须写在候选纯函数或它组合调用的本模块纯函数中，通过 `ctx.db` 实时读取模块业务表。
- `module.yaml.resource_pools[]`、`AcquisitionConfig.resource_pool`、资源池资格卡片和资源池同步工作流不再是 0.4.0 正式契约。

### 3.1.1 环境清理候选声明

- 环境清理候选必须在 `cleanups/*.py` 中声明，入口是 `@env_cleanup_candidates(name=...)` 同步纯函数。
- 清理候选函数可以直接返回 env id 列表，也可以返回 `EnvCandidates` 链式查询对象。
- 清理候选函数运行面只允许只读 `ctx.db`，不暴露 `ctx.tools`；模块只声明候选集合，不执行删除动作。
- 宿主客户端触发批量清理时会汇总所有模块声明，按 env id 去重，展示来源模块和候选函数，用户确认后再执行。
- 删除前宿主必须二次校验 REM 当前状态，只允许删除 `READY/PAUSED`、无租约、无关联任务的环境。

### 3.2 Workflow 与运行模板对象配置

Workflow 不在 `module.yaml` 中声明 `parameters[]`。0.4.0 正式契约中，Workflow 只通过构造函数接收宿主装配对象，普通可配置值下沉到 component 的 `object_param(...)`，对象依赖通过 `object_inject(...)` 或装饰器 `inject` 声明。

运行模板页通过公共 `ObjectGraphTree` 组件按 workflow 根对象递归展示树形对象图，层级为 `workflow -> interface 绑定行 -> 子 interface/参数`。interface 绑定行左侧显示 interface 的 `label(name)`，右侧下拉选择显示 component 的 `label(name)`；注入路径只作为绑定 key 与提示信息保留。interface 与 component 节点优先展示装饰器 `label`，模块可用中文 label 提升可读性。用户除了选择 interface 绑定到哪个 component，还可以直接在绑定行下填写 `object_param(...)` 声明的创建参数；保存后分别写入 `RunProfile.execution.object_bindings` 与 `RunProfile.execution.object_params`。运行时由 Core 为每个 task/env 创建独立对象图，模块代码不通过 `ctx.runtime["params"]` 读取 workflow 入参。

约束：

- `module.yaml.workflows[].parameters[]` 不是 0.4.0 正式字段。
- `module.yaml` 不承载 workflow parameters、data、`ui_extension` 或 `resource_pools`。
- `object_bindings` 只记录接口到具体 component 的绑定。
- `object_params` 只记录 component 创建所需参数。
- 宿主运行模板 UI 在 `QComboBox` 切换装配对象时，不得在 `currentIndexChanged` 回调里同步销毁并重建对象装配控件树；必须延后到下一轮事件循环，避免 macOS Qt accessibility 原生崩溃。
- 业务过滤条件优先写入模块数据表，由 `@env_candidates` 或 workflow 主体通过 `ctx.db` 读取。

## 4. 运行态元数据契约

`ctx.runtime` 是宿主拥有的只读运行态字典。当前固定字段如下：

| 键 | 含义 |
|---|---|
| `workflow` | 本次执行命中的工作流名 |
| `object_bindings` | 运行模板保存的接口实现绑定 |
| `object_params` | 运行模板保存的 component 对象参数 |
| `devel_mode` | 当前是否为 DevLink 开发态 |
| `creation_params` | 本次环境创建参数；已有环境导入时也通过这里透传来源元数据 |
| `candidates` | 当前运行模板绑定的环境候选函数名；仅在 `mode=select` 且非固定 `env_id` 时注入 |
| `candidate_params` | 当前运行模板传给候选函数的参数字典 |
| `env_recycle` | 本次终态环境回收结果 |

约束：

- 模块不得覆盖或重写这些键。
- `workflow`、`devel_mode`、`creation_params` 不能再混进 `ctx.config`。
- 模块不得把 `object_bindings` / `object_params` 当成 workflow 入参字典读取；它们只服务 Core 对象图装配。
- 本次执行的临时变量也不要写入 `ctx.runtime`，应放到局部变量或 `ctx.state`。
- `ctx.runtime["candidates"]` 只表示“本次任务通过哪个已声明候选函数拿环境”，不是模块业务配置事实源。
- `ctx.runtime["candidate_params"]` 只承载运行模板传入候选函数的参数；候选函数仍应从模块业务表实时读取账号状态。

### 4.1 已有环境导入场景

当宿主通过 `环境管理 -> 从已有环境导入` 把来源环境关联到已有“执行一次”任务时，`ctx.runtime["creation_params"]` 还会补充以下键：

| 键 | 含义 |
|---|---|
| `provider` | 外部环境来源，例如 `virtual_browser` |
| `name` | 来源系统中的环境名称，也是宿主判定是否已导入的唯一性字段之一 |
| `provider_env_id` | 来源系统中的环境 ID，用于模块记录导入来源 |
| `provider_env_name` | 来源系统中的环境名称，用于模块记录导入来源；当前与 `name` 保持一致 |
| `import_mode` | 固定为 `existing_env` |
| `import_group_id` | 同一次多环境导入的批次 ID；单环境导入也会生成，用于模块日志、审计或幂等关联 |

该场景还有补充约束：

- 宿主仍必须保证 `ctx.env_id` 与 `ctx.page` 可用，模块不需要自己重新绑定浏览器上下文。
- 标准浏览器交互由宿主 `browser.*` tool 提供；模块直接调用 `ctx.tools.call("browser.goto" | "browser.click" | "browser.type" | ...)`，`ctx.page` 主要用于读取与宿主未覆盖能力。
- `browser.*` 的拟人化行为由宿主统一治理，包括分段停顿、导航前后扫描、随机落点、鼠标 dwell、自然输入纠错概率、敏感输入保护与惯性滚动；模块不应在本地重复实现同类 click/type/drag/scroll helper。
- 宿主用 `(provider, name)` 判定导入唯一性；来源系统中的其他扩展元数据不写入环境表，也不作为重复导入判断依据。
- 0.4.0 不再通过 `module.yaml.workflows[].host_scenarios` 声明适配提示；已有环境导入能力必须由 workflow 装饰器声明：`@workflow(..., host_scenarios=["existing_env_import"])`。
- 宿主导入对话框和导入服务只允许选择已声明 `existing_env_import` 的 workflow；未声明的普通 workflow 不会出现在导入列表中，服务端也会拒绝调度。
- 多环境导入时，宿主把每个环境作为同一 Job 下的一条 Task 运行实例；并发上限来自该 Job 的 `concurrency_target`，不会按选择环境数量无限制打开窗口。

### 4.2 当前环境代理读取

模块如果需要读取当前环境绑定的代理 IP、端口、用户名、密码或代理 URL，应通过宿主工具面读取，不直接查询 REM/IP 池内部表：

```python
proxy = await ctx.tools.call("env.get_proxy")
```

返回值以只读快照为准：

| 键 | 含义 |
|---|---|
| `mode` | 当前环境代理模式，例如 `none`、`static`、`pool` |
| `source` | 数据来源，`ip_pool` 表示来自 IP 池绑定，`proxy_config` 表示只能从环境代理配置回退解析 |
| `ip_entry_id` | IP 池条目 ID；新绑定会直接写入，旧环境首次读取时会按 pool/static 信息懒回填 |
| `pool_id` | 代理池 ID，若没有池绑定则为空 |
| `protocol` / `type` | 代理协议或条目类型 |
| `host` / `port` | 代理地址与端口 |
| `username` / `password` | 代理认证信息；没有认证时为空 |
| `proxy_url` | 宿主可解析出的完整代理地址 |
| `resolved` | 是否成功解析到有效代理信息 |
| `fallback` | 是否从旧 `ProxyConfig` 信息回退解析 |

`env.get_proxy` 只读取当前 task 绑定环境；没有 `ctx.env_id`、环境不存在或没有代理配置时返回 `resolved=False`，模块应按“无代理”路径处理。

## 5. 页面 schema 契约

### 5.1 页面声明

页面 schema 只能通过 `@page(...)` 声明；正式 Hosted UI 链路会扫描 v2 runtime descriptor，并把声明结果缓存到当前 bridge 内存中供 `ui.get_page` / renderer 消费，不再把 `data.db.module_pages` 作为正式渲染事实源。

正式契约：

- `@page(menu=True)` 只声明导航元信息
- 页面 load handler 由 `@page` 装饰函数提供
- 页面按钮和 CRUD handler 由 `@ui_action` 装饰函数提供，schema 使用 `type: "ui_action"`
- `ui.get_page` 只读取页面 schema
- 正式页面链路固定为 `@page -> Page.children[] 内联 DataTable -> query_handler`
- 不再存在 `ui.declare_data_table` / `ui.get_data_table`

### 5.2 页面数据

页面数据只允许通过两类同步函数提供：

- `load_handler(context, page_id, params=None)`
- `query_handler(context, query: HostedDataTableQuery) -> HostedDataTableQueryResult`

模块可以在这些函数中调用：

- `ctx.db.from_(...)`
- `ctx.db.audit(...).query(...)`
- `ctx.tools.call("ui.get_page", ...)`

页面 load/query handler 使用只读运行面；写入数据、导出、刷新和其它用户命令应放到 `@ui_action`。宿主只负责接收结构化返回值并渲染，不解释业务语义。

`DataTable.table_id` 只是页面内 UI 组件实例 ID，用于宿主定位刷新目标；它不是数据库资源 ID，不传给 `query_handler`。一个内联表格可以由一个或多个 `ctx.db.from_(...)` 查询组装，返回值必须固定为 `HostedDataTableQueryResult[RowT]`。`HostedDataTableQuery.search_fields` 来自 `DataTable.columns` 中显式 `searchable=True` 的列 `key`，未声明时默认不可搜索；`sort[].field` 来自可排序列的 `key`，排序既可由表头点击触发，也可由宿主工具栏的排序字段/方向控件触发；handler 不应信任或使用 schema 外字段。`type="select"` 且带 `options` 的 searchable 列会被宿主渲染为快速筛选下拉，筛选值写入 `HostedDataTableQuery.params[column.key]`。`params` 同时承载页面导航参数和表格筛选参数，宿主合并时表格筛选参数优先。

### 5.3 `DataTable` 组件

`DataTable` 只是页面 schema 的子组件。

数据源只支持：

- `binding`
- `rows`
- `query_handler`
- `managed_resource`

正式宿主页里的可交互表格统一走内联 `DataTable(data_source.type="query_handler")`。

- `query_handler` 是正式查询链路，负责把过滤、排序、分页路由到 `ctx.db` fluent API
- `binding` / `rows` 只用于页面内静态或局部数据，不构成另一条宿主页注册链路
- 表格交互由宿主统一处理，但数据查询和写回策略由模块自行决定

## 6. 模块数据与只读数据库视图契约

### 6.1 快照数据位置

- `@data_table` 是表资源的唯一声明入口，扫描结果必须进入 manifest lock
- `managed_dataset` 模式下，`ctx.db.from_(...)` / `ctx.db.into(...).replace(...)` 读写的快照记录持久化到 `data.db.module_datasets`
- `custom_table` 模式下，宿主会在模块加载/安装时创建受控物理表 `module_name_resource_id`
- 审计事件不建模为 `resources[]`，只通过 `ctx.db.audit("dataset")` 写入和查询 `data.db.module_audit_events`
- 未注册的 `resource_id` 会直接报错；宿主不再按资源名隐式补建 `managed_dataset`
- `@data_view` 会在宿主加载时完成校验并同步到 `module_db_views`，运行时只能通过 `ctx.db.from_("view_id")` 只读访问
- `ctx.tools` 不再暴露任何 `db.*` 工具；旧接入方式必须从模块代码和文档示例中删除

### 6.2 写入与并发语义

- 模块开发者不直接管理 SQLite 连接、锁或 `commit/rollback`。
- 每个 `ctx.db` 写入 plan 都由宿主包成短事务；成功自动提交，异常自动回滚。
- 宿主写入层对 `data.db` 设置 busy timeout，并通过写协调器按数据库文件和 `module/resource` 写入键排队，遇到 SQLite 短暂忙碌时由宿主重试。
- `ctx.db.into(resource).replace(records)` 保留为全量快照覆盖语义，适合低频稳定数据；并发任务更新同一实体表时优先使用 `upsert/update_where/delete_where`。
- `ctx.db.into(resource).add(records)` 是 `custom_table` 的 insert-only 新增语义；当 `record_key_field` 对应 integer schema 字段声明 `auto_increment=True` 时，add 可以省略主键并返回生成 id 列表。
- `ctx.db.batch().upsert(...).audit(...).execute()` 表达一组数据库动作的原子提交；batch 内只允许数据库 plan，不允许跨浏览器、网络请求或任意长耗时业务操作持有事务。

### 6.3 查询能力分层

| 数据源 | 允许能力 | 禁止能力 |
|---|---|---|
| `managed_dataset` | `select`、`where`、`order_by`、`limit`、`offset`、`where` 后 `count(*)`、`replace/upsert/update_where/delete_where`，以及写入 `run_status` / `record_status` 状态列 | `join`、`group_by`、`sum/avg/min/max`、混合列选择和聚合、更新宿主生成型物理字段 |
| `custom_table` | `select`、`where`、`order_by`、`limit`、`offset`、已声明 `join`、`group_by`、`count/sum/avg/min/max`、`add/upsert/update_where/delete_where` | 未声明 join、跨模块表、未注册 SQL、模块自管事务 |
| `view` | 只读筛选、排序、分页 | 写入、运行时拼 SQL、访问未声明资源 |

`where` 条件统一使用数组表达式：简单条件是 `["age", "=", 18]`，多个条件默认 `AND`，显式组合用 `["or", ...]` / `["and", ...]`。`managed_dataset` 的筛选、排序和选择必须按字段来源分流：`record_index`、`record_key`、`run_status`、`record_status`、`created_at`、`updated_at` 属于 `module_datasets` 物理列；schema 声明的模块业务字段下推为 SQLite `json_extract(record_json, '$.<field>')` 查询每行 `record_json` 的顶层 JSON 字段。`ctx.db.from_("resource").where(...).count(alias="total").execute()` 只统计 `where` 后记录条数，返回 `[{"total": n}]`，不打开 `managed_dataset` 的 join、group 或其它聚合能力。不支持嵌套 JSON path、schema 外 JSON key 或 raw `record_json`。资源读取统一进入 `query_resource_records` / `execute_query_plan`，旧内部 `get_record`、`list_records`、`read_resource_records`、`query_db_view` wrapper 已删除；`ctx.db.from_` 与内部查询共用 `ModuleDataStore.describe_data_source()` 的字段描述，`managed_dataset` 返回会展开 schema 业务字段和宿主物理字段。

`@data_table.schema` 是稳定字段描述、空表描述基线和 `managed_dataset.record_json` 的持久化白名单。模块页面如果只需要临时展示 `*_label`、`*_display`、`*_masked` 等派生值，仍可在页面 `query_handler` 返回值中组装；如果需要持久化、筛选或排序，则必须先作为普通 schema 业务字段声明。

`managed_dataset` 写入同样按字段来源处理：replace/upsert/update_where 会把 schema 业务字段合并进 `record_json`，允许 `run_status` / `record_status` 作为物理状态列写入，并忽略 replace/upsert 中的 `record_key` / `record_index` / `created_at` / `updated_at` 这类生成型物理字段；update_where 会拒绝更新这些生成型物理字段。

### 6.4 数据分工

| 你要保留什么 | 正式入口 | 语义 |
|---|---|---|
| 低频稳定记录、账号表、开关清单 | `@data_table(storage_mode="managed_dataset")` + `ctx.db.from_` / `ctx.db.into(...).replace/upsert/update_where/delete_where` | 当前托管快照，物理字段和 schema 业务字段统一返回 |
| 高频计算明细、计费明细 | `@data_table(storage_mode="custom_table")` + `ctx.db.from_` / `ctx.db.into(...).add/upsert/update_where/delete_where` | schema 驱动的受控实体表，按主键新增、幂等更新或条件更新；integer 主键可声明 `auto_increment=True` 后由 add 生成 |
| 基于实体表的统计汇总、条件筛选、排序分页 | `@data_table(storage_mode="custom_table")` + 装饰器索引/查询声明 + fluent aggregate | 查询构造器下推到受控实体表 |
| 同一次业务动作里的多表写入和审计 | `ctx.db.batch().upsert(...).audit(...).execute()` | 宿主短事务内原子提交或回滚 |
| 基于实体表的只读 read model | `@data_view` + `ctx.db.from_("view_id")` | 宿主创建真实 SQLite view，运行时按数据源只读查询 |
| 只追加的历史记录、状态迁移、操作痕迹 | `ctx.db.audit("dataset").append(...)` / `.query(...)` | 独立审计表 append-only，不污染快照资源 |

补充约束：

- `@data_table` 的默认 `storage_mode` 是 `custom_table`，用于保持 0.4.x 装饰器路径的当前行为。
- 需要旧快照语义时必须显式写 `@data_table(storage_mode="managed_dataset")`。
- `@data_view` 只允许引用 `custom_table`；`managed_dataset` 不进入 SQL 模板、视图、join、group 或除 `count(*)` 外的 aggregate 路径。

### 6.5 明确删除的旧边界

不再存在以下正式契约：

- `module_data_table_views`
- `ui.declare_data_table`
- `ui.get_data_table`
- `core:data_table`
- `module.yaml.data`
- 由宿主替模块管理数据表页面语义

## 7. 短期状态契约

模块侧短期状态使用 `ctx.state`，只在当前一次任务 / workflow 执行期间有效。宿主内部可以继续使用 `state.db.kv_store` 管理自己的状态和锁，但这不是模块开发者接口。

推荐 key 结构：

- `<module_name>:<domain>:<name>`

## 8. 明确禁止的模式

- 在模块运行时代码中写配置
- 直接连接 `config.db`、`data.db`、`state.db`
- 在模块代码里执行未注册 SQL
- 在模块代码里调用旧 `ctx.tools.call("db.*")`
- 把 `workflow`、`devel_mode`、`creation_params` 写进 `ctx.config`
- 把大批量业务数据写进 `ctx.state`
- 绕过 `@data_table` / manifest lock 私自读写模块数据
- 绕过 `@env_candidates` 私自恢复 `selector_name/env_selector/resource_pool` 环境选择路径
- 在模块目录里再维护一份正式 `*.yml` 配置事实源
- 把页面 schema 当成模块配置保存
- 重新引入独立数据表页面契约
- 绕过宿主 YAML 验证层直接把编辑器文本写入 `config.db.module_config_entries`

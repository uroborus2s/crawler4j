# 模块配置、运行态与数据契约

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 模块开发者  
**关联 ID：** `API-005`, `API-006`, `API-008`, `API-009`, `API-010`
**最后更新：** 2026-04-24

## 1. 设计目标

本契约用于统一模块开发者在运行时面对的六类核心对象：

1. 配置
2. 运行态元数据
3. 单次运行内共享内存
4. 页面 schema
5. 模块数据资源 / 数据库视图 / 命名查询
6. 短期状态

目标不是再引入多套抽象，而是把当前已经落地的事实源固定下来，避免模块作者继续在 `module.yaml`、模块目录、自定义 YAML、`ctx.runtime`、`ctx.state`、旧 `ctx.tools.call("db.*")` 和 UI schema 之间混用。

## 2. 统一分层

| 类别 | 事实源 | 模块读取方式 | 模块写入方式 | 说明 |
|---|---|---|---|---|
| 静态清单 | `module.yaml` | 宿主扫描和装配 | 禁止 | 放模块名、版本、工作流、页面导航，以及一次性初始化模板 `config_defaults` 和 `data` 数据契约 |
| 持久配置 | `config.db.module_config_entries` | `ctx.get_config()` / `ctx.config` | 禁止 | 宿主统一维护；模块运行时只读 |
| 运行态元数据 | `ctx.runtime` | `ctx.runtime[...]` | 禁止 | 由 ATM / Debug / Core 注入 |
| 单次运行内共享内存 | `ctx.state` | `ctx.state[...]` | 允许 | 只在当前一次任务 / 工作流执行期间有效 |
| 页面 schema | `declare_ui()` 本轮声明缓存（宿主桥接内存） | `ctx.tools.call("ui.get_page")` | `ctx.tools.call("ui.declare_page")` | 宿主管理页面 schema；模块只声明页面，不再声明独立数据表页；正式 Hosted UI 刷新链路不再依赖 `data.db.module_pages` |
| 模块数据资源 | `module.yaml.data.resources[]` + `data.db.module_data_resources` + `data.db.module_datasets` / 模块自定义物理表 | `ctx.db.from_("resource_id")` | `ctx.db.into("resource_id").replace(records)` | `managed_dataset` 适合低频稳定数据，`custom_table` 适合高频计算或明细表 |
| 模块审计事件 | `data.db.module_audit_events` | `ctx.db.audit("dataset").query(...)` | `ctx.db.audit("dataset").append(...)` | append-only 历史事件，不进入 `module_datasets` |
| 数据库视图 | `module.yaml.data.views[]` + `data.db.module_db_views` | `ctx.db.from_("view_id")` | 禁止 | 只读 read model；不承载复杂联表或聚合 |
| 命名查询 | `module.yaml.data.queries[]` | `ctx.db.named("query_id").bind(...).execute()` | 禁止 | 受控 SQL 查询，只能执行已注册 `query_id` |
| 短期状态 | `ctx.state` | `ctx.state[...]` | `ctx.state[...] = ...` | 仅当前一次任务 / workflow 内有效，不落正式业务库 |

`ctx.captured_data` 不再作为正式契约存在。临时小状态统一放 `ctx.state`，任务输出统一放 `TaskResult.data`，需要跨运行持久化的数据统一走 `ctx.db`。

## 3. 配置契约

- `module.yaml` 是唯一模块清单，可额外声明只读默认模板 `config_defaults` 与 `data` 数据契约，但不是可变配置存储。
- 模块可变配置统一持久化到 `config.db.module_config_entries`。
- 模块运行时代码只能通过 `ctx.get_config()` 或 `ctx.config` 读取配置。
- 模块不得自行读取宿主配置数据库。
- 除 `module.yaml.config_defaults` 外，不再承认模块目录里的第二套配置事实源，例如 `module.settings.yml`、`strategy.yaml`、`config_schema.json`。

## 4. 运行态元数据契约

`ctx.runtime` 是宿主拥有的只读运行态字典。当前固定字段如下：

| 键 | 含义 |
|---|---|
| `workflow` | 本次执行命中的工作流名 |
| `execution_params` | 运行模板上的默认输入 |
| `job_params` | 当前作业的一次性覆盖输入 |
| `params` | `execution_params + job_params` 合并后的有效输入 |
| `devel_mode` | 当前是否为 DevLink 开发态 |
| `creation_params` | 本次环境创建参数；已有环境导入时也通过这里透传来源元数据 |
| `env_action` | 本次终态环境动作结果 |

约束：

- 模块不得覆盖或重写这些键。
- `workflow`、`devel_mode`、`creation_params` 不能再混进 `ctx.config`。
- 本次执行的临时变量也不要写入 `ctx.runtime`，应放到局部变量或 `ctx.state`。

### 4.1 已有环境导入场景

当宿主通过 `环境管理 -> 从已有环境导入` 启动模块 workflow 时，`ctx.runtime["creation_params"]` 还会补充以下键：

| 键 | 含义 |
|---|---|
| `provider` | 外部环境来源，例如 `virtual_browser` |
| `provider_env_id` | 来源系统中的环境 ID |
| `provider_env_name` | 来源系统中的环境名称 |
| `provider_group` | 来源系统中的环境分组 |
| `provider_proxy` | 来源系统返回的代理摘要或原始代理对象 |
| `import_mode` | 固定为 `existing_env` |

该场景还有两条补充约束：

- 宿主仍必须保证 `ctx.env_id` 与 `ctx.page` 可用，模块不需要自己重新绑定浏览器上下文。
- `module.yaml.workflows[].host_scenarios` 可选声明 `existing_env_import` 作为适配提示；宿主未命中该声明时只显示风险提示，不作为执行门禁。

## 5. 页面 schema 契约

### 5.1 页面声明

页面 schema 只能通过 `ui.declare_page` 声明；正式 Hosted UI 链路会在每次 refresh 前重新执行 `declare_ui()`，并把声明结果缓存到当前 bridge 内存中供 `ui.get_page` / renderer 消费，不再把 `data.db.module_pages` 作为正式渲染事实源。

正式契约：

- `module.yaml.ui_extension.pages[]` 只声明导航元信息
- `declare_ui()` 只调用 `ui.declare_page`
- `ui.get_page` 只读取页面 schema
- 正式页面链路固定为 `ui.declare_page -> Page.children[] 内联 DataTable -> query_handler`
- 不再存在 `ui.declare_data_table` / `ui.get_data_table`

### 5.2 页面数据

页面数据只允许通过两类同步函数提供：

- `load_handler(context, page_id, params=None)`
- `query_handler(context, table_id, query, params=None)`

模块可以在这些函数中调用：

- `ctx.db.from_(...)`
- `ctx.db.named(...)`
- `ctx.db.into(...).replace(...)`
- `ctx.db.audit(...).append(...)` / `.query(...)`
- 其它宿主能力

但宿主只负责接收结构化返回值并渲染，不解释业务语义。

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

## 6. 模块数据、数据库视图与命名查询契约

### 6.1 快照数据位置

- `module.yaml.data.resources[]` 是表资源的唯一声明入口
- `managed_dataset` 模式下，`ctx.db.from_(...)` / `ctx.db.into(...).replace(...)` 读写的快照记录持久化到 `data.db.module_datasets`
- `custom_table` 模式下，宿主会在模块加载/安装时创建受控物理表 `module_name_resource_id`
- 审计事件不建模为 `resources[]`，只通过 `ctx.db.audit("dataset")` 写入和查询 `data.db.module_audit_events`
- 未注册的 `resource_id` 会直接报错；宿主不再按资源名隐式补建 `managed_dataset`
- `module.yaml.data.views[]` 会同步到 `data.db.module_db_views`
- `module.yaml.data.queries[]` 会在宿主加载时完成校验，运行时只能通过 `ctx.db.named("query_id").bind(...).execute()` 调用
- `ctx.tools` 不再暴露任何 `db.*` 工具；旧接入方式必须从模块代码和文档示例中删除

### 6.2 查询能力分层

| 数据源 | 允许能力 | 禁止能力 |
|---|---|---|
| `managed_dataset` | `select`、`where_*`、`order_by`、`limit`、`offset` | `join`、`group_by`、`aggregate` |
| `custom_table` | `select`、`where_*`、`order_by`、`limit`、`offset`、已声明 `join`、`group_by`、`count/sum/avg/min/max` | 未声明 join、跨模块表、未注册 SQL |
| `view` | 只读筛选、排序、分页 | 复杂联表、复杂聚合、写入 |
| `named query` | 已注册参数绑定和执行 | 运行时拼 SQL、访问未声明资源 |

### 6.3 数据分工

| 你要保留什么 | 正式入口 | 语义 |
|---|---|---|
| 低频稳定记录、账号表、开关清单 | `module.yaml.data.resources[]`(`managed_dataset`) + `ctx.db.from_` / `ctx.db.into(...).replace` | 当前快照，可整包覆盖 |
| 高频计算明细、计费明细 | `module.yaml.data.resources[]`(`custom_table`) + `ctx.db.from_` / `ctx.db.into(...).replace` | schema 驱动的受控实体表 |
| 基于实体表的统计汇总、条件筛选、排序分页 | `module.yaml.data.resources[]`(`custom_table`) + manifest `joins` + fluent aggregate | 查询构造器下推到受控实体表 |
| 固定复杂 SQL | `module.yaml.data.queries[]` + `ctx.db.named(...).bind(...).execute()` | 只允许执行已注册命名查询 |
| 只追加的历史记录、状态迁移、操作痕迹 | `ctx.db.audit("dataset").append(...)` / `.query(...)` | 独立审计表 append-only，不污染快照资源 |

### 6.4 明确删除的旧边界

不再存在以下正式契约：

- `module_data_table_views`
- `ui.declare_data_table`
- `ui.get_data_table`
- `core:data_table`
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
- 绕过 `module.yaml.data.resources[]` 私自读写模块数据
- 在模块目录里再维护一份正式 `*.yml` 配置事实源
- 把页面 schema 当成模块配置保存
- 重新引入独立数据表页面契约

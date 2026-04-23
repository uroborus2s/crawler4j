# 模块配置、运行态与数据契约

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 模块开发者  
**关联 ID：** `API-005`, `API-006`, `API-008`, `API-009`  
**最后更新：** 2026-04-23

## 1. 设计目标

本契约用于统一模块开发者在运行时面对的六类核心对象：

1. 配置
2. 运行态元数据
3. 单次运行内共享内存
4. 页面 schema
5. 快照数据 / 数据库视图
6. 审计事件与短期状态

目标不是再引入一层抽象，而是把当前已经落地的事实源固定下来，避免模块作者继续在 `module.yaml`、模块目录、自定义 YAML、`ctx.runtime`、`ctx.state`、`db.*`、UI schema 之间混用。

## 2. 统一分层

| 类别 | 事实源 | 模块读取方式 | 模块写入方式 | 说明 |
|---|---|---|---|---|
| 静态清单 | `module.yaml` | 宿主扫描和装配 | 禁止 | 放模块名、版本、工作流、页面导航，以及一次性初始化模板 `config_defaults` |
| 持久配置 | `config.db.module_config_entries` | `ctx.get_config()` / `ctx.config` | 禁止 | 宿主统一维护；模块运行时只读 |
| 运行态元数据 | `ctx.runtime` | `ctx.runtime[...]` | 禁止 | 由 ATM / Debug / Core 注入 |
| 单次运行内共享内存 | `ctx.state` | `ctx.state[...]` | 允许 | 只在当前一次任务 / 工作流执行期间有效 |
| 页面 schema | `declare_ui()` 本轮声明缓存（宿主桥接内存） | `ctx.tools.call("ui.get_page")` | `ctx.tools.call("ui.declare_page")` | 宿主管理页面 schema；模块只声明页面，不再声明独立数据表页；正式 Hosted UI 刷新链路不再依赖 `data.db.module_pages` |
| 快照数据 | `data.db.module_data_resources` + `data.db.module_datasets` / 模块自定义物理表 | `ctx.tools.call("db.list_records")` | `ctx.tools.call("db.declare_data_resource")` / `ctx.tools.call("db.replace_records")` | `managed_dataset` 适合低频稳定数据，`custom_table` 适合高频计算或明细表 |
| 数据库视图 | `data.db.module_db_views` | `ctx.tools.call("db.query_view")` | `ctx.tools.call("db.declare_db_view")` | 基于当前模块 `custom_table` 的受控 `SELECT` 统计视图 |
| 审计事件历史 | `data.db.module_audit_events` | `ctx.tools.call("db.query_events")` | `ctx.tools.call("db.append_event")` | append-only 业务历史、操作轨迹、时间线查询 |
| 短期状态与锁 | `state.db.kv_store` | `ctx.tools.call("db.get_state")` 等 | `ctx.tools.call("db.set_state")` 等 | 游标、进度、会话、小体量状态、幂等锁 |

## 3. 配置契约

- `module.yaml` 是唯一模块清单，可额外声明只读默认模板 `config_defaults`，但不是可变配置存储。
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
| `creation_params` | 本次环境创建参数 |
| `env_action` | 本次终态环境动作结果 |

约束：

- 模块不得覆盖或重写这些键。
- `workflow`、`devel_mode`、`creation_params` 不能再混进 `ctx.config`。
- 本次执行的临时变量也不要写入 `ctx.runtime`，应放到局部变量或 `ctx.state`。

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

- `db.list_records`
- `db.query_view`
- `db.query_events`
- 其它宿主能力

但宿主只负责接收结构化返回值并渲染，不解释业务语义。

### 5.3 `DataTable` 组件

`DataTable` 只是页面 schema 的子组件。

数据源只支持：

- `binding`
- `rows`
- `query_handler`

正式宿主页里的可交互表格统一走内联 `DataTable(data_source.type="query_handler")`。

- `query_handler` 是正式查询链路，负责把过滤、排序、分页路由到 `db.query_view` / `db.list_records` 等能力
- `binding` / `rows` 只用于页面内静态或局部数据，不构成另一条宿主页注册链路
- 表格交互由宿主统一处理，但数据查询和写回策略由模块自行决定

## 6. 快照数据、数据库视图与审计事件契约

### 6.1 快照数据位置

- `db.declare_data_resource` 会把模块数据资源登记到 `data.db.module_data_resources`
- `managed_dataset` 模式下，`db.list_records` / `db.replace_records` 读写的快照记录持久化到 `data.db.module_datasets`
- `custom_table` 模式下，宿主会创建受控物理表 `module_name_resource_id`
- `db.declare_db_view` 会把数据库视图登记到 `data.db.module_db_views`
- `db view` 的正式 V1 契约只支持 `view_kind="sql_view"`，`cleanup_policy` 只支持 `drop_view` / `keep`
- `db.append_event` / `db.query_events` 读写的审计事件持久化到 `data.db.module_audit_events`

### 6.2 数据分工

| 你要保留什么 | 正式入口 | 语义 |
|---|---|---|
| 低频稳定记录、账号表、开关清单 | `db.declare_data_resource(storage_mode="managed_dataset")` + `db.list_records` / `db.replace_records` | 当前快照，可整包覆盖 |
| 高频计算明细、运行审计、计费明细 | `db.declare_data_resource(storage_mode="custom_table")` + `db.list_records` / `db.replace_records` | schema 驱动的受控实体表 |
| 基于实体表的统计汇总、条件筛选、排序分页 | `db.declare_db_view` + `db.query_view` | 只读统计查询 |
| 只追加的历史记录、状态迁移、操作痕迹 | `db.append_event` / `db.query_events` | append-only 历史，不回写快照 |

### 6.3 明确删除的旧边界

不再存在以下正式契约：

- `module_data_table_views`
- `ui.declare_data_table`
- `ui.get_data_table`
- `core:data_table`
- 由宿主替模块管理数据表页面语义

## 7. 短期状态与锁契约

`state.db.kv_store` 当前只承载轻量状态和锁，不再用于正式业务数据表。

正式入口：

- `db.get_state`
- `db.set_state`
- `db.exists_state`
- `db.acquire_lock`
- `db.release_lock`
- `db.is_locked`

推荐 key 结构：

- `<module_name>:<domain>:<name>`

## 8. 明确禁止的模式

- 在模块运行时代码中写配置
- 直接连接 `config.db`、`data.db`、`state.db`
- 把 `workflow`、`devel_mode`、`creation_params` 写进 `ctx.config`
- 把大批量业务数据写进 `ctx.state` 或 `db.set_state`
- 把审计事件历史混进快照数据
- 在模块目录里再维护一份正式 `*.yml` 配置事实源
- 把页面 schema 当成模块配置保存
- 重新引入独立数据表页面契约

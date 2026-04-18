# 核心概念

开始写代码前，先把两件事看清楚:

1. 模块在 `crawler4j` 里到底是什么
2. 哪些事情已经被宿主抽象好了，模块开发者不应该再做一遍

## 一句话理解模块

模块是运行在 `crawler4j` 宿主中的轻量业务应用。

这句话有两个重点:

1. 模块不是独立平台
2. 模块不是拿来继续抽象框架的

## 第一次开发时，你真正会改的只有这几处

如果你现在是第一次上手，不要先记内部名词，先记你会碰到哪些文件和入口:

| 你要做什么 | 直接改哪里 | 什么时候会用到 |
|---|---|---|
| 改模块名、工作流、升级源、默认配置 | `module.yaml` | 初始化后第一时间 |
| 写一个原子业务动作 | `tasks/*.py` | 例如登录、抓一页、提交表单 |
| 写业务流程编排 | `workflows/*.py` | 需要顺序、分支、循环时 |
| 写生命周期 hook、环境选择器、只读数据表声明 | `module_runtime.py` | 需要宿主 hook 或托管数据表时 |
| 做宿主内验证 | 宿主 `📦 模块管理` + `📋 任务监控` | CLI 自检通过后 |

只要还在这 5 个落点里，你大概率没有走偏。

## 宿主已经抽象好的层

| 层 | 正式入口 | 你能在这里放什么 | 明确不要放什么 |
|---|---|---|---|
| 静态清单 | `module.yaml` | 工作流声明、升级源、UI 入口、默认配置模板 | 运行时状态、持久数据、SDK 兼容范围 |
| 模块入口 | 根 `__init__.py` | `ModuleAssembler` 薄壳、必要导出 | 业务逻辑、配置解析、页面操作 |
| 模块级胶水 | `module_runtime.py` | hook、环境选择器、`declare_ui`、很薄的适配代码 | 多步业务流程、领域转换、大量数据处理 |
| 原子业务动作 | `tasks/*.py` | 登录、抓一页、提交表单、解析一个详情页 | 完整流程编排、通用平台层 |
| 业务流程 | `workflows/*.py` | 顺序、分支、循环、停止判断、阶段切换 | 页面细节、字段解析、数据库封装 |
| 持久配置 | `ctx.get_config()` / `ctx.config` | 读取模块和 workflow 配置 | 写运行时状态、拼 job 参数 |
| 运行态 | `ctx.runtime` | 读取 workflow、params、`devel_mode` 等 | 持久配置、长期状态 |
| 单次执行状态 | `ctx.state` | 少量阶段状态、轻量控制参数 | 大对象总线、持久业务数据 |
| 快照数据 | `db.list_records` / `db.replace_records` | 当前结构化 records、当前结果集 | append-only 历史、宿主内部数据库细节 |
| 审计事件历史 | `db.append_event` / `db.query_events` | 只追加的业务历史、操作轨迹、事件时间线 | 当前快照、`core:data_table` CRUD |
| 轻状态与锁 | `db.get_state` / `db.set_state` / `db.acquire_lock` | 游标、短 TTL 状态、互斥锁 | 正式配置、可编辑业务列表 |
| UI | 代码页面或 `core:data_table` | 业务页面或受控数据表 | 第二套 CRUD 框架 |

## 模块执行链路

标准模块的执行路径是:

1. Core 读取 `module.yaml`，加载模块根 `__init__.py`
2. 根入口里的 `ModuleAssembler` 自动发现 `tasks/`、`workflows/`、`module_runtime.py`
3. ATM 构造 `TaskContext`
4. 宿主调用 `prepare_env -> init_env -> before_run`
5. `ModuleAssembler` 根据 `ctx.runtime["workflow"]` 或默认工作流执行 workflow / task
6. workflow 通过 `ctx.run_subtask(...)` 调 task
7. task 通过 `ctx.page`、`ctx.http`、`ctx.tools.call(...)` 执行业务逻辑
8. 模块返回 `TaskResult`，必要时附带 `TaskSignal`
9. 宿主执行环境动作，再进入 `on_success/on_failure/on_timeout/on_cleanup`

第一次读这段时，只要理解成下面 4 句就够了:

- `ModuleAssembler` = 根 `__init__.py` 里的托管装配器，不是你写业务逻辑的地方
- ATM = 宿主 `📋 任务监控` 页对应的运行入口
- `prepare_env / init_env / before_run / on_*` = 你可选写在 `module_runtime.py` 里的生命周期 hook
- `TaskSignal` = task 或 workflow 返回给宿主的控制信号，例如等待确认或取消

## 硬约束

### 必须做

- 必须先用 CLI 生成模块骨架、task、workflow、UI 入口
- 必须把业务动作放进 `TaskScript`，把业务流程放进 `TaskFlow`
- 必须通过 `ctx.get_config()` / `ctx.config` 读取持久配置
- 必须通过 `ctx.runtime` 读取 workflow、params、`devel_mode`、`creation_params` 等运行态信息
- 必须通过 `ctx.tools.call("db.*")`、`ctx.tools.call("ui.*")` 等统一入口访问宿主能力
- 必须把生命周期逻辑写在 `module_runtime.py`
- 必须用 `crawler4j check structure`、`crawler4j check release`、`crawler4j check full` 做对应层级的自检

### 明确禁止

- 禁止再造 `config_schema.json`、`strategy.yaml`、`module.settings.yml` 这类第二套配置事实源
- 禁止在 `module.yaml` 中声明 `sdk_version_range`
- 禁止直连 `config.db`、`data.db`、`state.db` 或宿主内部 ORM / Session
- 禁止把 `workflow`、`params`、`devel_mode`、`creation_params` 写进 `ctx.config`
- 禁止把大批量业务数据塞进 `ctx.state`
- 禁止为了“复用”而搭 `service / repository / manager / base class` 多层体系
- 禁止修改根 `__init__.py` 薄壳来实现业务逻辑

## 不要过度抽象

推荐的抽象层次最多三层就够了:

1. `workflow`
2. `task`
3. `utils` 里的纯函数

下面这些通常会把模块写重:

- `BaseTask -> BusinessTask -> XxxTaskImpl`
- `OrderService -> OrderRepository -> OrderStore`
- 再包一层 `ContextAdapter`、`DbAdapter`、`ToolsClient`
- 把单个模块做成“可插拔框架”

## 运行态边界

| 目标 | 应该用什么 | 不应该用什么 |
|---|---|---|
| 读配置 | `ctx.get_config()` | 直接读 `module.yaml` 或数据库 |
| 读执行参数 | `ctx.runtime["params"]` | 自己拼接配置和 job 输入 |
| 暂存单次执行状态 | `ctx.state` | `db.set_state` 或全局变量 |
| 保存当前快照 | `db.list_records` / `db.replace_records` | `ctx.state` |
| 记录历史事件 | `db.append_event` / `db.query_events` | `db.replace_records` / `core:data_table` |
| 保存轻状态和锁 | `db.get_state` / `db.set_state` / `db.acquire_lock` | `ctx.config` |

## 术语表

| 术语 | 含义 |
|---|---|
| module | 一个可被宿主加载、调试、安装、升级的业务包 |
| task | 最小原子业务动作 |
| workflow | 多个 task 的编排流程 |
| hook | 宿主在生命周期节点调用的模块函数，通常写在 `module_runtime.py` |
| `ModuleAssembler` | 根 `__init__.py` 里的托管装配器，负责发现 task/workflow 和转发执行 |
| ATM | 宿主 `📋 任务监控` 页面，对模块开发者来说就是“创建作业并执行”的入口 |
| `TaskSignal` | task/workflow 返回给宿主的控制信号，例如等待确认、取消、保留环境 |
| `config_defaults` | 首次初始化和“恢复默认”使用的静态模板 |
| `devel_mode` | DevLink 开发态标志，位于 `ctx.runtime` |
| `core:data_table:<view_id>` | 宿主管理的数据表详情页入口 |

## 最常见的认知错误

- 把模块当成要长期演化成平台的项目
- 把 `module_runtime.py` 写成新的业务层
- 把 `ctx.state` 当成参数总线
- 拿 `core:data_table` 或快照 dataset 直接充当审计日志表
- 为了“规范”把模块拆成一堆空层

下一步建议看 [模块结构](module-structure.md)。

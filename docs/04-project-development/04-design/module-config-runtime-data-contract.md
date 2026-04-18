# 模块配置、运行态与数据契约

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | 开发 | QA | 模块开发者  
**上游输入：** `module-boundaries.md` | `api-design.md` | 当前 `TaskContext` / MMS / ATM / Debug 实现  
**下游输出：** `docs/03-developer-guide/core-concepts.md` | `docs/03-developer-guide/build-modules.md` | `docs/03-developer-guide/reference-core-capabilities.md` | `.factory/memory/api.summary.md`  
**关联 ID：** `API-005`, `REQ-002`, `REQ-003`, `REQ-006`, `CR-003`  
**最后更新：** 2026-04-18

## 1. 设计目标

本契约用于统一模块开发者在运行时面对的五类核心对象：

1. 配置
2. 运行态元数据
3. 单次运行内共享内存
4. 快照数据
5. 审计事件与短期状态

目标不是再引入一层抽象，而是把当前已经落地的事实源固定下来，避免模块作者继续在 `module.yaml`、模块目录、自定义 YAML、`ctx.runtime`、`ctx.state`、`db.*` 之间混用。

## 2. 统一分层

| 类别 | 事实源 | 模块读取方式 | 模块写入方式 | 说明 |
|---|---|---|---|---|
| 静态清单 | `module.yaml` | 宿主扫描和装配 | 禁止 | 放模块名、版本、工作流、UI 扩展，以及一次性初始化模板 `config_defaults` |
| 持久配置 | `config.db.module_config_entries` | `ctx.get_config()` / `ctx.config` | 禁止 | 宿主统一维护；模块运行时只读 |
| 运行态元数据 | `ctx.runtime` | `ctx.runtime[...]` | 禁止 | 由 ATM / Debug / Core 注入 |
| 单次运行内共享内存 | `ctx.state` | `ctx.state[...]` | 允许 | 只在当前一次任务 / 工作流执行期间有效 |
| 快照数据 | `data.db.module_datasets` / `data.db.module_data_table_views` | `ctx.tools.call("db.list_records")` / `ctx.tools.call("ui.get_data_table")` | `ctx.tools.call("db.replace_records")` / `ctx.tools.call("ui.declare_data_table")` | 当前记录列表、当前结果集、可编辑数据表 |
| 审计事件历史 | `data.db.module_audit_events` | `ctx.tools.call("db.query_events")` | `ctx.tools.call("db.append_event")` | append-only 业务历史、操作轨迹、时间线查询 |
| 短期状态与锁 | `state.db.kv_store` | `ctx.tools.call("db.get_state")` 等 | `ctx.tools.call("db.set_state")` 等 | 游标、进度、会话、小体量状态、幂等锁 |

## 3. 配置契约

### 3.1 配置事实源

- `module.yaml` 是唯一模块清单，可额外声明只读默认模板 `config_defaults`，但不是可变配置存储。
- 模块可变配置统一持久化到 `config.db.module_config_entries`。
- 模块详情页的 `配置` 标签以 YAML 作为编辑格式，但数据库才是正式事实源。
- `config_defaults` 只参与首次初始化和手动“恢复默认”，不会成为运行时直接读取的配置来源。

### 3.2 模块开发者约束

- 运行时代码只能通过 `ctx.get_config()` 或 `ctx.config` 读取配置。
- 运行时代码不得写配置。
- 模块不得自行读取宿主配置数据库。
- 除 `module.yaml.config_defaults` 外，不再承认模块目录里的第二套配置事实源，例如 `module.settings.yml`、`strategy.yaml`、`config_schema.json`。

### 3.3 推荐 YAML 结构

```yaml
auth:
  base_url: https://example.com
  username: demo

browser:
  headless: true
  timeout_seconds: 30
```

规则：

- 根节点必须是 mapping。
- key 统一使用 `snake_case`。
- 按业务域分组，不要铺平成一堆魔法 key。
- workflow 覆盖只写差异项，不复制整份模块级配置。

### 3.4 `config_defaults` 契约

`module.yaml` 允许声明：

```yaml
config_defaults:
  module:
    auth:
      base_url: https://example.com
  workflows:
    default:
      headless: false
```

约束：

- `config_defaults.module` 必须是 mapping
- `config_defaults.workflows.<workflow_name>` 必须是 mapping
- `workflow_name` 必须先在 `module.yaml.workflows` 中声明
- 首次加载模块时，如数据库中尚无该模块的配置记录，宿主会把这份模板初始化到 `config.db.module_config_entries`
- 初始化完成后会写入宿主侧标记，后续升级、刷新和重扫不再自动覆盖数据库里的当前配置

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

## 5. 单次运行内共享内存契约

`ctx.state` 是当前一次任务 / 工作流执行内可读写的共享内存，不会替代长期配置，也不承担业务数据集职责。

推荐命名空间如下：

```python
ctx.state.setdefault("module", {})
ctx.state.setdefault("workflow", {})
ctx.state.setdefault("tasks", {})
```

推荐约束：

- `ctx.state["module"]`：模块级临时缓存，例如本次登录态、当前游标快照。
- `ctx.state["workflow"]`：工作流编排临时结果，例如阶段计数、分页进度。
- `ctx.state["tasks"]`：任务级共享对象，例如子任务回传的小体量中间结果。

不要把下面这些内容塞进 `ctx.state`：

- 大批量业务 records
- 长期配置
- 需要跨多次任务长期保留的持久状态

## 6. 快照数据、审计事件与数据表契约

### 6.1 快照数据位置

- `ui.declare_data_table` 声明的 schema 持久化到 `data.db.module_data_table_views`
- `db.list_records` / `db.replace_records` 读写的 records 持久化到 `data.db.module_datasets`

### 6.2 审计事件通道的目标边界

- 审计事件历史与快照数据应该分离。
- 当前正式持久化表为 `data.db.module_audit_events`，正式工具名为 `db.append_event` / `db.query_events`。
- 无论这组工具是否已经暴露，审计事件都不应回写 `module_datasets`，也不直接进入 `core:data_table` 的 schema / records 链路。

### 6.3 模块源码与运行时数据边界

当前 CLI V1 不再为“源码层数据模型”单独建立 `data/` 命令或固定目录。

换句话说：

- 业务辅助代码按实际职责放在 `tasks/`、`workflows/`、`ui/` 或模块自定义源码文件里
- `data.db` 才是运行时业务数据，但其中也已按“快照数据 / 审计事件”分成两条能力面

### 6.4 两条持久数据通道怎么分工

| 你要保留什么 | 正式入口 | 语义 |
|---|---|---|
| 当前最新名单、当前状态、当前结果集 | `db.list_records` / `db.replace_records` | 可被下一次写入整体替换的快照 |
| 只追加的历史记录、状态迁移、操作痕迹 | `db.append_event` / `db.query_events` | append-only 历史，不回写当前快照 |
| 宿主内可编辑数据表 | `ui.declare_data_table` + `core:data_table` | 只服务快照 dataset |

### 6.5 数据表开发约束

- 数据表 schema 只能通过 `ui.declare_data_table` 声明。
- 数据表 records 只能通过 `db.list_records` / `db.replace_records` 读写。
- `view_id` 与 `dataset` 必须保持一致，由宿主统一管理。
- `core:data_table` 只服务快照 dataset，不承担 append-only 审计历史。
- schema 不是配置，不要塞进 `ctx.config`。
- `lock_key` / `lock_scope` 只用于 Core 临时锁，不用于表达模块业务占用态。
- 若模块已自行维护 `occupied` / `occupied_label` 等业务占用字段，不得再同时声明 `lock_key`；宿主会把它视为冲突 schema 并拒绝加载。

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
- 例如 `ctrip:orders:cursor`

推荐用法：

- 轻量游标、进度、短期 session 信息 -> `db.set_state`
- 并发互斥、幂等写保护 -> `db.acquire_lock`

## 8. 典型代码模型

```python
from crawler4j_sdk import TaskContext


async def execute(ctx: TaskContext):
    auth = ctx.get_config("auth", {})
    workflow = ctx.runtime.get("workflow")
    params = ctx.runtime.get("params", {})

    ctx.state.setdefault("workflow", {})
    ctx.state["workflow"]["page"] = 1

    if ctx.tools and ctx.tools.has_tool("ui.declare_data_table"):
        ctx.tools.call(
            "ui.declare_data_table",
            view_id="accounts",
            schema={
                "title": "账号管理",
                "dataset": "accounts",
                "columns": ["id", "phone_number", "status"],
            },
        )

    if ctx.tools and ctx.tools.has_tool("db.list_records"):
        rows = ctx.tools.call("db.list_records", dataset="accounts")
        ctx.tools.call("db.replace_records", dataset="accounts", records=rows)

    return {
        "workflow": workflow,
        "auth_username": auth.get("username"),
        "params": params,
    }
```

最小分流示例：

```python
snapshot_rows = [...]
ctx.tools.call("db.replace_records", dataset="accounts", records=snapshot_rows)

if ctx.tools and ctx.tools.has_tool("db.append_event"):
    audit_event_kwargs = {...}  # 事件参数键以宿主当前工具签名为准
    ctx.tools.call("db.append_event", **audit_event_kwargs)
```

## 9. 明确禁止的模式

- 在模块运行时代码中写配置
- 直接连接 `config.db`、`data.db`、`state.db`
- 把 `workflow`、`devel_mode`、`creation_params` 写进 `ctx.config`
- 把大批量业务数据写进 `ctx.state` 或 `db.set_state`
- 把审计事件历史混进 `module_datasets` 或 `core:data_table`
- 在模块目录里再维护一份正式 `*.yml` 配置事实源
- 把数据表 schema 当成模块配置保存

## 10. 当前实现说明

为了避免文档与运行代码漂移，这里额外固定两条当前事实：

1. 当前运行时代码里不存在 `state.db.kv_store -> data.db` 的模块数据表自动迁移逻辑。
2. 如果历史环境仍有旧 KV 里的 schema / records，需要通过显式迁移工具或人工导入处理；当前读链路只读取 `data.db`。
3. `core:data_table` 当前只服务快照 dataset，不承担 append-only 审计历史读写。

## 11. 变更记录

| 日期 | 变更内容 | 变更人 |
|---|---|---|
| 2026-04-17 | 初版建立模块配置、运行态、内存与数据表的统一契约 | Codex |

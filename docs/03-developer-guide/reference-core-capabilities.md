# Core 能力参考

模块运行时只有三类正式边界：

1. 从 `crawler4j-contracts` 导入共享契约
2. 通过 `ctx.tools` 调用非数据库类宿主能力
3. 通过 `ctx.db` 使用唯一的模块数据 fluent API

模块不应该直接 import Core 内部实现，也不应该依赖 `crawler4j-sdk` 参与运行时装配。

## 宿主扫描协议

Core 会扫描固定目录并读取固定导出：

| 目录 | 必需导出 | 作用 |
|---|---|---|
| `tasks/*.py` | `TASK`、`execute` | 原子任务 |
| `workflows/*.py` | `WORKFLOW`、`run` | 工作流 |
| `hooks/*.py` | `handle` | 生命周期 Hook |
| `env_selectors/*.py` | `SELECTOR`、`select` | 环境选择器 |
| `pages/*.py` / `pages/<group>/*.py` | `PAGE`、页面 handler | Hosted UI 页面 |

Core 不会调用模块根 `run()`，也不会让模块自己做运行时装配。

## 共享契约

运行时模块通常只需要这些类型：

- `TaskContext`
- `TaskResult`
- `TaskSignal`
- `EnvAction`
- `EnvCandidate`
- `TaskSpec`
- `WorkflowSpec`
- `EnvSelectorSpec`
- `PageSpec`

## `TaskContext.tools`

非数据库类宿主能力经 `ctx.tools` 暴露：

- `ctx.tools.has_tool(name)`
- `ctx.tools.list_tools()`
- `ctx.tools.call(name, **kwargs)`

常见能力面如下：

| 类别 | 工具名 | 主要用途 |
|---|---|---|
| Hosted UI | `ui.get_page` | 调试页面声明结果 |
| 环境与资源池 | `env.*` `ip_pool.pick_proxy` | 环境选择、代理、固定池维护 |
| 验证码 | `captcha.match_slider` `captcha.match_click_targets` | 图像辅助 |

`ctx.tools` 不再暴露任何 `db.*` 工具。旧写法会被 SDK `check full` 拒绝，运行时也不会注册这些工具。

资源池资格也不再由 `crawler4j-sdk` 提供运行时 helper。模块需要维护固定池资格时，直接调用宿主 `env.*` tools；如需更顺手的函数，只在模块仓内封装本地薄 helper。

## `TaskContext.db`

模块数据访问只有一个入口：`ctx.db`。

```python
rows = (
    ctx.db.from_("accounts")
    .select("account_id", "status")
    .where_eq("status", "ready")
    .order_by("account_id")
    .limit(50)
    .execute()
)

stats = (
    ctx.db.from_("billing_entries")
    .join("accounts", on={"account_id": "account_id"}, how="left")
    .group_by("account_id")
    .sum("amount", alias="total_amount")
    .execute()
)

detail = ctx.db.named("get_account_detail").bind(account_id="A001").execute()

ctx.db.into("accounts").replace(rows)

event_id = ctx.db.audit("account_events").append(
    entity_key="A001",
    event_type="status_changed",
    previous_status="ready",
    next_status="blocked",
    result="success",
    reason="risk_control",
    payload={"operator": "system"},
)

events = ctx.db.audit("account_events").query(entity_key="A001", limit=20)
```

数据源能力按类型收敛：

| 数据源 | 能力 |
|---|---|
| `managed_dataset` | 单源 `select/where/order_by/limit/offset`；禁止 `join/group_by/aggregate` |
| `custom_table` | 支持 `select/where/order_by/limit/offset`；只允许使用 `module.yaml.data.resources[].joins` 中声明过的 `join`；支持 `group_by` 与聚合 |
| `view` | 只读 read model；支持轻量筛选、排序、分页；不承载复杂聚合 |
| `named query` | 通过 `ctx.db.named(...).bind(...).execute()` 执行已注册 SQL |
| `audit` | 通过 `ctx.db.audit(...).append/query` 访问独立审计表；不进入 `module_datasets` |

## 任务与工作流

最小任务签名：

```python
async def execute(ctx: TaskContext) -> TaskResult:
    ...
```

最小工作流签名：

```python
async def run(ctx: TaskContext):
    return await ctx.run_subtask("task_name")
```

如果 `run()` 返回：

- `TaskResult`：宿主直接使用
- `dict`：宿主归一化为成功结果
- `None`：宿主会把当前 `ctx.state` 归一化为成功结果

`ctx.captured_data` 已不是正式契约。单次运行内的小状态放 `ctx.state`，任务输出放 `TaskResult.data`，需要持久化的数据走 `ctx.db`。

如果某个 workflow 明确适配“已有环境导入”场景，可以在 `module.yaml` 里可选声明：

```yaml
workflows:
  - name: reuse_logged_in_env
    display_name: 复用已登录环境
    description: 从外部浏览器已有环境导入后执行
    host_scenarios:
      - existing_env_import
```

约束如下：

- 宿主全局环境页的 `从已有环境导入` 入口会选择一个已配置的“执行一次”批次任务；该任务的运行模板决定模块与 workflow。
- 缺少 `host_scenarios: [existing_env_import]` 只会触发风险提示，不会阻断执行。
- 该场景下宿主保证 `ctx.env_id` 与 `ctx.page` 可用。
- 宿主以 `(provider, name)` 判定某个外部环境是否已导入；未同步列表也通过来源环境名称在本地不存在来判断。
- 多选导入时，每个环境会生成一个挂在同一 Job 下的 Task；实际同时打开的窗口数受该 Job 的 `concurrency_target` 限制。
- 宿主会在 `ctx.runtime["creation_params"]` 中写入 `provider`、`name`、`provider_env_id`、`provider_env_name` 以及 `import_mode="existing_env"`，模块可据此判断当前运行来自已有环境导入。

## 生命周期 Hook

当前宿主识别的 Hook 文件名固定为：

- `prepare_env`
- `init_env`
- `before_run`
- `on_success`
- `on_failure`
- `on_timeout`
- `on_cleanup`

每个文件都导出：

```python
async def handle(context: TaskContext):
    ...
```

文件名就是 Hook 名。宿主负责调度，不需要模块再注册。

## 环境选择器

环境选择器文件导出：

```python
from crawler4j_contracts import EnvCandidate, EnvSelectorSpec, TaskContext

SELECTOR = EnvSelectorSpec(name="pick_ready")

def select(context: TaskContext, candidates: list[EnvCandidate]):
    ...
```

返回值约定：

- 返回 `env_id`：宿主绑定该环境
- 返回 `None`：当前轮未选中

当作业配置了 `resource_pool` 时，`None` 会进入宿主管理的等待语义；没有 `resource_pool` 时会按失败处理。

## 页面与处理函数

页面文件导出：

```python
from crawler4j_contracts import PageSpec

PAGE = PageSpec(
    id="dashboard",
    label="Dashboard",
    icon="📄",
    schema={...},
)
```

常见 handler 签名：

```python
def load_dashboard_page(context: TaskContext, page_id: str, params: dict | None = None) -> dict:
    ...

def query_orders_table(
    context: TaskContext,
    table_id: str,
    query: dict,
    params: dict | None = None,
) -> dict:
    ...
```

正式约束：

- `PAGE.id` 必须是唯一的扁平 snake_case；`module.yaml.ui_extension.pages[]` 只决定哪些页面进入左侧菜单
- `PAGE.schema` 顶层必须是 `Page`
- `load_handler` 必须指向页面文件中真实存在的函数
- `DataTable(query_handler)` 必须指向页面文件中真实存在的函数
- `open_page.page_id` 可以跳转到任意已注册 `PAGE`，包括未配置到左侧菜单的详情页或二级页

## 数据表

`DataTable` 是页面内组件，不是独立运行时入口。当前正式数据源只有三种：

- `binding`
- `rows`
- `query_handler`

推荐用法：

- 快照列表：`ctx.db.from_("resource_id")` + `binding`
- 统计查询：内联 `DataTable(query_handler)` + `ctx.db.from_("custom_table")`
- 命名 SQL：`ctx.db.named("query_id").bind(...).execute()`
- 页面动作写入：在 `hooks/*.py` 中调用 `ctx.db.into("resource_id").replace(records)`
- 审计事件：`ctx.db.audit("dataset").append(...)` / `.query(...)`

文档示例统一只写 fluent API。旧的 `ctx.tools.call("db.*")` 接入方式不是正式协议。

## 数据能力约束

`ctx.db.into(...).replace(records)` 的语义只有一个：全量覆盖，不是 patch 或 upsert。

模块不能在运行时代码里声明表或视图。表、视图、命名查询统一来自：

- `module.yaml.data`
- `data/sql/views/*.sql`
- `data/sql/queries/*.sql`
- `data/seeds/*.json`

未在 `module.yaml.data.resources[]` 注册的 `resource_id` 会直接报错；`managed_dataset` 也不再按 `dataset` 名自动创建托管表资源。

`ctx.db.named(...)` 当前只支持：

- 宿主已注册的 `query_id`
- 受控 `SELECT` / `WITH ... SELECT`
- 通过 `{{resource:<resource_id>}}` 引用已在 `module.yaml.data.resources[]` 注册的资源
- 不允许执行未注册 SQL

## 调试建议

能力边界问题优先这样查：

1. `uv run crawler4j check full`
2. 确认导出对象和 handler 是否存在
3. 用 `ctx.tools.list_tools()` 看非数据库能力是否真的暴露
4. 数据能力统一检查 `module.yaml.data`、`schema.columns`、`joins` 和 `ctx.db` 报错
5. 再去查业务逻辑

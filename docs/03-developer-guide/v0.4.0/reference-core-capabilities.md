# Core 能力参考

> 版本绑定：本文只描述 Core 0.4.0 / `core-native-v2` 能力。Core 0.4.0 不把 0.3.x `TaskSpec` / `WorkflowSpec` 模块当作新协议兼容运行。

模块运行时只有三类正式边界：

1. 从 `crawler4j-contracts` 导入共享契约和装饰器
2. 通过 `ctx.db` 使用唯一数据库入口
3. 通过 `ctx.tools` 调用非数据库宿主能力

模块不直接 import Core 内部实现，也不依赖 `crawler4j-sdk` 参与运行。

## 装饰器扫描

Core 扫描模块 Python 文件，读取装饰器挂载的元数据。

| 能力 | 装饰器 | 运行时作用 |
|---|---|---|
| Interface | `@interface` | 能力类型 |
| Component | `@component` | 任务环境级对象 |
| Workflow | `@workflow` | workflow 根对象 |
| Page Action | `@page_action` | 页面操作函数 |
| UI Action | `@ui_action` | Hosted UI 用户操作函数 |
| Page | `@page` | Hosted UI 页面 schema、菜单状态与 load handler |
| Data Table | `@data_table` | 数据表声明 |
| Data View | `@data_view` | 只读数据库视图声明 |

扫描阶段可以缓存 descriptor，不创建业务实例。

## ObjectContainer

每次 task/env 启动时，Core 创建对象容器。

容器保存：

- descriptor
- 运行模板 object bindings
- 运行模板 object params
- 已创建 component 实例
- workflow 实例

descriptor 中的对象注入和对象参数由 SDK/Core 扫描归一：装饰器参数、类属性 `Annotated[..., object_inject/object_param]`、`__init__` 参数 `Annotated[..., object_inject/object_param]` 都会进入同一份元数据。

生命周期：

- task/env 开始时创建
- `workflow.run(ctx)` 前按 component 组合顺序再到 workflow 调用可选 `setup(ctx, workflow)`
- 同一 task/env 内复用
- 不同 task/env 互不共享
- 任务结束后按 component 依赖反向顺序再到 workflow 调用可选 `cleanup(ctx, outcome)`

## Workflow 调用

workflow 类必须提供：

```python
async def run(self, ctx):
    ...
```

返回值约定：

- `TaskResult`：宿主直接使用
- `dict`：宿主归一化为成功结果
- `None`：宿主按当前状态归一化为成功结果

workflow 不接收 parameters。

已有环境导入 workflow 必须显式声明宿主场景：

```python
@workflow(name="import_existing_env", host_scenarios=["existing_env_import"])
class ImportExistingEnvWorkflow:
    async def run(self, ctx):
        params = ctx.runtime.get("creation_params", {})
        assert params.get("import_mode") == "existing_env"
        ...
```

宿主“从已有环境导入”对话框和导入服务只允许选择这类 workflow。普通 workflow 未声明 `existing_env_import` 时不会被误选，也不会被服务端作为导入任务调度。

## Page Action 调用

page action 必须是函数：

```python
@page_action(name="open_login_page")
async def open_login_page(ctx, url: str):
    await ctx.tools.call("browser.goto", url=url)
    ...
```

workflow 或 component 内调用：

```python
await ctx.run_page_action("open_login_page", url="https://example.com")
```

`ctx.run_subtask(...)` 已从 0.4.0 Contracts 公共面移除。v2 编排对象应调用明确的 page action 或组件方法，不依赖旧子任务兼容名。

`TaskContext` 不提供 `screenshot()`。截图属于浏览器宿主副作用能力，应由 Core 暴露的工具能力或测试宿主直接提供，而不是放进 contracts。

## `TaskContext.db`

模块数据访问只有一个入口：`ctx.db`。

```python
rows = (
    ctx.db.from_("accounts")
    .select(["account_id", "status"])
    .where(["status", "=", "ready"])
    .order_by("account_id")
    .limit(50)
    .execute()
)

overview = ctx.db.from_("account_overview").where(["status", "=", "ready"]).execute()
total = ctx.db.from_("accounts").where(["status", "=", "ready"]).count(alias="total").execute()[0]["total"]
contract = ctx.db.describe("accounts")

ctx.db.into("accounts").replace(rows)
ctx.db.into("account_events").add([{"account_id": "A001", "event_type": "login"}])
ctx.db.into("accounts").upsert([{"account_id": "A001", "status": "ready"}])
ctx.db.into("accounts").update_where({"status": "used"}, where=["account_id", "=", "A001"])
ctx.db.into("accounts").delete_where(where=["status", "=", "expired"])
ctx.db.into("accounts").update_where({"status": "used"}, where=lambda q: q.where("account_id", "=", "A001"))
ctx.db.into("accounts").delete_where(where=lambda q: q.where(["status", "=", "expired"]))
ctx.db.into("accounts").delete_where(where="A001")

event_id = ctx.db.audit("account_events").append(
    entity_key="A001",
    event_type="status_changed",
    result="success",
    payload={"operator": "system"},
)

ctx.db.batch().upsert("accounts", [{"account_id": "A001", "status": "ready"}]).audit(
    "account_events",
    {"entity_key": "A001", "event_type": "status_changed"},
).execute()
```

`delete_where(where=<主键值>)` 是主键删除快捷写法。`custom_table` 会按数据源描述中的 `record_key_field` 匹配；`managed_dataset` 会按宿主物理字段 `record_key` 匹配。高频按主键删除时优先使用这个快捷写法；需要按非主键字段删除时，继续使用 `where=["field", "=", value]`、`where={"field": value}` 或 callable 条件。

数据表和只读视图必须先由 `@data_table` / `@data_view` 声明并进入 manifest lock。
`ctx.db.describe(source)` 读取宿主归一化后的数据源契约；`source` 是逻辑数据源名，不是 SQLite 物理表名。返回值包含 `kind`、`source_kind`、`storage_mode`、`record_key_field`、`columns`、`system_fields`、`writable_fields`、`required_fields` 和 `read_only_fields`。模块侧需要生成 repository 写入契约时，应优先使用这个宿主描述。
`custom_table` 可以在 `record_key_field` 对应的 integer schema 字段上声明 `auto_increment=True`；这种表用 `ctx.db.into(...).add(...)` 新增记录，新增时可以省略 id，返回值是生成的 id 列表。`upsert` 仍然要求提供主键。
`where` 条件统一写成数组：`["field", "=", value]`、`["field", ">", value]`、`["field", "in", [...]]`、`["field", "between", [start, end]]`、`["field", "is_null"]`。多个条件默认 `AND`；需要组合时使用 `["or", condition, condition]` 或 `["and", condition, condition]`，例如 `["and", ["or", ["status", "=", "ready"], ["status", "=", "pending"]], ["age", ">=", 18]]`。
`ctx.db.from_(...).execute()` 没有隐式分页上限；未调用 `.limit(...)` / `.offset(...)` 时，宿主不会追加 `LIMIT/OFFSET`，会读取满足条件的全部行。列表页、表格页和可增长数据源必须显式分页。
`custom_table` 查询会把业务 `columns` 和宿主 `system_fields` 一起作为可读字段；默认查询与 `select("*")` 会返回 `created_at` / `updated_at`，也可以显式 `select`、`where` 或 `order_by` 这些只读系统字段。
`managed_dataset` 的 `where/select/order_by` 会分成两类字段处理：宿主物理列包括 `record_index`、`record_key`、`run_status`、`record_status`、`created_at`、`updated_at`；schema 业务字段下推为 SQLite `json_extract(record_json, '$.<field>')` 查询。模块可以按 schema 字段过滤、排序和选择，也可以用 `where(...).count(alias="total")` 统计过滤后的记录条数；这个 count 只支持 `count(*)`，不支持 `group_by`、`join` 或其它 aggregate。模块不能查询嵌套 JSON path、schema 外 JSON key 或 raw `record_json`；正式 `ctx.db` 查询面与宿主内部 `query_resource_records()` 使用同一份数据源描述，返回时会把 schema 业务字段和物理字段展开成同一行记录。写入时只有 schema 业务字段会合并进 `record_json`；`run_status` / `record_status` 可通过 replace/upsert/update_where 更新物理状态列，其余宿主生成型物理字段仍由宿主管理。
数据表和只读视图的列契约不再提供 `filterable` / `sortable` 开关；筛选和排序由统一查询执行器按字段存在性、数据源类型和表达式校验。
模块不需要管理数据库锁、事务提交或回滚；所有写入由宿主包装成短事务并自动排队、重试、提交或回滚。并发处理保持宿主 `DbWriteCoordinator` 现有策略。

## `TaskContext.tools`

`ctx.tools` 只承载非数据库宿主能力：

- `ctx.tools.has_tool(name)`
- `ctx.tools.list_tools()`
- `ctx.tools.call(name, **kwargs)`

常见类别：

| 类别 | 示例 |
|---|---|
| 浏览器交互 | `browser.goto`、`browser.click`、`browser.hover`、`browser.type`、`browser.press`、`browser.drag`、`browser.scroll`、`browser.pause` |
| 环境与代理 | `env.get_proxy`、`env.set_proxy`、`ip_pool.pick_proxy` |
| 验证码 | `captcha.match_slider`、`captcha.match_click_targets` |

`ctx.tools` 不注册 `db.*`。数据库能力全部走 `ctx.db`。

读取当前环境绑定代理时使用：

```python
proxy = await ctx.tools.call("env.get_proxy")
if proxy.get("resolved"):
    host = proxy["host"]
    port = proxy["port"]
    username = proxy.get("username")
    password = proxy.get("password")
```

`env.get_proxy` 只返回当前 task 绑定环境的只读代理快照。新 IP 池绑定会返回 `ip_entry_id`；旧环境如果只有历史 `ProxyConfig`，首次读取时宿主会按池和地址信息懒回填 `ip_entry_id`，解析不到时返回 `resolved=False`。

Hosted UI 的页面读取、渲染和 action 调用属于宿主 UI surface，不作为 workflow/page action 的普通 `TaskContext.tools` 能力示例。

浏览器相关正式边界：

- 标准页面交互优先走 `ctx.tools.call("browser.*", ...)`
- `ctx.page` 继续保留给读取标题、HTML、locator 状态、执行 `evaluate()`，以及宿主还没抽象成正式 tool 的浏览器能力
- `ctx.tools.has_tool(name)` 只接受精确工具名，不支持 `browser.*` 这类通配
- `browser.*` 由宿主统一执行拟人化节奏：停顿会分段并可带轻微 idle 漂移；点击使用元素内随机落点、鼠标 down/up dwell 和距离/目标尺寸驱动轨迹；输入支持自然分块、可控纠错概率和敏感文本默认不纠错；滚动使用惯性分段和轻微回调修正。`browser.drag` 的返回 trace 只用于模块或测试自检，会包含 `pre_pause`、`down_position`、`up_position`、`phase_names`、`phases[].samples`、`samples[].dt` 和 `sample_count`，便于验证事件完整性与两种拖拽模式的差异；`natural` 模式使用连续轨迹生成，并通过 profile、节奏权重、侧向扰动和末段修正提供变化性，`down -> up` 体感时长默认控制在 `0.9~2.8s`，移动点数按约 `54~66Hz` 采样生成，固定 `seed` 默认也会混入运行时随机盐，只有显式 `deterministic_seed=True` 才复现同一随机序列；回归自检覆盖采样率、`dt` 变化、速度变化、纵向微动和跨 seed 差异，越过目标和回拉不是必经步骤。该能力用于稳定标准页面交互，不承诺绕过站点风控。

## 生命周期与环境

0.4.0 不再把 `hooks/`、`env_selectors/` 或 `EnvSelectorSpec` 作为 SDK / Contracts 主路径。生命周期和资源等待由 Core 0.4.0 的运行模板、对象容器和宿主调度负责；模块侧只声明 `@workflow`、`@component`、`@page_action`、`@ui_action`、`@data_table`、`@data_view`、`@env_candidates` 与 `@env_cleanup_candidates`。

对象生命周期归宿主所有。Core 会在每个 task/env 内创建独立对象图，并在 `workflow.run(ctx)` 前按 component 组合顺序再到 workflow 调用可选 `setup(ctx, workflow)`；`workflow` 为 `WorkflowLifecycleInfo`，包含当前 workflow 名称、标签、描述和代码符号。终态时按 component 依赖反向顺序再到 workflow 调用可选 `cleanup(ctx, outcome)`，`outcome.workflow` 保存同一份 workflow 信息，`outcome.status` 为 `succeeded`、`failed`、`timed_out` 或 `cancelled`。setup 失败会阻止 `workflow.run(ctx)` 并进入 cleanup；cleanup 不设置宿主固定执行超时，异常只写日志，不覆盖任务终态或环境回收结果；用户停止或超时收尾期间，单个 cleanup 因停止信号抛出 `asyncio.CancelledError` 时也只记录该对象清理失败，并继续清理后续对象；旧 `aclose()` / `close()` 不再会被宿主调用。

环境选择写在 `candidates/*.py` 中，使用 `@env_candidates` 装饰同步纯函数。函数可以直接返回 env id 列表，也可以返回 `EnvCandidates.from_table(...).filter(...).order_by(...).limit(...)` 这样的链式查询。账号注册时间、会员等级、黑号状态等模块业务过滤应存放在模块数据表中，并在候选纯函数里实时查询，不需要同步资源池。运行模板的选择环境模式会保存候选函数名和可选 `candidate_params` 字典，UI 中可通过“候选参数”配置窗口填写 YAML 对象。

```python
from crawler4j_contracts import EnvCandidates, env_candidates


@env_candidates(name="ready_accounts")
def ready_accounts(params: dict | None = None) -> EnvCandidates:
    params = params or {}
    min_score = int(params.get("min_score", 80))
    limit = int(params.get("limit", 10))
    return (
        EnvCandidates.from_table("accounts")
        .filter(status="ready", score__gte=min_score)
        .order_by("last_used_at")
        .limit(limit)
    )
```

候选函数是同步纯函数，可以声明 `params` 接收运行模板候选参数，也可以声明 `ctx` 或 `context` 读取只读 `ctx.db`。候选函数不暴露 `ctx.tools`，也不创建、启动或销毁环境。

模块数据表如果代表账号、登录态或其他环境绑定业务实体，必须在 `@data_table(..., env_binding_field="env_id")` 中声明绑定字段；字段必须存在于 schema 且为 integer。宿主只通过这些声明扫描“模块是否已经认领环境”。

运行模板选择已有环境时，可直接指定固定 `env_id`，也可引用模块 `@env_candidates` 做动态筛选。宿主客户端的固定环境下拉只展示 `READY`、浏览器类型、无租约，且未归属或已归属当前模块的环境。

固定选择环境运行时，宿主会先临时标记该环境归属当前模块；任务终态后仍会按 `env_binding_field` 重新扫描业务表。如果没有任何业务数据绑定该环境，claim 会转为 abandoned，避免固定环境长期卡在“已归属但未认领”的中间态；已有业务绑定的环境继续保持 claimed。

批量环境清理写在 `cleanups/*.py` 中，使用 `@env_cleanup_candidates` 装饰同步纯函数。函数返回待清理 env id 列表或同一个 `EnvCandidates` 链式查询对象；这个入口只表达“模块认为已绑定且业务上可丢弃的候选集合”。宿主客户端触发清理时会同时扫描孤岛环境、任务创建后未被模块数据表认领的环境、owner 模块已不存在的环境，以及模块清理候选；展示预览后再二次校验 `READY/PAUSED`、无租约、无关联任务、无活跃 task 引用、未被当前 `ACTIVE` 运行模板固定引用，最后由 REM 调用 `destroy_env()` 删除。历史、暂停、已完成、异常或手动执行一次后无活跃任务的模板不会单独阻断清理。清理候选运行面只有只读 `ctx.db`，不暴露 `ctx.tools`。

```python
from crawler4j_contracts import env_cleanup_candidates


@env_cleanup_candidates(name="expired_accounts")
def expired_accounts(ctx) -> list[int]:
    rows = (
        ctx.db.from_("accounts")
        .select(["env_id"])
        .where(["status", "=", "expired"])
        .execute()
    )
    return [int(row["env_id"]) for row in rows if row.get("env_id") is not None]
```

模块 workflow 不允许导入或发送 `TaskSignal`、`TaskSignalAction`、`EnvAction` 这类流程/环境处置对象。单次运行结束、失败、超时或用户中止后的环境统一由宿主回收；模块若要表达“长期未使用”“黑号已废弃”“账号过期”等业务清理条件，只能通过 `@env_cleanup_candidates` 返回候选 env id，由宿主预览确认后执行。

如果历史模块仍依赖 `hooks/*.py`、`env_selectors/*.py`、`TaskSpec` 或 `WorkflowSpec`，它属于 0.3.x 维护线，需要在 0.3.x 分支处理，不在当前 0.4.x SDK / Contracts 中兼容。

## Hosted UI

页面文件使用 `@page` 装饰页面 load handler：

```python
from crawler4j_contracts import TaskContext, page

@page(
    name="dashboard",
    label="Dashboard",
    menu=True,
    schema={
        "type": "Page",
        "title": "Dashboard",
        "children": [],
    },
)
def load_dashboard_page(context: TaskContext, page_id: str, params: dict | None = None) -> dict:
    ...
```

正式约束：

- `@page.name` 是唯一扁平 snake_case
- `@page(menu=True)` 控制左侧菜单，`menu=False` 只注册可路由页面
- `schema` 顶层是 `Page`
- 被 `@page` 装饰的函数就是页面 `load_handler`
- `DataTable(query_handler)` 指向真实函数，签名固定为 `context, HostedDataTableQuery`，返回 `HostedDataTableQueryResult`
- `open_page.page_id` 可以跳到未进菜单的页面
- Hosted UI 按钮和 CRUD handler 使用 `type: "ui_action"` 调用 `@ui_action`

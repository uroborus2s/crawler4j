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
| Page | `@page` | Hosted UI 页面 schema、菜单状态与 load handler |
| Data Table | `@data_table` | 数据表声明 |
| Data Query | `@data_query` | 命名查询声明 |

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
- 同一 task/env 内复用
- 不同 task/env 互不共享
- 任务结束后按依赖反向顺序清理

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

## Page Action 调用

page action 必须是函数：

```python
@page_action(name="open_login_page")
async def open_login_page(ctx, url: str):
    ...
```

workflow 或 component 内调用：

```python
await ctx.run_page_action("open_login_page", url="https://example.com")
```

`ctx.run_subtask(...)` 不属于 0.4.0 新模块主路径。v2 编排对象应调用明确的 page action 或组件方法，不依赖旧子任务兼容名。

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

detail = ctx.db.named("ready_accounts").bind(status="ready").execute()

ctx.db.into("accounts").replace(rows)
ctx.db.into("accounts").upsert([{"account_id": "A001", "status": "ready"}])
ctx.db.into("accounts").update_where({"status": "used"}, where={"account_id": "A001"})
ctx.db.into("accounts").delete_where("status", "eq", "expired")

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

数据表和命名查询必须先由 `@data_table` / `@data_query` 声明并进入 manifest lock。
模块不需要管理数据库锁、事务提交或回滚；所有写入由宿主包装成短事务并自动排队、重试、提交或回滚。`replace()` 是全量覆盖语义，并发任务更新同一实体时优先使用 `custom_table` 的 `upsert/update_where/delete_where` 或 `batch()`。

## `TaskContext.tools`

`ctx.tools` 只承载非数据库宿主能力：

- `ctx.tools.has_tool(name)`
- `ctx.tools.list_tools()`
- `ctx.tools.call(name, **kwargs)`

常见类别：

| 类别 | 示例 |
|---|---|
| Hosted UI | `ui.get_page` |
| 环境与代理 | `env.set_proxy`、`ip_pool.pick_proxy` |
| 验证码 | `captcha.match_slider`、`captcha.match_click_targets` |

`ctx.tools` 不注册 `db.*`。数据库能力全部走 `ctx.db`。

## 生命周期与环境

0.4.0 不再把 `hooks/`、`env_selectors/` 或 `EnvSelectorSpec` 作为 SDK / Contracts 主路径。生命周期和资源等待由 Core 0.4.0 的运行模板、对象容器和宿主调度负责；模块侧只声明 `@workflow`、`@component`、`@page_action`、`@data_table`、`@data_query`、`@env_candidates` 与 `@env_cleanup_candidates`。

对象生命周期归宿主所有。Core 会在每个 task/env 内创建独立对象图，并在 workflow 成功、失败、超时、异常或被用户停止后清理 workflow 与 component 实例；清理顺序为 workflow 优先，然后 component 依赖反向顺序。模块对象只实现 `cleanup(ctx, outcome)`，`outcome.status` 为 `succeeded`、`failed`、`timed_out` 或 `cancelled`。清理异常只写日志，不覆盖任务终态或环境回收结果；旧 `aclose()` / `close()` 不再会被宿主调用。

环境选择写在 `candidates/*.py` 中，使用 `@env_candidates` 装饰同步纯函数。函数可以直接返回 env id 列表，也可以返回 `EnvCandidates.from_table(...).filter(...).order(...).limit(...)` 这样的链式查询。账号注册时间、会员等级、黑号状态等模块业务过滤应存放在模块数据表中，并在候选纯函数里实时查询，不需要同步资源池。

模块数据表如果代表账号、登录态或其他环境绑定业务实体，必须在 `@data_table(..., env_binding_field="env_id")` 中声明绑定字段；字段必须存在于 schema 且为 integer。宿主只通过这些声明扫描“模块是否已经认领环境”。

批量环境清理写在 `cleanups/*.py` 中，使用 `@env_cleanup_candidates` 装饰同步纯函数。函数返回待清理 env id 列表或同一个 `EnvCandidates` 链式查询对象；这个入口只表达“模块认为已绑定且业务上可丢弃的候选集合”。宿主客户端触发清理时会同时扫描孤岛环境、任务创建后未被模块数据表认领的环境、owner 模块已不存在的环境，以及模块清理候选；展示预览后再二次校验 `READY/PAUSED`、无租约、无关联任务、无活跃 task 引用、未被运行模板固定引用，最后由 REM 调用 `destroy_env()` 删除。清理候选运行面只有只读 `ctx.db`，不暴露 `ctx.tools`。

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
- `DataTable(query_handler)` 指向真实函数
- `open_page.page_id` 可以跳到未进菜单的页面

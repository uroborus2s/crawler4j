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

event_id = ctx.db.audit("account_events").append(
    entity_key="A001",
    event_type="status_changed",
    result="success",
    payload={"operator": "system"},
)
```

数据表和命名查询必须先由 `@data_table` / `@data_query` 声明并进入 manifest lock。

## `TaskContext.tools`

`ctx.tools` 只承载非数据库宿主能力：

- `ctx.tools.has_tool(name)`
- `ctx.tools.list_tools()`
- `ctx.tools.call(name, **kwargs)`

常见类别：

| 类别 | 示例 |
|---|---|
| Hosted UI | `ui.get_page` |
| 环境与资源池 | `env.*`、`ip_pool.pick_proxy` |
| 验证码 | `captcha.match_slider`、`captcha.match_click_targets` |

`ctx.tools` 不注册 `db.*`。数据库能力全部走 `ctx.db`。

## 生命周期 Hook

Hook 仍由宿主调度。每个 Hook 文件导出：

```python
async def handle(context: TaskContext):
    ...
```

常见 Hook：

- `prepare_env`
- `init_env`
- `before_run`
- `on_success`
- `on_failure`
- `on_timeout`
- `on_cleanup`

`on_cleanup` 是 best-effort。任务已暂停或中止时，不要从 cleanup 再启动新的 page action 或旧子任务。

## 环境选择器

环境选择器仍用于宿主环境选择：

```python
from crawler4j_contracts import EnvCandidate, EnvSelectorSpec, TaskContext

SELECTOR = EnvSelectorSpec(name="pick_ready")

def select(context: TaskContext, candidates: list[EnvCandidate]):
    ...
```

返回：

- `env_id`：宿主绑定环境
- `None`：当前轮未选中

当作业配置 `resource_pool` 时，`None` 进入等待语义；没有资源池时按失败处理。

## Hosted UI

页面文件导出 `PAGE`：

```python
from crawler4j_contracts import PageSpec

PAGE = PageSpec(
    id="dashboard",
    label="Dashboard",
    schema={...},
)
```

正式约束：

- `PAGE.id` 是唯一扁平 snake_case
- `module.yaml.ui_extension.pages[]` 只控制左侧菜单
- `PAGE.schema` 顶层是 `Page`
- `load_handler` 指向真实函数
- `DataTable(query_handler)` 指向真实函数
- `open_page.page_id` 可以跳到未进菜单的页面

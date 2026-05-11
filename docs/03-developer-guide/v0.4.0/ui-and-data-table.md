# UI 与数据表

> 版本绑定：本文只适用于 0.4.x SDK / Contracts 与 Core 0.4.0。0.4.x Hosted UI、页面动作和数据读取按 `@page`、`@ui_action`、`@page_action`、`@data_table`、`@data_view` 工作，不兼容 0.3.x 数据命令或任务按钮模式。

0.4.0 的 UI 仍由宿主渲染，页面源码仍放在 `pages/`。变化在数据和动作来源：

- 页面 schema 来自 `@page` 装饰器
- 用户按钮和 CRUD 只调用 `@ui_action`
- workflow 浏览器自动化动作调用 `@page_action`
- 数据表和视图读取 `@data_table` / `@data_view` 注册后的 `ctx.db`
- 左侧菜单由 `@page(menu=True)` 决定，`module.yaml` 不再声明 UI

## 页面入口

页面文件：

```python
from crawler4j_contracts import TaskContext, page

@page(
    name="dashboard",
    label="Dashboard",
    icon="chart",
    menu=True,
    schema={
        "type": "Page",
        "title": "Dashboard",
        "children": [
            {"type": "Text", "style": "title", "binding": "title"},
        ],
    },
)
def load_dashboard_page(
    context: TaskContext,
    page_id: str,
    params: dict | None = None,
) -> dict:
    del context, page_id, params
    return {"title": "Dashboard"}
```

菜单和路由是两件事：

- `@page(menu=True)`：页面进入左侧菜单，也可路由打开
- `@page(menu=False)`：页面可通过 `open_page.page_id` 打开，但不进菜单

`@page` 装饰的函数就是页面 `load_handler`。如需显式写 `schema["load_handler"]`，它必须与被装饰函数名一致。

## UI 操作

按钮目标只能触发宿主动作 `reload` / `open_page`，或触发 `@ui_action`。Hosted UI 用户操作必须绑定 `ui_action`；`page_action` 不是合法的 Hosted UI 按钮 action type。

```python
{
    "type": "Button",
    "label": "创建账号",
    "action": {
        "type": "ui_action",
        "name": "create_account_from_ui",
        "params": {"account_id": {"binding": "selected.id"}},
    },
}
```

UI action 示例：

```python
from crawler4j_contracts import TaskContext, ui_action


@ui_action(name="create_account_from_ui")
def create_account_from_ui(ctx: TaskContext, account_id: str):
    ctx.db.into("accounts").update_where({"status": "active"}, where=account_id)
    return {"ok": True}
```

`Button.action.params` 会被解析成 `@ui_action` 的命名参数。`{"account_id": {"binding": "selected.id"}}` 会从当前页面 `load_handler` 返回的 payload 里读取 `selected.id`，然后调用 `create_account_from_ui(ctx, account_id=...)`。

`@ui_action` 不依赖浏览器页面，不调用 `ctx.run_page_action(...)`。它适合 Hosted UI 按钮、CRUD handler、刷新、导出和表单提交。需要操作真实浏览器页面时，把动作写成 `@page_action`，并由 workflow/component 通过 `ctx.run_page_action(...)` 调用。

`@page_action` 内部不要再调用另一个 `@page_action` 拆公共步骤。公共页面动作应抽成普通函数、browser adapter 或 use case；多个可观测页面动作的顺序由 workflow/component 编排。

## DataTable 数据源

### binding

从 `load_handler` 返回值读取：

```python
{
    "type": "DataTable",
    "table_id": "accounts",
    "columns": [
        {"key": "account_id", "label": "账号"},
        {"key": "status", "label": "状态", "type": "badge"},
    ],
    "data_source": {"type": "binding", "binding": "rows"},
}
```

`DataTable.columns` 中 `searchable` 与 `sortable` 都是显式 opt-in：未写 `searchable=True` 的列不会参与搜索，未写 `sortable=True` 的列不会响应表头排序，也不会进入 `query.sort`。

```python
def load_accounts_page(context: TaskContext, page_id: str, params: dict | None = None) -> dict:
    del page_id, params
    rows = context.db.from_("accounts").limit(100).execute()
    return {"rows": rows}
```

### query_handler

把分页、筛选、排序交给页面 handler。`DataTable.table_id` 只是页面内组件实例 ID，用于宿主渲染和刷新定位；它不是数据库资源名，也不会作为 handler 入参。一个表格可以由多个 `@data_table` / `@data_view` 查询结果组装而成。

```python
from crawler4j_contracts import HostedDataTableQuery, HostedDataTableQueryResult, TaskContext


def query_accounts_table(
    context: TaskContext,
    query: HostedDataTableQuery,
) -> HostedDataTableQueryResult:
    rows = (
        context.db.from_("accounts")
        .limit(query.limit)
        .offset(query.offset)
        .execute()
    )
    return HostedDataTableQueryResult(
        rows=rows,
        total=len(rows),
        page=query.page,
        page_size=query.page_size,
    )
```

正式签名固定为：

```python
(context, query: HostedDataTableQuery) -> HostedDataTableQueryResult
```

`HostedDataTableQuery` 固定字段：

- `search_text`
- `search_fields`
- `sort`
- `page`
- `page_size`
- `params`
- 计算属性 `limit`、`offset`

`search_fields` 由当前 `DataTable.columns` 中显式设置 `searchable=True` 且不是 `actions` 类型的列 `key` 生成；未写 `searchable` 的列默认不可搜索。模块 handler 应只在这些字段上处理 `search_text`。`sort` 来自当前表格列点击或 `features.sort.default`，字段值同样是列 `key`；未显式设置 `sortable=True` 的列默认不可排序，宿主会过滤掉不可排序列和非法方向。`params` 承载页面导航参数，例如主表打开详情表时传入的账号 ID。

返回值必须是 `HostedDataTableQueryResult[RowT]`，`RowT` 是一行数据的泛型 mapping 类型；结果字段固定为 `rows`、`total`、`page`、`page_size`。结果不再回传 `sort`，排序状态由发起查询时的 `HostedDataTableQuery.sort` 表达；宿主渲染层不再接受普通 `dict` 作为 query handler 返回值。

如果 handler 只是把表格查询下推到 `ctx.db.from_(...)`，可以用 `HostedDataTableQuery.to_query_callback(...)` 生成查询回调：

```python
FIELD_MAP = {
    "account_id": "account_id",
    "status": "account_status",
    "createdAt": "created_at",
}


def query_accounts_table(
    context: TaskContext,
    query: HostedDataTableQuery,
) -> HostedDataTableQueryResult:
    callback = query.to_query_callback(
        FIELD_MAP,
        sort=lambda field: field in {"created_at"},
        like=lambda field: field in {"account_id", "account_status"},
        eq=lambda field: field in {"account_id"},
    )
    rows = callback(context.db.from_("accounts")).execute()
    return HostedDataTableQueryResult(rows=rows, total=len(rows), page=query.page, page_size=query.page_size)
```

`FIELD_MAP` 的 key 是 UI 表格字段，value 是 `ctx.db` 数据源字段；`search_fields`、`sort.field` 和 `params` 中没有出现在映射里的字段会被忽略，不会下推到数据库。`like`、`sort`、`eq` 三个可选函数用于二次判断映射后的字段是否合法：输入字段名，返回 `True` 才会生成对应的 `LIKE` 搜索、`order_by` 排序或 `=` 参数过滤。`search_text` 会按有效 `search_fields` 生成 OR `LIKE` 条件，`params` 会生成 `=` 条件，分页会生成 `limit(query.page_size).offset(query.offset)`。

### managed_resource

直接绑定已由 `@data_table` 声明的数据表：

```python
{
    "type": "DataTable",
    "table_id": "accounts",
    "columns": [
        {"key": "account_id", "label": "账号"},
        {"key": "status", "label": "状态", "type": "badge"},
    ],
    "data_source": {"type": "managed_resource", "resource_id": "accounts"},
}
```

`resource_id` 必须来自装饰器扫描和 manifest lock。

## CRUD

如果表格需要增删改，schema 只声明交互，真正写入走 `@ui_action` handler 和 `ctx.db`：

```python
{
    "type": "DataTable",
    "table_id": "accounts",
    "data_source": {"type": "managed_resource", "resource_id": "accounts"},
    "crud": {
        "mode": "handlers",
        "render": "row_actions",
        "primary_key": "account_id",
        "toolbar": {"create": True},
        "create_handler": "create_account",
        "update_handler": "update_account",
        "delete_handler": "delete_account",
        "form": {
            "create_columns": ["name", "secret"],
            "update_columns": ["name", "secret"],
        },
    },
}
```

```python
from crawler4j_contracts import TaskContext, ui_action


@ui_action(name="create_account")
def create_account(context: TaskContext, payload: dict) -> dict:
    context.db.into("accounts").add([payload])
    return {"ok": True}


@ui_action(name="update_account")
def update_account(context: TaskContext, account_id: str, payload: dict) -> dict:
    context.db.into("accounts").update_where(payload, where=account_id)
    return {"ok": True}


@ui_action(name="delete_account")
def delete_account(context: TaskContext, account_id: str) -> dict:
    context.db.into("accounts").delete_where(where=account_id)
    return {"ok": True}
```

CRUD 参数来源固定：

- `create_handler`：调用 `create_account(ctx, payload=form_payload)`；`payload` 来自 `crud.form.create_columns` 弹窗表单。
- `update_handler`：调用 `update_account(ctx, account_id=row_key, payload=form_payload)`；`account_id` 这个参数名来自 `crud.primary_key`，`row_key` 来自当前选中行的 `selected_row[primary_key]`。
- `delete_handler`：调用 `delete_account(ctx, account_id=row_key)`；参数名同样来自 `crud.primary_key`。

`@page(schema=...)` 的类型提示由 `crawler4j_contracts.PageSchema` 提供；`DataTable.crud.primary_key`、`create_handler`、`update_handler`、`delete_handler` 和 `form.create_columns/update_columns` 都在这个 schema 类型里声明。

## 页面滚动

页面级滚动配置：

```python
{"scroll": {"vertical": "auto"}}
{"scroll": {"vertical": "hidden"}}
```

`hidden` 只隐藏外层滚动槽，仍保留滚轮和触控板滚动。

## 旧概念

这些只在迁移时出现：

- 运行时代码声明页面
- 运行时代码声明表或视图
- `ctx.tools.call("db.*")`

0.4.0 新页面只通过页面 schema、handler、ui action、page action 和 `ctx.db` 工作。

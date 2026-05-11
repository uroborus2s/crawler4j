# UI 与数据表

> 版本绑定：本文只适用于 0.4.x SDK / Contracts 与 Core 0.4.0。0.4.x Hosted UI、页面动作和数据读取按 `@page`、`@ui_action`、`@page_action`、`@data_table`、`@data_view` 工作，不兼容 0.3.x 数据命令或任务按钮模式。

0.4.0 的 UI 仍由宿主渲染，页面源码仍放在 `pages/`。变化在数据和动作来源：

- 页面 schema 来自 `@page` 装饰器
- 用户按钮和 CRUD 优先调用 `@ui_action`
- workflow 浏览器自动化动作调用 `@page_action`
- 数据表和视图读取 `@data_table` / `@data_view` 注册后的 `ctx.db`
- 左侧菜单由 `@page(menu=True)` 决定，`module.yaml` 不再声明 UI

## 页面入口

页面文件：

```python
from crawler4j_contracts import HostedPageLoadResult, HostedPageParams, TaskContext, page

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
    params: HostedPageParams | None = None,
) -> HostedPageLoadResult:
    del context, page_id, params
    return {"title": "Dashboard"}
```

菜单和路由是两件事：

- `@page(menu=True)`：页面进入左侧菜单，也可路由打开
- `@page(menu=False)`：页面可通过 `open_page.page_id` 打开，但不进菜单

`@page` 装饰的函数就是页面 `load_handler`。如需显式写 `schema["load_handler"]`，它必须与被装饰函数名一致。

## UI 操作

按钮目标上可以触发宿主动作，也可以触发 UI action。Hosted UI 用户操作优先绑定 `ui_action`，不要把按钮、CRUD 或表单提交继续塞进 `@page_action`。

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
def create_account_from_ui(ctx: TaskContext, payload: dict):
    ctx.db.into("accounts").upsert([payload])
    return {"ok": True}
```

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
        {"key": "id", "label": "ID", "visible": False},
        {"key": "account_id", "label": "账号"},
        {"key": "status", "label": "状态", "type": "badge"},
    ],
    "data_source": {"type": "binding", "binding": "rows"},
}
```

```python
def load_accounts_page(
    context: TaskContext,
    page_id: str,
    params: HostedPageParams | None = None,
) -> HostedPageLoadResult:
    del page_id, params
    rows = context.db.from_("accounts").limit(100).execute()
    return {"rows": rows}
```

### query_handler

把分页、筛选、排序交给页面 handler：

```python
from typing import TypedDict

from crawler4j_contracts import (
    HostedDataTableQuery,
    HostedDataTableQueryResult,
    HostedPageParams,
    TaskContext,
)


class AccountRow(TypedDict):
    id: int
    account_id: str
    status: str


def query_accounts_table(
    context: TaskContext,
    table_id: str,
    query: HostedDataTableQuery,
    params: HostedPageParams | None = None,
) -> HostedDataTableQueryResult[AccountRow]:
    del table_id, params
    page_size = query.get("page_size", 20)
    page = query.get("page", 1)
    rows = (
        context.db.from_("accounts")
        .limit(page_size)
        .offset(max(page - 1, 0) * page_size)
        .execute()
    )
    return {
        "rows": rows,
        "total": len(rows),
        "page": page,
        "page_size": page_size,
    }
```

正式签名固定为：

```python
def query_handler(
    context: TaskContext,
    table_id: str,
    query: HostedDataTableQuery,
    params: HostedPageParams | None = None,
) -> HostedDataTableQueryResult[RowType]:
    ...
```

`crawler4j check full` 会拒绝未使用上述参数名、同步函数形态、参数类型或返回类型的 `query_handler`。

`HostedDataTableQueryResult` 中的 `page` / `page_size` 可省略；省略时宿主会沿用本次 `query` 里的分页值，不会把回调查询结果重置到默认页。

`rows` 的字段名和 `columns[].key` 对齐；`columns[].visible` 默认是可见，显式写 `visible=False` 时该列不渲染，但 row 里的字段仍会保留，可用于 `row_action.params`、CRUD 主键或详情页跳转。

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

如果表格需要增删改，schema 只声明交互，真正写入仍走 `@ui_action` handler 和 `ctx.db`：

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
    },
}
```

```python
def create_account(context: TaskContext, payload: dict) -> dict:
    context.db.into("accounts").replace([payload])
    return {"ok": True}
```

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

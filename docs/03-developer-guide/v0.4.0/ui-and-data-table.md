# UI 与数据表

> 版本绑定：本文只适用于 0.4.x SDK / Contracts 与 Core 0.4.0。0.4.x 页面动作和数据读取按 `@page_action`、`@data_table`、`@data_query` 工作，不兼容 0.3.x 数据命令或任务按钮模式。

0.4.0 的 UI 仍由宿主渲染，页面源码仍放在 `pages/`。变化在数据和动作来源：

- 页面 schema 来自 `@page` 装饰器
- 页面动作优先调用 `@page_action`
- 数据表读取 `@data_table` / `@data_query` 注册后的 `ctx.db`
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

## 页面动作

按钮目标上可以触发宿主动作，也可以触发 page action。0.4.0 模块里的业务按钮优先绑定 `page_action`，不要回退到 0.3.x 任务按钮模式。

```python
{
    "type": "Button",
    "label": "打开登录页",
    "action": {
        "type": "page_action",
        "name": "open_login_page",
        "params": {"url": "https://example.com"},
    },
}
```

page action 示例：

```python
from crawler4j_contracts import page_action


@page_action(name="open_login_page")
async def open_login_page(ctx, url: str):
    await ctx.page.goto(url)
    return {"opened": True}
```

复杂编排不要放在 button handler 或 page action 里。放到 workflow 注入的 orchestrator component。

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

```python
def load_accounts_page(context: TaskContext, page_id: str, params: dict | None = None) -> dict:
    del page_id, params
    rows = context.db.from_("accounts").limit(100).execute()
    return {"rows": rows}
```

### query_handler

把分页、筛选、排序交给页面 handler：

```python
def query_accounts_table(
    context: TaskContext,
    table_id: str,
    query: dict,
    params: dict | None = None,
) -> dict:
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
(context, table_id, query, params=None)
```

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

如果表格需要增删改，schema 只声明交互，真正写入仍走 handler 和 `ctx.db`：

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

0.4.0 新页面只通过页面 schema、handler、page action 和 `ctx.db` 工作。

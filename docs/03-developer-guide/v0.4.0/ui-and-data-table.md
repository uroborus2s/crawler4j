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
    ctx.db.into("accounts").update_where({"status": "active"}, where=["account_id", "=", account_id])
    return {"ok": True}
```

`Button.action.params` 会被解析成 `@ui_action` 的命名参数。`{"account_id": {"binding": "selected.id"}}` 会从当前页面 `load_handler` 返回的 payload 里读取 `selected.id`，然后调用 `create_account_from_ui(ctx, account_id=...)`。

`@ui_action` 不依赖浏览器页面，不调用 `ctx.run_page_action(...)`。它适合 Hosted UI 按钮、CRUD handler、刷新、导出和表单提交。它不是 workflow/component 对象图节点，不支持通过 `@ui_action` 注入 component；需要复用业务逻辑时，把逻辑放到普通函数、服务对象或 `ctx.db` 等正式运行面里。需要操作真实浏览器页面时，把动作写成 `@page_action`，并由 workflow/component 通过 `ctx.run_page_action(...)` 调用。

`@page_action` 内部不要再调用另一个 `@page_action` 拆公共步骤。公共页面动作应抽成普通函数、browser adapter 或 use case；多个可观测页面动作的顺序由 workflow/component 编排。

## Toolbar 与批量导入

页面和 `DataTable` 都可以声明 `toolbar.actions[]`。toolbar 普通动作可调用 `@ui_action`，长耗时动作可调度 workflow；需要读取本地文件或剪贴板时，必须使用宿主复合动作 `open_import_dialog`。模块代码不会拿到本地文件路径、文件句柄或二进制内容，只会收到宿主解析后的 JSON-compatible `import_payload`。

页面级导入按钮：

```python
@page(
    name="accounts",
    label="账号管理",
    schema={
        "type": "Page",
        "toolbar": {
            "actions": [
                {
                    "id": "import_accounts",
                    "label": "导入账号",
                    "icon": "upload",
                    "action": {
                        "type": "open_import_dialog",
                        "target_type": "ctrip_account",
                        "business_key_field": "phone",
                        "source_types": ["file", "clipboard", "manual"],
                        "field_mapping": {"手机号": "phone", "姓名": "name"},
                        "limits": {
                            "max_file_size_bytes": 10485760,
                            "max_rows": 5000,
                        },
                        "submit": {"type": "ui_action", "name": "import_accounts"},
                    },
                }
            ]
        },
        "children": [],
    },
)
def load_accounts_page(context: TaskContext, page_id: str, params: dict | None = None) -> dict:
    del context, page_id, params
    return {}
```

表格级 toolbar 写在 `DataTable` 组件上，动作语义相同：

```python
{
    "type": "DataTable",
    "table_id": "accounts",
    "data_source": {"type": "managed_resource", "resource_id": "accounts"},
    "columns": [{"key": "phone", "label": "手机号"}],
    "toolbar": {
        "actions": [
            {
                "id": "import_accounts",
                "label": "导入",
                "action": {
                    "type": "open_import_dialog",
                    "target_type": "ctrip_account",
                    "submit": {"type": "ui_action", "name": "import_accounts"},
                },
            }
        ]
    },
}
```

`@ui_action` 默认必须接收 `import_payload` 参数；如 schema 写了 `submit.payload_param`，函数参数名也要一致：

```python
@ui_action(name="import_accounts")
async def import_accounts(context: TaskContext, import_payload: dict):
    rows = import_payload["rows"]
    # 模块在这里做业务校验、暂存、去重和落库。
    return {
        "batch_id": "imp-001",
        "total_rows": len(rows),
        "staged_rows": len(rows),
        "failed_rows": 0,
        "target_type": import_payload["target_type"],
        "records_page_id": "import_data_records",
    }
```

返回 `records_page_id="import_data_records"` 时，宿主会带 `batch_id` 和 `target_type` 打开该页面。该页面和暂存明细表由模块用 `@page` / `DataTable` / `@data_table` / `ctx.db` 自行实现；宿主不提供统一业务暂存物理表。建议逐条状态使用 `pending`、`staged`、`validation_failed`、`imported`、`import_failed`、`skipped_duplicate`。

如果提交给 workflow：

```python
"submit": {"type": "workflow", "name": "import_accounts"}
```

宿主会创建 batch/manual job，并把 payload 写入 `ctx.runtime["import_payload"]`。workflow 不应读取本地文件，也不应把完整 `rows`、`raw_payload`、token、cookie、密码等敏感字段写进日志。

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

当列声明为 `type="select"`、提供非空 `options`，并显式写 `searchable=True` 时，宿主会在表格工具栏渲染该列的快速筛选下拉。选择非全量项会写入 `HostedDataTableQuery.params[column.key]`；选择 `不限`、`全部`、`all`、`__all__` 或空值会清除该筛选。启用排序且存在 `sortable=True` 列时，宿主除了保留表头点击排序，也会提供可见的排序字段和升降序控件，两种入口共享同一份 `query.sort` 状态。

```python
def load_accounts_page(context: TaskContext, page_id: str, params: dict | None = None) -> dict:
    del page_id, params
    rows = context.db.from_("accounts").limit(100).execute()
    return {"rows": rows}
```

`DataTable.data_source` 也支持短小静态行：`{"type": "rows", "rows": [...]}`。固定枚举、示例数据或空状态可以用它；会增长的数据仍应使用 binding、query_handler 或 managed_resource。

### query_handler

把分页、筛选、排序交给页面 handler。`DataTable.table_id` 只是页面内组件实例 ID，用于宿主渲染和刷新定位；它不是数据库资源名，也不会作为 handler 入参。一个表格可以由多个 `@data_table` / `@data_view` 查询结果组装而成。

```python
{
    "type": "DataTable",
    "table_id": "accounts",
    "columns": [
        {"key": "account_id", "label": "账号", "searchable": True},
        {"key": "status", "label": "状态", "type": "badge", "sortable": True},
    ],
    "data_source": {"type": "query_handler", "handler": "query_accounts_table"},
}
```

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
    total = context.db.from_("accounts").count(alias="total").execute()[0]["total"]
    return HostedDataTableQueryResult(
        rows=rows,
        total=total,
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

`search_fields` 由当前 `DataTable.columns` 中显式设置 `searchable=True` 且不是 `actions` 类型的列 `key` 生成；未写 `searchable` 的列默认不可搜索。模块 handler 应只在这些字段上处理 `search_text`。`sort` 来自当前表格列点击、工具栏排序控件或 `features.sort.default`，字段值同样是列 `key`；未显式设置 `sortable=True` 的列默认不可排序，宿主会过滤掉不可排序列和非法方向。`params` 同时承载页面导航参数和表格工具栏筛选参数，例如主表打开详情表时传入的账号 ID，或 select 快速筛选写入的状态值。宿主会先合并导航参数，再合并表格参数；同名冲突时，以用户在当前表格上显式选择的筛选值为准。

返回值必须是 `HostedDataTableQueryResult[RowT]`，`RowT` 是一行数据的泛型 mapping 类型；结果字段固定为 `rows`、`total`、`page`、`page_size`。结果不再回传 `sort`，排序状态由发起查询时的 `HostedDataTableQuery.sort` 表达；宿主渲染层不再接受普通 `dict` 作为 query handler 返回值。

如果 handler 只是把表格查询下推到 `ctx.db.from_(...)`，可以用 `HostedDataTableQuery.to_result(...)` 归一化 rows/count 查询和 UI 行转换：

```python
def map_search_field(field: str) -> str | None:
    return {
        "account_id": "account_id",
        "status": "account_status",
    }.get(field)


def map_sort_field(field: str) -> str | None:
    return {
        "createdAt": "created_at",
    }.get(field)


def map_filter_field(key: str, value: object) -> str | tuple[str, object] | None:
    if key == "account_id":
        return "account_id"
    if key == "enabled":
        return ("is_enabled", str(value).strip().lower() in {"1", "true", "yes", "on"})
    return None


def to_table_row(row: dict[str, object]) -> dict[str, object]:
    return {
        "account_id": row["account_id"],
        "status": row["account_status"],
        "createdAt": row["created_at"],
    }


def query_accounts_table(
    context: TaskContext,
    query: HostedDataTableQuery,
) -> HostedDataTableQueryResult:
    return query.to_result(
        lambda callback: callback(context.db.from_("accounts")).execute(),
        lambda callback: callback(context.db.from_("accounts")).count(alias="total").execute()[0]["total"],
        to_table_row,
        search_transform=map_search_field,
        sort_transform=map_sort_field,
        filter_transform=map_filter_field,
    )
```

`search_transform` 和 `sort_transform` 都是单字段回调：输入 UI 字段名，返回数据库字段名；返回 `None` 或空字符串表示过滤该字段。`sort_transform` 只能改字段名或过滤字段，排序方向始终保留 `HostedDataTableSortSpec.direction` 原值。`filter_transform` 是单参数回调：输入 `params` 中的 `key, value`，返回字段名表示只改 key、返回 `(new_key, new_value)` 表示同时改 key/value、返回 `None` 表示过滤该参数。未提供 transform 时，字段按原名下推。`search_text` 会按有效 `search_fields` 生成 OR `LIKE` 条件，`params` 会生成 `=` 条件，rows 查询会生成 `order_by/limit/offset`，count 查询只复用搜索与参数过滤，不生成排序或分页。

如果需要分开处理仓储查询和结果归一化，也可以先调用 `query.to_query(...)` 得到 `(total, rows)`，再用 `HostedDataTableQueryResult.from_query(query, query_result, to_table_row)` 生成标准返回值。`to_result(...)` 只是把这两个步骤合在一起，`page/page_size` 会直接来自当前 `HostedDataTableQuery`，不需要额外传入。

SDK 会在扫描阶段校验 `query_handler`：handler 必须定义在同一个 `pages/*.py` 模块中，必须是同步函数，并且签名能按 `(context, query)` 位置参数调用。缺失、异步或签名不兼容会在 `crawler4j check full` / manifest lock / 打包前被诊断出来。

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

`resource_id` 必须来自装饰器扫描和 manifest lock。宿主会把搜索、排序和分页下推到模块数据存储，不会先固定读取前 1000 行再在内存中过滤；表格 `total` 应反映满足当前搜索条件的完整记录数。

## CRUD

如果表格需要增删改，schema 只声明交互，真正写入走 `@ui_action` handler 和 `ctx.db`：

```python
{
    "type": "DataTable",
    "table_id": "accounts",
    "columns": [
        {"key": "account_id", "label": "账号", "sortable": True},
        {"key": "name", "label": "名称", "searchable": True},
        {"key": "secret", "label": "密钥"},
        {"key": "actions", "label": "操作", "type": "actions"},
    ],
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
from typing import TypedDict

from crawler4j_contracts import DataTableCrudResult, TaskContext, ui_action


class AccountCreatePayload(TypedDict):
    name: str
    secret: str


class AccountUpdatePayload(TypedDict, total=False):
    name: str
    secret: str


@ui_action(name="create_account")
def create_account(context: TaskContext, payload: AccountCreatePayload) -> DataTableCrudResult:
    context.db.into("accounts").add([payload])
    return {"ok": True}


@ui_action(name="update_account")
def update_account(
    context: TaskContext,
    account_id: str,
    payload: AccountUpdatePayload,
) -> DataTableCrudResult:
    context.db.into("accounts").update_where(payload, where=["account_id", "=", account_id])
    return {"ok": True}


@ui_action(name="delete_account")
def delete_account(context: TaskContext, account_id: str) -> DataTableCrudResult:
    context.db.into("accounts").delete_where(where=account_id)
    return {"ok": True}
```

CRUD 参数来源固定：

- `create_handler`：调用 `create_account(ctx, payload=form_payload)`；`payload` 来自 `crud.form.create_columns` 弹窗表单。
- `update_handler`：调用 `update_account(ctx, account_id=row_key, payload=form_payload)`；`account_id` 这个参数名来自 `crud.primary_key`，`row_key` 来自当前选中行的 `selected_row[primary_key]`。
- `delete_handler`：调用 `delete_account(ctx, account_id=row_key)`；参数名同样来自 `crud.primary_key`。

`actions` 列可以在同一行里追加自定义按钮。点击 `__crud_update__` / `__crud_delete__` 仍走内置编辑和删除流程；未声明 `type` 的其他 action id 默认调用同名 `@ui_action`，并按 `crud.primary_key` 从当前行组装单个命名参数，例如 `crud.primary_key="phone"` 且当前行 `phone="13800138000"` 时调用 `verify_phone(ctx, phone="13800138000")`。

行按钮也可以显式声明 `type="open_page"`，用当前行字段打开详情页：

```python
{
    "account_id": "acct-001",
    "actions": [
        {
            "id": "open_details",
            "label": "详情",
            "type": "open_page",
            "page_id": "account_details",
            "params": {
                "account_id": {"binding": "account_id"},
            },
        },
    ],
}
```

`open_page` 行按钮只解析显式 `params`，不使用 `crud.primary_key` 兜底；未声明 `params` 时目标页收到 `None`。导航不会调用同 ID 的 `@ui_action`，也不会刷新源表。多选表格需要同时保留整行选择时，优先使用这种显式详情按钮；顶层 `row_action` 仍表示整行单击导航。

CRUD handler 签名必须写成确定参数，不允许用 `**kwargs` 或 `Mapping[str, Any]` 模糊接收输入：

- `create_handler`：`(context, payload)`，`payload` 建议使用模块自定义 `TypedDict`，字段应覆盖 `crud.form.create_columns`。
- `update_handler`：`(context, <primary_key>, payload)`，主键参数名必须等于 `crud.primary_key`，`payload` 建议使用模块自定义 `TypedDict`，字段应覆盖 `crud.form.update_columns`。
- `delete_handler`：`(context, <primary_key>)`，主键参数名必须等于 `crud.primary_key`，主键参数要标注具体标量类型，例如 `str` 或 `int`。

`@page(schema=...)` 的类型提示由 `crawler4j_contracts.PageSchema` 提供；`DataTable.crud.primary_key`、`create_handler`、`update_handler`、`delete_handler` 和 `form.create_columns/update_columns` 都在这个 schema 类型里声明。

### 字段 change 与 Form reset

独立 `Input` / `Select` 和 CRUD Form 字段可以声明同一个公共事件：

```python
{
    "key": "preset",
    "label": "方案",
    "type": "select",
    "options": ["basic", "advanced"],
    "default": "basic",
    "on_change": {"type": "ui_action", "name": "handle_field_change"},
}
```

`on_change` handler 固定接收 `HostedFieldChangeEvent`：

```python
from crawler4j_contracts import HostedFieldChangeEvent, TaskContext, ui_action


@ui_action(name="handle_field_change")
def handle_field_change(context: TaskContext, event: HostedFieldChangeEvent) -> None:
    scope = event["scope"]
    if scope["kind"] != "form":
        return
    context.tools.call(
        "ui.form.reset",
        form_id=scope["form_id"],
        initial_values={
            **scope["values"],
            "priority": 0,
            "enabled": False,
            "note": "",
            "marker": "undefined",
        },
    )
```

Form 事件包含组件/字段标识、`value`、`previous_value` 和 `scope.kind/form_id/mode/values`；Form 外事件的 scope 只有 `{"kind":"standalone"}`。模块只有在 Form 事件中才能使用 handle。reset 会用模块传入的整张 `initial_values` 同时替换当前值和初始值，并清理 dirty/validation；它不会提交，也不会调用 create/update handler。

create Form 用 column `default` 初始化，update Form 优先使用当前 row 实际值；两者都按键存在性保留 `0`、`False`、`""` 和字面量 `"undefined"`。字段很多时表单内容区域可滚动，确认/取消按钮保持可见。

CRUD Form 需要多列时，可在原有 `crud.form` 中声明：

```python
"form": {
    "create_columns": ["field_a", "field_b", "field_c"],
    "update_columns": ["field_a", "field_b", "field_c"],
    "layout": {"columns": 3, "gap": 12},
}
```

`columns` 只接受整数 `1`、`2`、`3`，`gap` 可省略或使用非负整数。未声明 `layout` 时仍为一列。字段按声明顺序逐行排列；窄屏会自动降低列数，对话框不会超过 renderer 所在屏幕的可用区域，超大 gap 也会收敛到该屏幕可展示范围，按钮区始终位于滚动区外。布局只影响展示，不改变 create default、update row、change 事件、reset 或最终提交值。

字段事件只允许 `type="ui_action"` 和 `name`，SDK 会校验 handler 的 `(context, event: HostedFieldChangeEvent)` 签名。快速连续 change 使用 latest-wins reset 语义；旧 handler 不能覆盖新选择。未声明 `on_change` 的字段保持既有行为。

当前源码联调仍使用 Contracts `0.4.3` / SDK `0.4.4`，本轮没有发布新包。外部模块可临时安装本地 editable 源码：

```bash
uv pip install --python .venv/bin/python \
  --editable /Users/uroborus/PythonProject/crawler4j/packages/crawler4j-contracts \
  --editable /Users/uroborus/PythonProject/crawler4j/packages/crawler4j-sdk
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

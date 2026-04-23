# UI 与数据表

模块在宿主中的正式 UI 已经收口到纯 UI 页面模式。模块只声明页面 schema，并返回页面数据；宿主统一渲染，不再执行模块侧 UI 代码。

## 先记住唯一正式边界

- `module.yaml.ui_extension.pages[]` 只声明导航元信息：`id`、`label`、`icon`
- `declare_ui(context)` 只调用 `ui.declare_page(page_id=..., schema=...)`
- 页面 schema 的顶层必须是 `Page`
- `DataTable` 只是页面内组件，不再是独立宿主页型
- 所有页面数据都必须由模块或 Core 其它能力以结构化数据形式传给页面

换句话说：

- 宿主负责 UI 渲染、表格交互、分页控件、错误提示
- 模块负责页面组装逻辑、数据读取、业务动作和查询 handler
- 宿主不再替模块管理“数据表页面 schema”或“表格 CRUD 业务语义”

## 先确定落点

| 需求 | 正式落点 |
|---|---|
| Dashboard、说明页、操作入口、只读概览 | `Page` + `Text` + `Button` + `DataTable` |
| 当前账号列表、酒店列表、开关清单 | `Page` + `DataTable` + `db.list_records` / `db.replace_records` |
| 高频计算明细、运行审计、计费明细 | `Page` + `DataTable` + `db.declare_data_resource(storage_mode="custom_table")` |
| 基于实体表的汇总统计、条件查询、排序分页 | `Page` + `DataTable(data_source.type="query_handler")` + `db.query_view` |
| 历史时间线、操作留痕、状态流转 | `db.append_event` / `db.query_events`，必要时再由页面自行组合展示 |

## 一条接入主线

模块 UI 的标准开发顺序固定如下：

1. 用 SDK CLI 生成页面骨架：
   - `uv run crawler4j page create dashboard`
   - `uv run crawler4j page create accounts`
2. CLI 会同时更新两处：
   - `module.yaml.ui_extension.pages[]`
   - `module_runtime.py`
3. 你补完 schema、`load_handler`、内联表格 `query_handler`
4. 执行 `uv run crawler4j check full`
5. 用 DevLink 接入宿主验证页面是否能被宿主重放

这条链路里，CLI 负责生成入口和代码骨架，模块代码负责声明页面和返回数据，宿主负责渲染和交互执行。

## 页面导航清单

```yaml
ui_extension:
  pages:
    - id: dashboard
      label: Dashboard
      icon: 📄
    - id: accounts
      label: Accounts
      icon: 📄
```

`id` 就是页面标识，也是 `ui.declare_page(page_id=...)` 的目标值。清单里不再出现 `entry`。

## 最小页面声明

```python
from crawler4j_sdk import TaskContext


def declare_ui(context: TaskContext):
    if not context.tools or not context.tools.has_tool("ui.declare_page"):
        return None

    context.tools.call(
        "ui.declare_page",
        page_id="dashboard",
        schema={
            "type": "Page",
            "title": "Dashboard",
            "load_handler": "load_dashboard_page",
            "layout": {"direction": "column", "gap": 16},
            "children": [
                {
                    "type": "Section",
                    "variant": "plain",
                    "children": [
                        {"type": "Text", "style": "title", "text": "Dashboard"},
                        {"type": "Button", "label": "刷新", "action": {"type": "reload"}},
                    ],
                }
            ],
        },
    )
    return None


def load_dashboard_page(
    context: TaskContext,
    page_id: str,
    params: dict | None = None,
) -> dict:
    del page_id, params
    return {"summary": "Dashboard 页面已加载"}
```

## `DataTable` 现在怎么用

### 方式一：直接绑定 `load_handler` 返回的数据

```python
def build_accounts_page_schema() -> dict:
    return {
        "type": "Page",
        "title": "账号列表",
        "load_handler": "load_accounts_page",
        "children": [
            {
                "type": "DataTable",
                "table_id": "accounts",
                "title": "账号列表",
                "columns": [
                    {"key": "account_id", "label": "账号", "type": "text"},
                    {"key": "status", "label": "状态", "type": "badge"},
                ],
                "data_source": {"type": "binding", "binding": "rows"},
                "features": {
                    "search": {"enabled": True, "placeholder": "搜索账号"},
                    "sort": {"enabled": True, "default": [{"field": "account_id", "direction": "asc"}]},
                    "pagination": {"enabled": True, "page_size": 20},
                },
            }
        ],
    }


def load_accounts_page(context: TaskContext, page_id: str, params: dict | None = None) -> dict:
    del page_id, params
    rows = []
    if context.tools and context.tools.has_tool("db.list_records"):
        rows = context.tools.call("db.list_records", dataset="accounts") or []
    return {"rows": rows}
```

### 方式二：让表格自己向模块查询

```python
def build_billing_page_schema() -> dict:
    return {
        "type": "Page",
        "title": "计费统计",
        "load_handler": "load_billing_page",
        "children": [
            {
                "type": "DataTable",
                "table_id": "billing_stats",
                "title": "计费统计",
                "columns": [
                    {"key": "execution_date", "label": "执行日期", "type": "text"},
                    {"key": "total_count", "label": "数量", "type": "int"},
                    {"key": "total_amount", "label": "金额", "type": "number"},
                ],
                "data_source": {"type": "query_handler", "handler": "query_billing_stats_table"},
            }
        ],
    }


def load_billing_page(context: TaskContext, page_id: str, params: dict | None = None) -> dict:
    del context, page_id, params
    return {}


def query_billing_stats_table(
    context: TaskContext,
    table_id: str,
    query: dict,
    params: dict | None = None,
) -> dict:
    del table_id, params
    result = context.tools.call(
        "db.query_view",
        view_id="billing_stats",
        filters=query.get("filters") or {},
        sort=query.get("sort") or [],
        limit=query.get("page_size", 20),
        offset=max(query.get("page", 1) - 1, 0) * query.get("page_size", 20),
    )
    return {
        "rows": result.get("rows", []),
        "total": result.get("total", 0),
        "page": query.get("page", 1),
        "page_size": query.get("page_size", 20),
        "sort": query.get("sort", []),
    }
```

内联表格 `query_handler` 的正式签名是：

```python
(context, table_id, query, params=None)
```

## 页面动作与表格行跳转

当前正式动作只有两类：

- `reload`
- `open_page`

按钮示例：

```python
{
    "type": "Button",
    "label": "查看账号明细",
    "action": {
        "type": "open_page",
        "page_id": "account_detail",
        "params": {
            "account_id": {"binding": "selected_account_id"},
        },
    },
}
```

表格行点击示例：

```python
{
    "type": "DataTable",
    "table_id": "accounts",
    "columns": [...],
    "data_source": {"type": "binding", "binding": "rows"},
    "row_action": {
        "type": "open_page",
        "page_id": "account_detail",
        "params": {
            "account_id": {"binding": "account_id"},
        },
    },
}
```

目标页会通过 `load_handler(context, page_id, params=None)` 收到这些参数。

## 页面与数据的职责分工

### 宿主负责

- schema 校验
- 页面路由与刷新
- 统一渲染 `Page / Section / Text / Button / DataTable`
- 表格的搜索、排序、分页和点击事件分发
- 通用 UI 错误提示和空态

### 模块负责

- 页面 schema 组装
- 页面加载数据
- 表格查询逻辑
- 业务动作
- 数据资源声明、数据库视图声明、审计事件读写

### Core 其它能力负责

- `db.declare_data_resource`
- `db.list_records` / `db.replace_records`
- `db.declare_db_view` / `db.query_view`
- `db.append_event` / `db.query_events`

## `check full` 当前会直接校验

- `ui_extension.pages[]` 中的页面 `id` 是否合法
- `declare_ui()` 是否为同步函数
- Hosted UI 是否真的通过 `ui.declare_page` 注册
- `load_handler` 是否存在、为同步函数且签名兼容 `(context, page_id, params)`
- 内联表格 `query_handler` 若声明，是否存在、为同步函数且签名兼容 `(context, table_id, query, params)`
- 顶层 `ui/` 目录是否已清理；当前会被视为旧结构残留并直接阻断

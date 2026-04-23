# UI 与数据表

当前正式 UI 协议已经完全切到宿主扫描模式：

- `module.yaml.ui_extension.pages[]` 只声明导航元信息
- `pages/*.py` 或 `pages/<group>/*.py` 直接导出 `PAGE: PageSpec`
- Core 读取 `PAGE.schema` 并渲染
- 页面数据和动作都走页面 handler

模块不再声明 UI 运行入口，宿主也不再让模块自己装配页面。

## 页面入口放哪

页面入口分两部分：

1. `module.yaml.ui_extension.pages[]`
2. `pages/<page>.py` 或 `pages/<group>/<file>.py`

清单只放导航元信息：

```yaml
ui_extension:
  pages:
    - id: dashboard
      label: Dashboard
      icon: 📄
    - id: accounts
      label: Accounts
      icon: 👤
```

页面文件放真实 schema 和 handler：

```python
from crawler4j_contracts import PageSpec, TaskContext

PAGE = PageSpec(
    id="dashboard",
    label="Dashboard",
    icon="📄",
    schema={
        "type": "Page",
        "title": "Dashboard",
        "load_handler": "load_dashboard_page",
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

## 接入主线

标准顺序：

1. `uv run crawler4j page create dashboard`
2. 如果某个菜单下有多个文件，可以用 `uv run crawler4j page create account_detail --group account`
3. CLI 更新 `module.yaml.ui_extension.pages[]` 和对应页面文件，例如 `pages/dashboard.py` 或 `pages/account/detail.py`
4. 你补 `PAGE.schema` 和 handler
5. `uv run crawler4j check full`
6. 用 DevLink 到宿主里验证

分组目录只影响源码组织，不影响页面路由：

- `page_id` 仍然保持扁平，例如 `account_detail`
- `open_page.page_id` 继续写扁平 ID
- 左侧菜单层级仍然只看 `module.yaml.ui_extension.pages[]`

## 页面可以做什么

当前正式组件面固定为：

- `Page`
- `Section`
- `Text`
- `Button`
- `DataTable`

宿主负责渲染和交互分发；模块负责返回页面数据、实现查询和业务动作。

## `DataTable` 的 3 种数据源

### 1. `binding`

从 `load_handler` 返回值里取字段：

```python
from crawler4j_contracts import PageSpec, TaskContext

PAGE = PageSpec(
    id="accounts",
    label="账号列表",
    icon="👤",
    schema={
        "type": "Page",
        "title": "账号列表",
        "load_handler": "load_accounts_page",
        "children": [
            {
                "type": "DataTable",
                "table_id": "accounts",
                "columns": [
                    {"key": "account_id", "label": "账号", "type": "text"},
                    {"key": "status", "label": "状态", "type": "badge"},
                ],
                "data_source": {"type": "binding", "binding": "rows"},
            }
        ],
    },
)


def load_accounts_page(
    context: TaskContext,
    page_id: str,
    params: dict | None = None,
) -> dict:
    del page_id, params
    rows = context.tools.call("db.list_records", resource="accounts") or []
    return {"rows": rows}
```

### 2. `rows`

直接把静态或即时计算结果内联在 schema 里。适合很小的只读表。

### 3. `query_handler`

把搜索、排序、分页交给模块：

```python
def query_billing_stats_table(
    context: TaskContext,
    table_id: str,
    query: dict,
    params: dict | None = None,
) -> dict:
    del table_id, params
    page_size = query.get("page_size", 20)
    page = query.get("page", 1)
    result = context.tools.call(
        "db.query_view",
        view_id="billing_stats",
        filters=query.get("filters") or {},
        sort=query.get("sort") or [],
        limit=page_size,
        offset=max(page - 1, 0) * page_size,
    )
    return {
        "rows": result.get("rows", []),
        "total": result.get("total", 0),
        "page": page,
        "page_size": page_size,
    }
```

正式签名固定为：

```python
(context, table_id, query, params=None)
```

## 页面动作

当前正式动作只有两类：

- `reload`
- `open_page`

表格行跳转示例：

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

## 推荐落点

| 需求 | 推荐做法 |
|---|---|
| Dashboard、概览页 | `Page + Text + Button + DataTable` |
| 快照列表 | `db.list_records` + `binding` |
| 统计查询 | `db.query_view` + `query_handler` |
| 明细实体表 | `module.yaml.data.resources[]` + `db.get_record/db.list_records/db.replace_records` |
| 历史时间线 | `db.query_events` 后自行组装页面 |

## 职责分工

宿主负责：

- schema 校验
- 页面路由
- 页面刷新
- 统一渲染 `Page / Section / Text / Button / DataTable`
- 搜索、排序、分页交互分发

模块负责：

- `PAGE.schema`
- `load_handler`
- `query_handler`
- 页面业务动作
- `module.yaml.data` / `data/sql` / `data/seeds` 的声明与维护
- 数据记录、命名查询、数据库视图和审计事件的使用

## `check full` 会校验什么

- `ui_extension.pages[]` 是否有效
- `PAGE.id` 是否与清单对齐
- `PAGE.schema` 顶层是否是 `Page`
- `load_handler` 是否存在且签名兼容
- `query_handler` 是否存在且签名兼容

如果页面显示不对，优先查 `pages/*.py`、`pages/<group>/*.py`，不要回退去找已经删除的旧 UI 壳。

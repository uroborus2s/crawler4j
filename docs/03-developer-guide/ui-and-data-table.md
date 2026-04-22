# UI 与数据表

这一页只讲模块开发者当前真正会用到的两种 UI 形态：

1. hosted page
2. 宿主管理的 `core:data_table`

正式 UI 契约已经收口到这两条路径，不再让模块直接导出 `PyQt6` 页面。

## 什么时候选哪种 UI

| 需求 | 选什么 |
|---|---|
| 展示 KPI、说明文本、只读表格、操作按钮 | hosted page |
| 维护一批结构化快照记录 | `core:data_table` |
| 既要概览页，又要结构化记录列表 | 两者都用 |
| append-only 历史时间线 | 审计事件 + hosted page，不要直接塞进 `core:data_table` |

先把宿主里的落点心智模型记死：

- `ui_extension.pages[].entry = core:page:<page_id>` 对应宿主页
- `ui_extension.pages[].entry = core:data_table:<view_id>` 对应托管数据表页
- 两者都通过 `module_runtime.py -> declare_ui()` 声明

## 写 hosted page

先生成骨架：

```bash
uv run crawler4j page create dashboard
uv run crawler4j check structure
```

这会做两件事：

- 把 `dashboard` 写入 `module.yaml.ui_extension.pages`
- 在 `module_runtime.py` 追加 `build_dashboard_page_schema()`、`load_dashboard_page()` 和 `_declare_dashboard_page()`

### 最小页面清单写法

```yaml
ui_extension:
  pages:
    - id: dashboard
      label: Dashboard
      icon: 📄
      entry: core:page:dashboard
```

### 最小页面声明写法

```python
from crawler4j_sdk import TaskContext


def declare_ui(context: TaskContext):
    _declare_dashboard_page(context)
    return None


def _declare_dashboard_page(context: TaskContext):
    if not context.tools or not context.tools.has_tool("ui.declare_page"):
        return None

    return context.tools.call(
        "ui.declare_page",
        page_id="dashboard",
        schema=build_dashboard_page_schema(),
    )


def build_dashboard_page_schema() -> dict:
    return {
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
                    {"type": "Text", "style": "subtitle", "text": "今日概览"},
                    {"type": "Button", "label": "刷新", "action": {"type": "reload"}},
                ],
            },
            {
                "type": "Section",
                "title": "页面状态",
                "variant": "card",
                "children": [
                    {"type": "Text", "style": "body", "binding": "summary"},
                    {"type": "Text", "style": "meta", "binding": "updated_at"},
                ],
            },
        ],
    }


def load_dashboard_page(
    context: TaskContext,
    page_id: str,
    params: dict | None = None,
) -> dict:
    del page_id, params
    return {
        "summary": "Dashboard 页面已加载",
        "updated_at": "待接入真实数据",
    }
```

### hosted page 开发纪律

- `declare_ui()` 必须是同步函数
- `load_*_page()` 必须是同步函数
- `schema.type` 必须是 `Page`
- `load_handler` 必须指向 `module_runtime.py` 里真实存在的同步函数
- 页面数据返回纯结构化对象，不直接做宿主渲染

## 用托管数据表

`core:data_table` 只适合简单记录列表和轻量 CRUD。

适合：

- 小型业务记录维护
- 通用表格展示
- 简单新增、编辑、删除
- 配合锁显示“占用中”

不适合：

- 多步骤向导
- 复杂审批流
- 大量联动字段
- append-only 审计历史

## `core:data_table` 和审计事件怎么分工

| 你要保留什么 | 正确落点 |
|---|---|
| 当前账号列表、酒店列表这种“现在长什么样”的数据 | `core:data_table` + `db.list_records` / `db.replace_records` |
| 登录尝试、状态迁移、人工确认这种“发生过什么”的历史 | `db.append_event` / `db.query_events` |
| 既要当前列表又要历史轨迹 | 两条都用，不要把历史事件混进当前 dataset |

`core:data_table` 的 schema、编辑弹窗和 CRUD 语义都默认你维护的是当前快照。它不是审计日志表。

## 新人照抄版

执行完 `uv run crawler4j data-table create hotels` 之后，你通常只需要改两个位置：

1. `module.yaml.ui_extension.pages`
2. `module_runtime.py`

正确顺序只有 4 步：

1. 跑 `data-table create`，把入口写进 `module.yaml.ui_extension.pages`
2. 在 `module_runtime.py` 改 CLI 生成的同步 helper，必要时补同步 handler
3. 确认根 `__init__.py` 仍是 SDK 托管薄壳，不要手改坏 `__getattr__`
4. 回到宿主模块详情页，点数据表入口和 `刷新` 验证

## 第一步：注册入口

```bash
uv run crawler4j data-table create hotels
uv run crawler4j check structure
```

`module.yaml` 会出现：

```yaml
ui_extension:
  pages:
    - id: hotels
      icon: 📋
      label: Hotels
      entry: core:data_table:hotels
```

## 第二步：在 `module_runtime.py` 改同步 hook

当前宿主和 CLI 的真实调用链是：

1. 打开模块详情页里的 `core:data_table:hotels`
2. 宿主同步调用模块本地 `declare_ui(context)`
3. `declare_ui()` 内部调用 `context.tools.call("ui.declare_data_table", ...)`
4. 如果 schema 声明了 `create_handler` / `update_handler`
5. 宿主继续同步调用对应本地 hook

所以这里有 4 条硬约束：

1. `declare_ui()` 必须是同步函数
2. `create_handler` / `update_handler` 必须是同步函数
3. handler 名必须和 schema 里的字符串完全一致
4. 标准脚手架依赖根 `__init__.py` 的 `__getattr__` 自动转发，所以不要手改坏根薄壳

### 推荐写法

```python
from crawler4j_sdk import TaskContext


def _declare_hotels_table(context: TaskContext):
    if not context.tools or not context.tools.has_tool("ui.declare_data_table"):
        return None

    return context.tools.call(
        "ui.declare_data_table",
        view_id="hotels",
        schema={
            "title": "酒店列表",
            "dataset": "hotels",
            "primary_key": "id",
            "display_fields": ["name", "city", "status"],
            "create_fields": ["name", "city", "status"],
            "update_fields": ["status"],
            "create_handler": "create_hotel_from_ui",
            "update_handler": "update_hotel_from_ui",
            "columns": [
                {"key": "id", "label": "ID", "visible": False},
                {"key": "name", "label": "酒店名", "required": True},
                {"key": "city", "label": "城市", "required": True},
                {
                    "key": "status",
                    "label": "状态",
                    "required": True,
                    "type": "select",
                    "options": ["new", "active", "blocked"],
                },
            ],
        },
    )


def create_hotel_from_ui(context: TaskContext, payload: dict):
    rows = context.tools.call("db.list_records", dataset="hotels") or []
    rows.append(
        {
            "id": payload["name"].lower(),
            "name": payload["name"],
            "city": payload["city"],
            "status": payload["status"],
        }
    )
    return context.tools.call("db.replace_records", dataset="hotels", records=rows)


def update_hotel_from_ui(context: TaskContext, pk_value: str, payload: dict):
    rows = context.tools.call("db.list_records", dataset="hotels") or []
    for row in rows:
        if row.get("id") == pk_value:
            row["status"] = payload["status"]
            break
    return context.tools.call("db.replace_records", dataset="hotels", records=rows)
```

如果新增 / 编辑成功后还要留下操作历史，单独追加一条审计事件即可；不要把历史继续塞回 `hotels` 这个快照 dataset。

## 调试顺序

如果页面或数据表没出现，按这个顺序查：

1. `module.yaml.ui_extension.pages`
2. `module_runtime.py` 里的 `declare_ui()`
3. `crawler4j check full`
4. 宿主里点页面刷新

`check full` 当前会直接校验：

- `ui_extension.pages[]` 格式
- `declare_ui()` 是否为同步函数
- hosted page 是否真的调用了 `ui.declare_page`
- 数据表是否真的调用了 `ui.declare_data_table`
- hosted page 的 `load_handler` 是否存在且为同步函数
- `declare_ui()` 是否误写 `db.append_event`

## 额外提醒

- `lock_key` 只用于 Core 临时锁，不要再和业务占用列一起声明
- `data-table create` 会注册入口并生成最小 helper，但 schema 细节仍要你自己改
- hosted page 的布局和组件能力以宿主 V1 为准，不要自行发明扩展字段解释器

下一步建议看 [模块结构](module-structure.md) 和 [调试模块](debugging.md)。

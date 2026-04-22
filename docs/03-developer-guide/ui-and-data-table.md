# UI 与数据表

模块在宿主中的正式 UI 已收口到 Hosted UI V1。模块只声明页面和数据表 schema，由宿主统一渲染；模块不再导出 `PyQt6` 页面类，也不再让宿主执行模块侧 UI 组件代码。

当前只有两类正式入口：

- `core:page:<page_id>`：宿主页，用于概览、说明、KPI、只读表格和按钮操作
- `core:data_table:<view_id>`：宿主管理的数据表页，用于当前快照数据的轻量 CRUD

这两类入口都通过 `module_runtime.py` 中的同步 `declare_ui()` 注册，并由 `module.yaml.ui_extension.pages[]` 暴露给宿主导航。

## 先确定落点

| 需求 | 正式落点 |
|---|---|
| Dashboard、说明页、操作入口、只读概览 | Hosted UI V1 (`core:page:<page_id>`) |
| 当前账号列表、酒店列表、开关清单这类快照型记录维护 | `core:data_table:<view_id>` |
| 历史时间线、操作留痕、状态流转 | `db.append_event` / `db.query_events`，必要时再用 Hosted UI 展示 |
| 既要概览页又要记录页 | 同时声明 `core:page:*` 和 `core:data_table:*` |

一个硬边界必须记住：`core:data_table` 只服务“当前是什么”的快照数据，不承载“发生过什么”的 append-only 历史。

## 一条接入主线

模块 UI 的标准开发顺序固定如下：

1. 用 SDK CLI 生成入口骨架：
   - `uv run crawler4j page create dashboard`
   - `uv run crawler4j data-table create hotels`
2. CLI 会同时更新两处：
   - `module.yaml.ui_extension.pages[]`
   - `module_runtime.py`
3. 你补完 schema、加载函数或 CRUD handler
4. 执行 `uv run crawler4j check full`
5. 用 DevLink 接入宿主验证声明是否能被宿主重放：
   - `core:data_table` 页可直接点宿主 `刷新`
   - `core:page` 需要重新进入页面，或在 schema 里显式声明 `reload` 按钮

这条链路里，CLI 负责生成入口和托管骨架，模块代码负责声明业务 schema，宿主负责渲染和交互执行。

## Hosted UI V1

Hosted UI V1 是模块在宿主里的正式页面形态。入口写在 `module.yaml`，页面 schema 写在 `module_runtime.py`，页面数据由同步加载函数返回结构化字典。

### 入口清单

```yaml
ui_extension:
  pages:
    - id: dashboard
      label: Dashboard
      icon: 📄
      entry: core:page:dashboard
```

### 最小声明

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


def load_dashboard_page(
    context: TaskContext,
    page_id: str,
    params: dict | None = None,
) -> dict:
    del page_id, params
    return {"summary": "Dashboard 页面已加载"}
```

### Hosted UI V1 约束

- `declare_ui()` 必须是同步函数。
- `declare_ui()` 必须可重放。宿主会在页面重新进入或数据表刷新时再次调用它。
- `declare_ui()` 允许读取 schema、快照数据和审计事件，但不要在这里做 `db.append_event` 之类会留下副作用的写入。
- `ui.declare_page` 的 `page_id` 要与 `core:page:<page_id>` 对齐。
- 页面 schema 的顶层 `type` 必须是 `Page`。
- `load_handler` 必须指向 `module_runtime.py` 中真实存在的同步函数。
- 页面数据返回纯结构化对象，模块不直接参与宿主渲染。
- 页面动作按宿主 V1 约束执行，当前正式动作以 `reload`、`open_page` 为主。

如果只是确认页面 schema 是否真的被登记，可以用 `ctx.tools.call("ui.get_page", page_id="dashboard")` 做诊断。

## 宿主管理的数据表

`core:data_table` 用于管理当前快照数据。SDK CLI 会同时注册页面入口和 `module_runtime.py` helper，模块开发者只需要把 schema 和 handler 补成真实业务版本。

### 入口清单

```yaml
ui_extension:
  pages:
    - id: hotels
      label: Hotels
      icon: 📋
      entry: core:data_table:hotels
```

### 最小声明

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
                    "type": "select",
                    "required": True,
                    "options": ["new", "active", "blocked"],
                },
            ],
        },
    )
```

### 数据表约束

- `view_id`、`dataset` 和 `core:data_table:<view_id>` 必须保持同名。
- `declare_ui()`、`create_handler`、`update_handler` 都必须是同步函数。
- `declare_ui()` 会在数据表页刷新时被宿主重新执行，因此必须保持可重放，不要在里面写审计事件。
- handler 名必须与 schema 里的字符串完全一致。
- `db.list_records` / `db.replace_records` 维护的是整份当前快照，不是增量 patch。
- 数据表页刷新时，宿主会重放一次 `declare_ui()`，这也是验证最新 schema 的正式刷新路径。

如果根 `__init__.py` 里的 SDK 托管薄壳被改坏，数据表 handler 即使存在也不会被宿主正确定位。因此模块根薄壳不要手工改写。

## 快照数据与审计历史的分工

Hosted UI V1 里最容易混淆的是“当前列表”和“历史事件”。

| 要保留的内容 | 正式入口 |
|---|---|
| 当前账号列表、当前酒店状态、当前结果集 | `db.list_records` / `db.replace_records` + `core:data_table` |
| 登录尝试、人工确认、状态迁移、操作轨迹 | `db.append_event` / `db.query_events` |
| 页面上的统计总览、最近事件摘要 | Hosted UI 页面读取快照数据和审计事件后自行组合展示 |

不要把审计事件继续塞回快照 dataset，也不要把历史时间线直接接到通用 CRUD 数据表上。

## 开发与验收口径

UI 开发完成后，至少按下面顺序验一遍：

1. `uv run crawler4j check full`
2. 用 DevLink 把模块接进宿主
3. 打开模块详情页或数据表页
4. 验证宿主是否重放 `declare_ui()`：
   - `core:data_table` 页直接点宿主 `刷新`
   - `core:page` 重新进入页面，或点击 schema 里显式声明的 `reload` 按钮
5. 观察页面渲染、按钮动作、CRUD handler 和日志是否符合预期

`check full` 当前会直接校验：

- `ui_extension.pages[]` 的入口格式
- `declare_ui()` 是否为同步函数
- `declare_ui()` 是否保持无副作用声明路径；当前会拒绝把 `db.append_event` 这类审计写入放进 `declare_ui()`
- Hosted UI 是否真的通过 `ui.declare_page` 注册
- 数据表是否真的通过 `ui.declare_data_table` 注册
- `load_handler` 是否存在、为同步函数且签名兼容运行时调用 `(context, page_id, params)`
- 数据表 `create_handler` / `update_handler` 若声明，是否存在、为同步函数且签名兼容运行时调用 `(context, payload)` / `(context, row_id, payload)`
- 顶层 `ui/` 目录是否已清理；当前会被视为旧结构残留并直接阻断

开发态 UI 验收走 DevLink；正式交付仍然走 ZIP 安装包，不走源码目录。

# UI 与数据表

这一页只讲模块开发者真正会用到的两种 UI 形态:

1. 代码型页面
2. 宿主管理的 `core:data_table`

## 什么时候选哪种 UI

| 需求 | 选什么 |
|---|---|
| 只是展示和编辑一批结构化记录 | `core:data_table` |
| 需要复杂交互、业务面板、自定义组件布局 | 代码型页面 |
| 想展示按条件查询出来的审计历史时间线 | 代码型页面 |
| 既要业务页，又要结构化数据列表 | 两者都可以用 |

先把宿主里的落点心智模型记死:

- `ui_extension.entry` 对应模块详情页顶部的代码型页面
- `ui_extension.detail_menu` 对应详情页侧边或菜单里的数据表入口
- 两者都可以共存，但它们不是同一个入口

## 写代码型页面

先生成页面:

```bash
uv run crawler4j page create dashboard
uv run crawler4j check structure
```

这会做三件事:

- 生成 `ui/dashboard.py`
- 自动在 `ui/__init__.py` 里导出页面类
- 把 `module.yaml.ui_extension.entry` 写成 `ui:DashboardPage`

### 最小页面写法

```python
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget
from crawler4j_sdk import TaskContext


class DashboardPage(QWidget):
    def __init__(self, ctx: TaskContext, parent=None):
        super().__init__(parent)
        self.ctx = ctx

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("酒店模块"))

        btn = QPushButton("刷新数据")
        btn.clicked.connect(self.on_refresh)
        layout.addWidget(btn)

    def on_refresh(self):
        self.ctx.logger.info("UI 请求刷新数据")
```

### 页面开发纪律

- 页面类签名保持 `__init__(self, ctx: TaskContext, parent=None)`
- 页面里仍然通过 `ctx.tools.call(...)` 访问宿主能力
- 页面只做界面交互和轻量业务动作
- 如果页面逻辑已经需要大量状态机、服务层、仓储层，说明页面职责已经写重了

## 用托管数据表

`core:data_table` 只适合简单记录列表和轻量 CRUD。

适合:

- 小型业务记录维护
- 通用表格展示
- 简单新增、编辑、删除
- 配合锁显示“占用中”

不适合:

- 多步骤向导
- 复杂审批流
- 大量联动字段
- 跨页面异步编排
- append-only 审计历史

## `core:data_table` 和审计事件怎么分工

| 你要保留什么 | 正确落点 |
|---|---|
| 当前酒店列表、账号列表这类“现在长什么样”的数据 | `core:data_table` + `db.list_records` / `db.replace_records` |
| 登录尝试、状态迁移、人工确认这类“发生过什么”的历史 | `db.append_event` / `db.query_events` |
| 既要当前列表又要历史轨迹 | 两条都用，不要把历史事件行混进当前 dataset |

`core:data_table` 的 schema、编辑弹窗和 CRUD 语义都默认你维护的是当前快照。它不是审计日志表，也不会替你管理 append-only 历史。

## 新人照抄版

执行完 `uv run crawler4j data-table create hotels` 之后，你通常只需要改一个文件:

1. `module_runtime.py`

正确顺序只有 4 步:

1. 跑 `data-table create`，把入口写进 `module.yaml.ui_extension.detail_menu`
2. 在 `module_runtime.py` 改 CLI 生成的同步 helper，必要时补同步 handler
3. 确认根 `__init__.py` 仍是 SDK 托管薄壳，不要手改坏 `__getattr__`
4. 回到宿主模块详情页，点数据表入口和 `刷新` 验证

如果你做了别的事，比如再建 `services/`、再建 `repository/`、再写一套 UI schema 文件，通常都走偏了。

## 第一步: 注册入口

```bash
uv run crawler4j data-table create hotels
uv run crawler4j check structure
```

`module.yaml` 会出现:

```yaml
ui_extension:
  detail_menu:
    - id: hotels
      icon: 📋
      label: Hotels
      entry: core:data_table:hotels
```

## 第二步: 在 `module_runtime.py` 改同步 hook

当前宿主和 CLI 的真实调用链是:

1. 打开模块详情页里的 `core:data_table:hotels`
2. 宿主同步调用模块本地 `declare_ui(ctx)`
3. `declare_ui` 内部调用 `ctx.tools.call("ui.declare_data_table", ...)`
4. 如果 schema 声明了 `create_handler` / `update_handler`
5. 宿主继续同步调用对应本地 hook

所以这里有 4 条硬约束:

1. `declare_ui` 必须是同步函数
2. `create_handler` / `update_handler` 必须是同步函数
3. handler 名必须和 schema 里的字符串完全一致
4. 标准脚手架依赖根 `__init__.py` 的 `__getattr__` 自动转发，所以不要手改坏根薄壳

补一条最容易抄错的签名规则:

- `create_handler(ctx, payload)` 只收 `payload`
- `update_handler(ctx, pk_value, payload)` 会先收到主键值，再收到编辑后的 `payload`

### 推荐写法

```python
from crawler4j_sdk import TaskContext


def declare_ui(ctx: TaskContext):
    if not ctx.tools or not ctx.tools.has_tool("ui.declare_data_table"):
        return None

    return ctx.tools.call(
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


def create_hotel_from_ui(ctx: TaskContext, payload: dict):
    rows = ctx.tools.call("db.list_records", dataset="hotels") or []
    rows.append(
        {
            "id": payload["name"].lower(),
            "name": payload["name"],
            "city": payload["city"],
            "status": payload["status"],
        }
    )
    return ctx.tools.call("db.replace_records", dataset="hotels", records=rows)


def update_hotel_from_ui(ctx: TaskContext, pk_value: str, payload: dict):
    rows = ctx.tools.call("db.list_records", dataset="hotels") or []
    for row in rows:
        if row.get("id") == pk_value:
            row["status"] = payload["status"]
            break
    return ctx.tools.call("db.replace_records", dataset="hotels", records=rows)
```

如果新增/编辑成功后还要留下操作历史，单独追加一条审计事件即可；不要把“谁改过、改了几次”继续塞回 `hotels` 这个快照 dataset。

## 第三步: 不要手改根 `__init__.py`

标准 CLI 脚手架已经会把 `module_runtime.py` 里的 hook 透传到根模块。

这一步真正要确认的是:

- 根 `__init__.py` 仍然是 SDK 托管薄壳
- 没有人手工删掉 `__getattr__`
- 你没有把数据表 hook 又搬回根入口

## 第四步: 在 UI 里验证

验证顺序不要乱:

1. 打开 `📦 模块管理`
2. 进入目标模块详情页
3. 点击详情菜单里对应的数据表入口
4. 点击页面上的 `刷新`
5. 确认表头、字段、按钮和 schema 对齐
6. 点 `新增` / `编辑`，确认 handler 真正生效

如果入口有了但页面还是空的，先查这 4 件事:

1. `module_runtime.py` 里是否存在 `declare_ui`
2. `declare_ui` 是否是同步函数
3. `view_id`、`dataset`、`module.yaml.ui_extension.detail_menu[].id` 是否完全一致
4. `create_handler` / `update_handler` 名字是否完全一致

## 数据表排障最短分叉清单

不要在空白页前面瞎猜，直接按现象分叉:

1. 看不到菜单入口:
   先查 `module.yaml.ui_extension.detail_menu`
2. 点进去是空白页:
   先查 `declare_ui` 是否存在且为同步函数
3. 表头或字段不对:
   先查 `ui.declare_data_table` 里的 schema
4. `新增` / `编辑` 按钮没反应:
   先查 `create_handler` / `update_handler` 名字和签名
5. 改完代码没生效:
   回到模块详情页重新打开入口，再点 `刷新`

## 数据表 schema 的硬约束

schema 顶层只允许这些字段:

- `title`
- `dataset`
- `primary_key`
- `lock_scope`
- `lock_key`
- `display_fields`
- `create_fields`
- `update_fields`
- `create_handler`
- `update_handler`
- `columns`

列类型只允许:

- `text`
- `number`
- `int`
- `bool`
- `select`

额外硬约束:

- `dataset` 必须和 `view_id` 完全一致
- `view_id`、`dataset`、handler 名都必须是 `snake_case`
- `select` 列必须提供非空 `options`
- `options` 只能给 `select` 列使用
- `lock_key` 只用于 Core 管理的临时锁；它会让宿主按 KV 锁状态追加一列通用“占用中”，并在删除/改主键时做锁保护
- 如果模块已经自己维护 `occupied` / `occupied_label` 这类业务占用字段，就不要再声明 `lock_key`
- 当前 Core 已显式拒绝“`lock_key` + 业务占用列”同时声明；`crawler4j check full` 也会提前报错

## 新手最容易误会的点

- `data-table create` 会注册入口并生成一个最小 helper，但 schema 细节仍要你自己改
- schema 必须通过 `ui.declare_data_table` 声明，不能自己写到别的文件里
- `dataset` 必须和 `view_id` 一致
- `lock_key` 不是“业务占用中”开关，它表示 Core 的临时锁键
- 当前本地数据表 hook 是同步调用链路，写成 `async def` 会直接失败

想继续调试，接着看 [调试模块](debugging.md)。

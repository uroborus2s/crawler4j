# Core 能力参考

模块运行时不应该直连宿主内部对象。正式边界只有一层：

```python
ctx.tools.call(...)
```

配套接口也只有三项：

- `ctx.tools.has_tool(name)`
- `ctx.tools.list_tools()`
- `ctx.tools.call(name, **kwargs)`

如果你绕过这层边界，模块就不再是宿主管理的轻量应用，而是在直接绑定宿主内部实现。

## 能力全景

| 类别 | 工具名 | 是否异步 | 主要用途 |
|---|---|---|---|
| Hosted UI V1 | `ui.declare_page` `ui.get_page` | 否 | 声明和读取宿主页 schema |
| 宿主管理数据表 | `ui.declare_data_table` `ui.get_data_table` | 否 | 声明和读取数据表 schema |
| 快照数据 | `db.list_records` `db.replace_records` | 否 | 读取和全量覆盖当前记录集 |
| 审计事件 | `db.append_event` `db.query_events` | 否 | 记录和查询 append-only 历史 |
| 轻状态与锁 | `db.get_state` `db.set_state` `db.exists_state` `db.acquire_lock` `db.release_lock` `db.is_locked` | 否 | 保存轻量状态、游标、会话和互斥锁 |
| 代理与环境 | `ip_pool.pick_proxy` `env.set_proxy` `env.bind_resource_pool` `env.mark_resource_pool_eligible` `env.mark_resource_pool_ineligible` `env.remove_resource_pool` `env.replace_resource_pool_snapshot` | `env.*` 为异步 | 代理选择、环境代理设置、固定环境池维护 |
| 验证码 | `captcha.match_slider` `captcha.match_click_targets` | 否 | 图像识别类验证码辅助 |

## Hosted UI V1

Hosted UI V1 是模块在宿主中的正式 UI 能力面。模块通过 schema 声明页面或数据表，宿主负责渲染和执行。

### `ui.declare_page`

```python
ctx.tools.call(
    "ui.declare_page",
    page_id="dashboard",
    schema={...},
)
```

正式约束：

- `page_id` 必须是 `snake_case`
- `module.yaml.ui_extension.pages[]` 中必须存在 `core:page:<page_id>`
- `declare_ui()` 必须是同步函数
- `load_handler` 必须指向 `module_runtime.py` 中真实存在的同步函数
- schema 顶层必须是 `Page`

### `ui.get_page`

```python
schema = ctx.tools.call("ui.get_page", page_id="dashboard")
```

适用场景：

- 确认页面 schema 是否已被宿主登记
- 调试页面刷新后是否拿到了最新声明

### `ui.declare_data_table`

```python
ctx.tools.call(
    "ui.declare_data_table",
    view_id="hotels",
    schema={...},
)
```

正式约束：

- `view_id` 必须是 `snake_case`
- `module.yaml.ui_extension.pages[]` 中必须存在 `core:data_table:<view_id>`
- `dataset` 必须和 `view_id` 完全一致
- `create_handler` / `update_handler` 必须是同步函数
- handler 名必须与 `module_runtime.py` 中的真实函数同名
- `core:data_table` 只服务快照型 dataset，不承载 append-only 历史

schema 顶层允许的核心字段：

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

列定义允许的核心字段：

- `key`
- `label`
- `visible`
- `required`
- `type`
- `options`
- `default`

列类型当前以：

- `text`
- `number`
- `int`
- `bool`
- `select`

为正式范围。

### `ui.get_data_table`

```python
schema = ctx.tools.call("ui.get_data_table", view_id="hotels")
```

适用场景：

- 确认数据表 schema 是否真的注册成功
- 宿主页或调试逻辑里读取当前持久化的数据表声明

宿主刷新数据表页时，会重新调用一次 `declare_ui()`。但要注意：

- `core:data_table` 页自带宿主级 `刷新`
- `core:page` 没有统一页头刷新按钮；只有重新进入页面，或页面 schema 显式声明 `reload` 按钮时，宿主才会重放声明和加载链

## 快照数据与审计事件

数据能力分成两条正式通道：

- 快照数据：`db.list_records` / `db.replace_records`
- 审计事件：`db.append_event` / `db.query_events`

写 Hosted UI 时再补一条硬约束：

- `declare_ui()` 必须是可重放的声明函数
- 允许在 `declare_ui()` 里读取快照和事件来组装 schema
- 不要在 `declare_ui()` 里调用 `db.append_event` 之类会留下副作用的写入；这类逻辑应放到 `load_handler`、数据表 handler、workflow 或 task

### `db.list_records`

```python
rows = ctx.tools.call("db.list_records", dataset="hotels")
```

适合：

- 读取当前账号列表、酒店列表、状态清单
- 给 Hosted UI V1 或 workflow 提供当前记录集

不适合：

- 读取宿主持久配置
- 读取一次性运行参数

### `db.replace_records`

```python
ok = ctx.tools.call("db.replace_records", dataset="hotels", records=rows)
```

真实语义只有一个：全量覆盖。

这不是：

- 增量更新
- patch
- upsert API

安全写法通常是先读、再改、再整包写回：

```python
rows = ctx.tools.call("db.list_records", dataset="hotels") or []
rows.append(new_row)
ctx.tools.call("db.replace_records", dataset="hotels", records=rows)
```

如果同一 dataset 有并发写入需求，先加锁；不要把 `db.replace_records` 当成多写者可并发合并的接口。

### `db.append_event`

```python
ctx.tools.call(
    "db.append_event",
    dataset="account_events",
    event_type="status_changed",
    entity_key="13800000001",
    previous_status="active",
    next_status="blocked",
    reason="risk_control",
    payload={"operator": "system"},
)
```

适合：

- 状态流转
- 操作留痕
- 历史时间线

不要把本来应该放在顶层的字段再次包进 `payload`。`previous_status`、`next_status`、`result`、`reason` 都是正式一等字段。

### `db.query_events`

```python
events = ctx.tools.call(
    "db.query_events",
    dataset="account_events",
    entity_key="13800000001",
    event_type="status_changed",
    limit=20,
)
```

适合：

- 查询某个实体的历史轨迹
- 给 Hosted UI V1 组装最近事件摘要
- 做排障和审计

如果你既要“当前状态”又要“历史轨迹”，应当快照和事件两条都写，不要混在一条数据通道里。

## 轻状态与锁

### `db.get_state` / `db.set_state` / `db.exists_state`

这组工具只服务轻量状态，不是正式业务表。

适合放：

- 分页游标
- 最近一次成功时间
- 小体量中间状态
- 短 TTL 会话标记

不适合放：

- 大批量业务 records
- 正式配置
- 长期结构化数据

示例：

```python
key = "hotel_demo:sync:cursor"
ctx.tools.call("db.set_state", key=key, value={"page": 2}, ttl=300)
cursor = ctx.tools.call("db.get_state", key=key)
```

### 锁工具

```python
ok = ctx.tools.call(
    "db.acquire_lock",
    scope="hotels",
    key="hotel-001",
    ttl=60,
    owner={"task_id": "t-1"},
)
```

适合：

- 并发互斥
- 防重跑
- 避免同一实体被重复处理

`lock_key` / `lock_scope` 属于 Core 临时锁语义，不是业务占用字段。

## 固定环境池与环境工具

固定环境池场景里，模块负责维护资格快照，排队和补位由宿主处理。不要在模块里自己 `sleep` 轮询。

### 运行模板语义矩阵

| 运行模板配置 | 宿主是否进入固定池等待语义 | `selector_name` 是否生效 | 当前轮没命中时的结果 |
|---|---|---|---|
| `mode=create` | 否 | 否 | 不适用 |
| `mode=select` + 只有 `selector_name` | 否 | 是 | 直接失败 |
| `Service Job + mode=select + resource_pool` | 是 | 否 | 回到等待席位 |
| `Service Job + mode=select + resource_pool + selector_name` | 是 | 是 | selector 返回 `None` 时回到等待席位 |

如果你要验证固定环境池等待链路，至少同时满足：

1. 作业类型是 `Service Job`
2. 运行模板选择了 `选择环境`
3. `resource_pool` 填了稳定池名

### 异步环境工具

下列工具都必须 `await`：

- `env.set_proxy`
- `env.bind_resource_pool`
- `env.mark_resource_pool_eligible`
- `env.mark_resource_pool_ineligible`
- `env.remove_resource_pool`
- `env.replace_resource_pool_snapshot`

示例：

```python
if ctx.tools and ctx.tools.has_tool("env.bind_resource_pool"):
    await ctx.tools.call(
        "env.bind_resource_pool",
        env_id=ctx.env_id,
        pool_name="bound_account_ready",
    )
```

### `replace_resource_pool_snapshot`

它的语义和 `db.replace_records` 一样，也是全量重建，不是 patch。

如果一个资源池当前应该有 10 张资格卡片，你只传 2 条 `entries`，剩余 8 张会被宿主删除。

## 代理与验证码工具

### `ip_pool.pick_proxy`

```python
proxy = ctx.tools.call(
    "ip_pool.pick_proxy",
    criteria={"pool_id": "hotel_pool", "protocol": "http"},
)
```

返回值可能是 `None`，必须判空。

### `captcha.match_slider`

```python
result = ctx.tools.call(
    "captcha.match_slider",
    background_image=bg_bytes,
    puzzle_piece_image=piece_bytes,
)
```

### `captcha.match_click_targets`

```python
result = ctx.tools.call(
    "captcha.match_click_targets",
    query_icons_image=query_bytes,
    background_image=bg_bytes,
)
```

## 防御式写法

```python
if ctx.tools and ctx.tools.has_tool("db.list_records"):
    rows = ctx.tools.call("db.list_records", dataset="hotels")
else:
    rows = []
```

兼容旧宿主或可选能力时，先 `has_tool()`，再调用。

## 明确禁止的再封装

下面这些做法会把轻量模块重新做成一套私有平台，应当避免：

- `DbClient(ctx.tools)` 再封一层所有 `db.*`
- `CoreApi`
- `ContextFacade`
- `HostRuntimeAdapter`
- `ModuleStateStore`

判断标准很简单：同一个工具名在模块里只出现少量几次，就直接调用；真有重复，再抽一个纯函数即可。

# Core 能力参考

模块运行时不应该直连宿主内部对象。统一边界只有一个:

```python
ctx.tools.call(...)
```

配套接口只有:

- `ctx.tools.has_tool(name)`
- `ctx.tools.list_tools()`
- `ctx.tools.call(name, **kwargs)`

如果你绕过这层边界，模块就不再是受控轻量应用，而是在偷偷绑定宿主内部实现。

## 工具总表

当前宿主注入的工具如下:

| 工具名 | 是否异步 | 主要用途 | 典型返回值 |
|---|---|---|---|
| `db.list_records` | 否 | 读取业务数据集 | `list[dict]` |
| `db.replace_records` | 否 | 全量覆盖业务数据集 | `bool` |
| `db.append_event` | 否 | 追加模块审计事件 | `bool` |
| `db.query_events` | 否 | 查询模块审计事件 | `list[dict]` |
| `db.acquire_lock` | 否 | 获取互斥锁 | `bool` |
| `db.release_lock` | 否 | 释放互斥锁 | `bool` |
| `db.is_locked` | 否 | 查询锁状态 | `bool` |
| `db.get_state` | 否 | 读取轻量状态 | `Any` |
| `db.set_state` | 否 | 写入轻量状态 | `bool` |
| `db.exists_state` | 否 | 判断状态键是否存在 | `bool` |
| `ip_pool.pick_proxy` | 否 | 选择代理 | `dict | None` |
| `env.set_proxy` | 是 | 给环境设置代理 | `bool` |
| `ui.declare_data_table` | 否 | 声明托管数据表 schema | `bool` |
| `ui.get_data_table` | 否 | 读取托管数据表 schema | `dict` |
| `captcha.match_slider` | 否 | 识别滑块验证码 | `SliderCaptchaMatchResult` |
| `captcha.match_click_targets` | 否 | 识别点选验证码 | `ClickCaptchaMatchResult` |

## 数据工具

先记住一个大原则：

- `db.list_records` / `db.replace_records` = 快照型当前状态
- `db.append_event` / `db.query_events` = append-only 审计历史

### `db.list_records`

```python
rows = ctx.tools.call("db.list_records", dataset="hotels")
```

适用场景:

- 读取结构化业务记录
- 给 task、workflow、代码型 UI 提供列表数据

不适合:

- 读取配置
- 读取一次性运行参数

### `db.replace_records`

```python
ok = ctx.tools.call("db.replace_records", dataset="hotels", records=rows)
```

这是当前最容易被误用的工具。

真实语义:

- 它是全量覆盖
- 不是增量更新
- 不是 patch
- 不是 upsert API

这意味着如果你这么写:

```python
ctx.tools.call("db.replace_records", dataset="hotels", records=[new_row])
```

你不是“插入一条”，你是在把整个 `hotels` 数据集重写成只剩一条。

安全写法通常是:

```python
rows = ctx.tools.call("db.list_records", dataset="hotels") or []
rows.append(new_row)
ctx.tools.call("db.replace_records", dataset="hotels", records=rows)
```

并发风险也必须知道:

- 两个 task 同时读旧列表再各自 `replace_records`，后写入的一方会覆盖前一方结果
- 如果存在并发写，优先先加锁
- 如果写逻辑越来越复杂，说明这个数据集设计该重做，而不是继续叠补丁

### `db.append_event`

```python
ok = ctx.tools.call(
    "db.append_event",
    dataset="account_events",
    event_type="status_changed",
    entity_key="13800000001",
    previous_status="active",
    next_status="blocked",
    payload={"reason": "risk_control"},
)
```

适用场景:

- 记录账号状态流转
- 写入运行留痕
- 保存 append-only 审计事件

不适合:

- 回写当前快照列表
- 覆盖历史事件
- 充当通用 CRUD 表

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

适用场景:

- 查询某个账号的历史轨迹
- 按事件类型筛选历史记录
- 按时间范围拉取运行留痕

返回结果按时间排序，支持：

- `entity_key`
- `event_type`
- `run_id`
- `start_at`
- `end_at`
- `limit`
- `offset`
- `order`

### `db.get_state` / `db.set_state` / `db.exists_state`

这些是轻量状态，不是正式业务表。

适合放:

- 分页游标
- 最近一次成功时间
- 短 TTL 会话标记
- 小体量中间状态

不适合放:

- 大批量 records
- 正式配置
- 长期结构化业务数据

推荐 key 命名:

```python
key = "hotel_demo:sync:cursor"
ctx.tools.call("db.set_state", key=key, value={"page": 2}, ttl=300)
cursor = ctx.tools.call("db.get_state", key=key)
```

推荐格式:

```text
<module_name>:<domain>:<name>
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

适合:

- 防重跑
- 并发互斥
- 避免同一账号或记录被重复处理

## 代理和环境工具

### `ip_pool.pick_proxy`

```python
proxy = ctx.tools.call(
    "ip_pool.pick_proxy",
    criteria={
        "pool_id": "hotel_pool",
        "protocol": "http",
        "min_safety_score": 90,
        "max_bound_count": 2,
    },
)
```

返回值可能是 `None`，所以必须判空。

### `env.set_proxy`

这是当前唯一异步工具，必须 `await`:

```python
if ctx.tools and ctx.tools.has_tool("env.set_proxy"):
    await ctx.tools.call(
        "env.set_proxy",
        env_id=ctx.env_id,
        proxy_value="http://1.1.1.1:8001",
    )
```

## UI 工具

### `ui.declare_data_table`

```python
ctx.tools.call(
    "ui.declare_data_table",
    view_id="hotels",
    schema={...},
)
```

当前真实约束:

- `view_id` 必须是 `snake_case`
- `dataset` 必须和 `view_id` 完全一致
- schema 只允许受控字段
- handler 名也必须是 `snake_case`

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

列定义只允许:

- `key`
- `label`
- `visible`
- `required`
- `type`
- `options`
- `default`

列类型只允许:

- `text`
- `number`
- `int`
- `bool`
- `select`

额外约束:

- 只有 `select` 列允许配置 `options`
- `select` 列必须提供非空 `options`
- `lock_key` 只用于 Core 临时锁，不用于表达业务占用态
- 已声明 `lock_key` 时，不要再声明 `occupied` / `occupied_label` 等业务占用列；Core 会直接拒绝这类 schema

### `ui.get_data_table`

```python
schema = ctx.tools.call("ui.get_data_table", view_id="hotels")
```

它适合:

- 调试 schema 是否真的声明成功
- 页面初始化时查看当前持久化 schema

## 验证码工具

### `captcha.match_slider`

```python
result = ctx.tools.call(
    "captcha.match_slider",
    background_image=bg_bytes,
    puzzle_piece_image=piece_bytes,
    puzzle_piece_start_bbox=(0, 0, 40, 40),
    device="cpu",
    return_debug=True,
)
```

### `captcha.match_click_targets`

```python
result = ctx.tools.call(
    "captcha.match_click_targets",
    query_icons_image=query_bytes,
    background_image=bg_bytes,
    device="cuda",
    return_debug=False,
)
```

## 防御式写法

```python
if ctx.tools and ctx.tools.has_tool("db.list_records"):
    rows = ctx.tools.call("db.list_records", dataset="hotels")
else:
    rows = []
```

## 明确禁止的“再包一层”

只要你开始写这些东西，就已经偏离“轻量业务模块”了:

- `DbClient(ctx.tools)` 再封一遍所有 `db.*`
- `CoreApi` 再包装 `has_tool/list_tools/call`
- `ContextFacade`
- `HostRuntimeAdapter`
- `ModuleStateStore`

判断标准很简单:

- 同一个工具名在模块里只出现 1 到 3 次，直接调
- 真有重复，就抽一个纯函数
- 不要为了“以后也许会复用”先搭一层平台

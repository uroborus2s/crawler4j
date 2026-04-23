# Core 能力参考

模块运行时不应该直连宿主内部对象。正式边界只有一层：

```python
ctx.tools.call(...)
```

配套接口也只有三项：

- `ctx.tools.has_tool(name)`
- `ctx.tools.list_tools()`
- `ctx.tools.call(name, **kwargs)`

## 能力全景

| 类别 | 工具名 | 是否异步 | 主要用途 |
|---|---|---|---|
| Hosted UI | `ui.declare_page` `ui.get_page` | 否 | 声明和读取页面 schema |
| 数据资源登记 | `db.declare_data_resource` | 否 | 登记 `managed_dataset` / `custom_table` 资源生命周期 |
| 数据库视图 | `db.declare_db_view` `db.query_view` | 否 | 登记受控统计视图并按过滤/排序/分页查询 |
| 快照数据 | `db.list_records` `db.replace_records` | 否 | 按资源模式读取和全量覆盖当前记录集 |
| 审计事件 | `db.append_event` `db.query_events` | 否 | 记录和查询 append-only 历史 |
| 轻状态与锁 | `db.get_state` `db.set_state` `db.exists_state` `db.acquire_lock` `db.release_lock` `db.is_locked` | 否 | 保存轻量状态、游标、会话和互斥锁 |
| 代理与环境 | `ip_pool.pick_proxy` `env.set_proxy` `env.bind_resource_pool` `env.mark_resource_pool_eligible` `env.mark_resource_pool_ineligible` `env.remove_resource_pool` `env.replace_resource_pool_snapshot` | `env.*` 为异步 | 代理选择、环境代理设置、固定环境池维护 |
| 验证码 | `captcha.match_slider` `captcha.match_click_targets` | 否 | 图像识别类验证码辅助 |

## Hosted UI

Hosted UI 是模块在宿主中的正式 UI 能力面。模块通过 schema 声明页面，宿主负责渲染和执行。

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
- `module.yaml.ui_extension.pages[]` 中必须存在同名页面
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

## 页面里的 `DataTable`

`DataTable` 不是独立工具，而是 `ui.declare_page` schema 的一个组件。正式能力边界如下：

- 数据源只支持 `binding`、`rows`、`query_handler`
- `query_handler` 必须是同步函数，签名为 `(context, table_id, query, params=None)`
- 行点击只支持 `row_action.type="open_page"`
- `open_page` 和按钮动作只支持 `page_id`，不再支持 `entry`

## `db.declare_data_resource`

```python
ctx.tools.call(
    "db.declare_data_resource",
    resource_id="billing_audit",
    storage_mode="custom_table",
    record_key_field="audit_id",
    cleanup_policy="drop_table",
    schema={
        "version": 1,
        "columns": [
            {"name": "audit_id", "type": "text"},
            {"name": "execution_date", "type": "text"},
            {"name": "amount", "type": "number", "nullable": True},
        ],
    },
    indexes={
        "exec_date": ["execution_date"],
    },
)
```

适用场景：

- 先显式登记数据资源，再由多个页面复用
- 为高频明细表声明 `custom_table` 生命周期
- 提前固定 `record_key_field`、`cleanup_policy`、资源 schema/index 元数据

正式约束：

- `resource_id` 必须是 `snake_case`
- `storage_mode` 只支持 `managed_dataset` / `custom_table`
- `cleanup_policy` 只支持 `delete_rows` / `drop_table` / `keep`
- `custom_table` 的真实物理表名由宿主受控生成，不由模块直接指定

## `db.declare_db_view`

```python
ctx.tools.call(
    "db.declare_db_view",
    view_id="labor_billing_stats",
    source_resource_ids=["billing_entries"],
    select_sql_template="""
SELECT
  execution_date,
  COUNT(*) AS total_count
FROM {{resource:billing_entries}}
GROUP BY execution_date
""",
    columns=[
        {"name": "execution_date", "type": "text", "filterable": True, "sortable": True},
        {"name": "total_count", "type": "int", "sortable": True},
    ],
)
```

正式约束：

- `view_id`、`source_resource_ids[*]` 必须是 `snake_case`
- V1 当前只支持 `sql_view`
- SQL 只能是单条 `SELECT` / `WITH ... SELECT` 模板
- 只允许通过 `{{resource:<resource_id>}}` 引用当前模块已登记的 `custom_table`

### `db.query_view`

```python
result = ctx.tools.call(
    "db.query_view",
    view_id="labor_billing_stats",
    filters={"execution_date": "2026-04-23"},
    sort=[{"field": "total_count", "direction": "desc"}],
    limit=50,
    offset=0,
)
```

返回值：

- `rows`
- `total`
- `limit`
- `offset`

正式约束：

- 过滤只支持等值匹配
- 只能过滤 `columns.filterable=true` 的字段
- 只能排序 `columns.sortable=true` 的字段
- 若页面中的 `DataTable` 通过 `query_handler` 调它，分页和排序由模块自行从 `query` 映射到这里

## 快照数据与审计事件

数据能力分成两条正式通道：

- 快照数据：`db.list_records` / `db.replace_records`
- 审计事件：`db.append_event` / `db.query_events`

### `db.list_records`

```python
rows = ctx.tools.call("db.list_records", dataset="hotels")
```

适合：

- 读取当前账号列表、酒店列表、状态清单
- 给 Hosted UI 页面或 workflow 提供当前记录集

### `db.replace_records`

```python
ctx.tools.call("db.replace_records", dataset="hotels", records=rows)
```

真实语义只有一个：全量覆盖。

这不是：

- 增量更新
- patch
- upsert API

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
- 操作审计
- 失败留痕
- 时间线追溯

### `db.query_events`

```python
events = ctx.tools.call(
    "db.query_events",
    dataset="account_events",
    entity_key="13800000001",
    limit=20,
)
```

## 轻状态与锁

| 工具 | 用途 |
|---|---|
| `db.get_state` | 读取轻量状态 |
| `db.set_state` | 写轻量状态 |
| `db.exists_state` | 判断状态是否存在 |
| `db.acquire_lock` | 获取互斥锁 |
| `db.release_lock` | 释放互斥锁 |
| `db.is_locked` | 检查锁状态 |

推荐：

- 用它们保存游标、会话、小体量幂等状态
- 不要把业务列表和大对象塞进去

## 固定环境池 helper

这些 helper 都依赖 `env.*resource_pool*` capability，必须在确认宿主能力存在时使用。

- `env.bind_resource_pool`
- `env.mark_resource_pool_eligible`
- `env.mark_resource_pool_ineligible`
- `env.remove_resource_pool`
- `env.replace_resource_pool_snapshot`

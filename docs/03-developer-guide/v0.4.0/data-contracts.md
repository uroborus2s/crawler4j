# 数据契约

> 版本绑定：本文只适用于 0.4.x SDK / Contracts 与 Core 0.4.0。0.4.x SDK 不兼容 0.3.x 的 `module.yaml.data`、`data resource/view/seed` 命令或 `data/sql` 事实源。

0.4.0 的数据契约由装饰器和 manifest lock 承载。

运行时代码仍然只有一个数据库入口：`ctx.db`。

## 声明数据表

```python
from crawler4j_contracts import data_table


@data_table(
    name="accounts",
    label="账号",
    storage_mode="custom_table",
    schema=[
        {"name": "account_id", "type": "string", "required": True},
        {"name": "status", "type": "string"},
        {"name": "source_created_at", "type": "string"},
    ],
    indexes=[
        {"fields": ["account_id"], "unique": True},
        {"fields": ["status"]},
    ],
)
class AccountsTable:
    pass
```

SDK 扫描 `@data_table` 后，把表声明写入 manifest lock。Core 安装或加载模块时按 lock 同步数据能力。`storage_mode` 支持：

- `custom_table`：默认模式，落到模块受控物理表，支持只读视图、联表、分组和聚合。
- `managed_dataset`：托管快照模式，落到 `data.db.module_datasets`，支持单源 `select/where/order/limit/offset` 和 `where` 后 `count(*)`，写入支持 `replace/upsert/update_where/delete_where`。

`@data_table.schema` 声明稳定业务字段和开发期校验基线。对 `managed_dataset` 来说，schema 也是 `record_json` 的持久化白名单；replace/upsert/update_where 只能写 schema 中声明的业务字段，`record_json` 不接受模块随意扩展字段。`custom_table` 仍必须写入实际物理表列。

`custom_table` 的主键由 `record_key_field` 指向 schema 中的某个字段；未显式声明时使用 schema 第一列。需要宿主自增主键时，只能把 `auto_increment=True` 声明在 `record_key_field` 对应的 integer 字段上：

```python
@data_table(
    name="account_events",
    storage_mode="custom_table",
    record_key_field="id",
    schema=[
        {"name": "id", "type": "integer", "auto_increment": True},
        {"name": "account_id", "type": "string"},
        {"name": "event_type", "type": "string"},
    ],
)
class AccountEventsTable:
    pass
```

自增主键表使用 `ctx.db.into("account_events").add(...)` 新增记录；新增时可以省略 `id`，返回值是本次插入生成的 id 列表。`upsert` 仍然需要稳定主键，不能把缺省 id 的自增插入伪装成幂等更新。

`managed_dataset` 的 `ctx.db.from_(...).where(...)` 会按字段分流：`record_index`、`record_key`、`run_status`、`record_status`、`created_at`、`updated_at` 是宿主物理列；schema 中声明的业务字段会下推为 SQLite `json_extract(record_json, '$.<field>')` 查询每行 `record_json` 的顶层 JSON 字段。支持 schema 字段过滤、排序、选择，以及 `ctx.db.from_(...).where(...).count(alias="total").execute()` 统计 `where` 后记录条数；`managed_dataset` 的 count 只支持 `count(*)`，不支持 `group_by`、`join` 或 `sum/avg/min/max`。不支持嵌套 JSON path、schema 外 JSON key 或直接查询原始 `record_json`。宿主内部 `query_resource_records()` 和 `ctx.db.from_` 共用同一份数据源描述，返回时会把 schema 业务字段与物理字段展开成同一行记录。`where` 条件统一写成数组，例如 `where(["age", "=", 18])`；多个条件默认 `AND`，也可以写 `["or", ...]` / `["and", ...]` 组合。

只服务 UI 的展示派生值仍建议由页面 `query_handler` 动态计算；如果模块确实需要持久化和查询 `phone_masked`、`status_label` 这类字段，必须先把它们声明为普通 schema 业务字段，宿主才会写入 `record_json` 并支持返回和查询。

`@data_view` 只能引用 `custom_table` 数据表；`managed_dataset` 使用 `ctx.db.from_(...)` 查询，不进入 SQL 视图。

数据表和只读视图的列契约只描述字段本身，不声明 `filterable` / `sortable`。能否过滤、排序由 `ctx.db` 和宿主内部查询执行器按字段存在性、数据源类型和表达式统一校验；继续声明这两个旧字段会在 manifest / schema 归一化阶段报错。

Core 0.4.0 只接受当前 `data.db` 表结构。旧版 `module_datasets`、`module_db_views` 或 `module_data_resources` schema 不再自动迁移，宿主启动时会直接报错，旧数据需要在升级前由运维脚本离线整理到 0.4.0 结构。

## 从 v1 数据模型重写

| 0.3.x 数据对象 | 0.4.0 对象 | 说明 |
|---|---|---|
| `module.yaml.data.resources[]` | `@data_table` | 表名、schema、indexes 从装饰器进入 lock |
| `data/sql/views/*.sql` + `module.yaml.data.views[]` | `@data_view(sql=..., schema=...)` | SQL 和视图 schema 跟随装饰器元数据，宿主创建只读 DB view |
| `managed_dataset` / `custom_table` | `@data_table(storage_mode=...)` | 存储策略进入装饰器 metadata，`module.yaml.data` 不再兜底 |
| `ctx.db.from_(...)` | 继续保留 | 数据表和视图都通过同一个查询入口读取，事实源从 manifest 改为 lock |

## 声明只读视图

```python
from crawler4j_contracts import data_view


@data_view(
    name="account_overview",
    sources=["accounts"],
    sql="""
    SELECT account_id, status
    FROM {{resource:accounts}}
    """,
    schema=[
        {"name": "account_id", "type": "string"},
        {"name": "status", "type": "string"},
    ],
)
def account_overview():
    pass
```

运行时调用：

```python
rows = (
    ctx.db.from_("account_overview")
    .select(["account_id", "status"])
    .where(["status", "=", "ready"])
    .execute()
)
```

`@data_view` 是数据库视图契约。Core 安装或加载模块时会根据 lock 同步真实 SQLite 视图；模块运行时只能以 `ctx.db.from_("view_id")` 的只读方式访问，不能写入视图，也不能在运行时拼接或执行未声明 SQL。

## 写入数据

```python
ctx.db.into("accounts").replace(
    [
        {"account_id": "A001", "status": "ready"},
        {"account_id": "A002", "status": "blocked"},
    ]
)

event_ids = ctx.db.into("account_events").add(
    [
        {"account_id": "A001", "event_type": "login"},
        {"account_id": "A002", "event_type": "blocked"},
    ]
)
```

读取数据：

```python
rows = (
    ctx.db.from_("accounts")
    .select(["account_id", "status"])
    .where(["status", "=", "ready"])
    .order_by("account_id")
    .limit(50)
    .execute()
)
```

如果没有调用 `.limit(...)` 或 `.offset(...)`，`ctx.db.from_(...).execute()` 不会在 SQL 上追加分页子句，会返回满足条件的全部行。列表页、表格页和可能增长的数据源必须显式调用 `.limit(page_size).offset(...)`，避免一次性加载大表。

条件组合示例：

```python
ctx.db.from_("accounts").where([["age", ">", 18], ["status", "=", "ready"]])
ctx.db.from_("accounts").where(["or", ["age", "<", 18], ["age", ">", 60]])
ctx.db.from_("accounts").where(["and", ["or", ["status", "=", "ready"], ["status", "=", "pending"]], ["age", ">=", 18]])
```

## 描述数据源

模块可以用 `ctx.db.describe(source)` 读取宿主归一化后的数据源契约。`source` 是逻辑数据源名，也就是 `@data_table(name=...)` 或 `@data_view(name=...)` 的名称，不是 SQLite 物理表名。

```python
descriptor = ctx.db.describe("accounts")
```

返回结构由宿主生成，字段含义固定：

- `kind`：`data_table` 或 `data_view`
- `source_kind`：`custom_table` 返回 `relation`，`managed_dataset` 返回 `snapshot`，`data_view` 返回 `read_model`
- `storage_mode`：数据表的存储模式；只读视图没有写入存储模式
- `record_key_field`：数据表主键字段
- `columns`：业务 schema 字段，包含 `nullable`、`required`、`writable`，自增主键还包含 `auto_increment`
- `system_fields`：宿主维护字段，例如 `created_at`、`updated_at`，或 `managed_dataset` 的 `record_index` / `record_key` / `run_status` / `record_status`
- `writable_fields`：模块可写字段列表
- `required_fields`：新增完整记录时必须提供的业务字段
- `read_only_fields`：模块不可写字段列表

`custom_table` 的非自增主键是模块必须提供的普通可写字段：

```json
{
  "source": "account_tags",
  "kind": "data_table",
  "source_kind": "relation",
  "storage_mode": "custom_table",
  "record_key_field": "tag_id",
  "columns": [
    {"name": "tag_id", "type": "text", "nullable": false, "required": true, "writable": true},
    {"name": "tag", "type": "text", "nullable": false, "required": true, "writable": true}
  ],
  "system_fields": [
    {"name": "created_at", "type": "int", "writable": false, "generated": true},
    {"name": "updated_at", "type": "int", "writable": false, "generated": true}
  ],
  "writable_fields": ["tag_id", "tag"],
  "required_fields": ["tag_id", "tag"],
  "read_only_fields": ["created_at", "updated_at"]
}
```

`custom_table` 的自增主键由宿主生成，主键字段不可写，也不进入 `required_fields`：

```json
{
  "source": "ctrip_account_daily_audits",
  "kind": "data_table",
  "source_kind": "relation",
  "storage_mode": "custom_table",
  "record_key_field": "id",
  "columns": [
    {"name": "id", "type": "int", "nullable": false, "required": false, "writable": false, "auto_increment": true},
    {"name": "ctrip_account", "type": "text", "nullable": false, "required": true, "writable": true},
    {"name": "audit_date", "type": "text", "nullable": false, "required": true, "writable": true}
  ],
  "system_fields": [
    {"name": "created_at", "type": "int", "writable": false, "generated": true},
    {"name": "updated_at", "type": "int", "writable": false, "generated": true}
  ],
  "writable_fields": ["ctrip_account", "audit_date"],
  "read_only_fields": ["id", "created_at", "updated_at"],
  "required_fields": ["ctrip_account", "audit_date"]
}
```

`managed_dataset` 的业务字段仍在 `columns` 中；宿主快照字段在 `system_fields` 中。只有 `run_status` / `record_status` 是可写系统字段，`record_index`、`record_key`、`created_at`、`updated_at` 仍只读。

例如 `accounts` 是托管快照表时：

```json
{
  "source": "accounts",
  "kind": "data_table",
  "source_kind": "snapshot",
  "storage_mode": "managed_dataset",
  "record_key_field": "account_id",
  "columns": [
    {"name": "account_id", "type": "text", "nullable": false, "required": true, "writable": true},
    {"name": "status", "type": "text", "nullable": true, "required": false, "writable": true}
  ],
  "system_fields": [
    {"name": "record_index", "type": "int", "writable": false, "generated": true},
    {"name": "record_key", "type": "text", "writable": false, "generated": true},
    {"name": "run_status", "type": "text", "writable": true, "generated": false},
    {"name": "record_status", "type": "text", "writable": true, "generated": false},
    {"name": "created_at", "type": "int", "writable": false, "generated": true},
    {"name": "updated_at", "type": "int", "writable": false, "generated": true}
  ],
  "writable_fields": ["account_id", "status", "run_status", "record_status"],
  "required_fields": ["account_id"],
  "read_only_fields": ["record_index", "record_key", "created_at", "updated_at"]
}
```

## 宿主保留字段

不要把这些字段声明为模块业务列：

- `created_at`
- `updated_at`
- `create_at`
- `update_at`

其中 `created_at` / `updated_at` 是宿主真实维护的创建、更新时间字段；`create_at` / `update_at` 是常见误写，也会被前置阻断，避免模块用近似字段绕过宿主语义。

`managed_dataset` 还有一组托管快照系统字段，不要在 `@data_table(..., storage_mode="managed_dataset")` 的 schema、类注解或 indexes 中声明：

- `record_index`
- `record_key`
- `run_status`
- `record_status`

这些字段由宿主的 `module_datasets` 物理表管理。`record_index` 由宿主按写入顺序生成；`record_key` 来自 `record_key_field` 对应的业务字段；`created_at` / `updated_at` 由宿主维护。replace/upsert 如果收到 `record_index`、`record_key`、`created_at`、`updated_at`，会忽略这些生成型物理字段，便于把查询结果读出后再写回。`run_status` / `record_status` 可以在 `replace/upsert/update_where` 时作为状态值写入并在快照查询结果中返回，但不进入 `record_json`，也不属于模块业务 schema。`update_where` 仍会拒绝 `record_index`、`record_key`、`created_at` 或 `updated_at`。
查询时可以在 `where`、`select`、`order_by` 中使用这些宿主字段；模块业务字段来自 schema 声明。正式 `ctx.db` 查询面与宿主内部查询使用同一份数据源描述，历史 `record_json` 中残留但未声明的顶层 key 不会被展开或查询。

这些字段会在以下入口被阻断：

- 模块项目打开
- DevLink 注册
- `crawler4j check full`
- `crawler4j manifest lock`
- `crawler4j package build`

阻断范围包括：

- `@data_table` 显式 schema
- 类注解推导字段
- indexes
- `@data_view.schema`

如果业务确实需要来源系统时间戳，使用明确业务名前缀：

- `source_created_at`
- `source_updated_at`
- `business_created_at`
- `business_updated_at`

## manifest lock

生成：

```bash
uv run crawler4j manifest lock
```

lock 是 SDK 的扫描快照，通常记录：

- 数据表名
- 字段 schema
- 索引
- 只读视图
- SQL 占位符
- 视图 schema
- 保留字段诊断结果
- `managed_dataset` 中疑似 UI 派生字段的 warning，例如 `*_label`、`*_display`、`*_masked`

不要手写 `.crawler4j/manifest.lock.json`。源码变化后重新生成。

最小 lock 片段：

```json
{
  "lock_version": 1,
  "data_tables": [
    {
      "name": "accounts",
      "source": "data/accounts.py",
      "schema": [{"name": "account_id", "type": "string"}],
      "indexes": [{"fields": ["account_id"], "unique": true}]
    }
  ],
  "data_views": [
    {
      "name": "account_overview",
      "source": "data/accounts.py",
      "sql_hash": "sha256:...",
      "source_resource_ids": ["accounts"]
    }
  ],
  "diagnostics": []
}
```

## 禁止的运行时写法

不要在运行时代码里声明数据库能力：

```python
ctx.tools.call("db.declare_data_resource", ...)
ctx.tools.call("db.declare_db_view", ...)
```

不要执行未注册 SQL。模块数据库访问固定走：

- `ctx.db.from_(...)`
- `ctx.db.into(...).replace(...)`
- `ctx.db.audit(...).append(...)`

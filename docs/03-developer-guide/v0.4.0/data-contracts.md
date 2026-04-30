# 数据契约

> 状态：设计预览。本文描述 0.4.0 目标数据契约；当前可执行数据契约仍在 0.3.x 指南中通过 `module.yaml.data` 和 `data/sql` 维护。

0.4.0 的数据契约由装饰器和 manifest lock 承载。

运行时代码仍然只有一个数据库入口：`ctx.db`。

## 声明数据表

```python
from crawler4j_contracts import data_table


@data_table(
    name="accounts",
    label="账号",
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

SDK 扫描 `@data_table` 后，把表声明写入 manifest lock。Core 安装或加载模块时按 lock 同步数据能力。

## 从 v1 数据模型映射

| 0.3.x 数据对象 | 0.4.0 目标对象 | 说明 |
|---|---|---|
| `module.yaml.data.resources[]` | `@data_table` | 表名、schema、indexes 从装饰器进入 lock |
| `data/sql/queries/*.sql` + `module.yaml.data.queries[]` | `@data_query(sql=...)` | SQL 和 output schema 跟随装饰器元数据 |
| `managed_dataset` / `custom_table` | `@data_table` 的存储策略字段 | 目标实现需要在装饰器 metadata 中保留该语义 |
| `ctx.db.from_(...)` / `ctx.db.named(...)` | 继续保留 | 运行时代码入口不变，事实源从 manifest 改为 lock |

## 声明命名查询

```python
from crawler4j_contracts import data_query


@data_query(
    name="ready_accounts",
    source="accounts",
    sql="""
    SELECT account_id, status
    FROM {{resource:accounts}}
    WHERE status = :status
    """,
    output_schema=[
        {"name": "account_id", "type": "string"},
        {"name": "status", "type": "string"},
    ],
)
def ready_accounts():
    pass
```

运行时调用：

```python
rows = ctx.db.named("ready_accounts").bind(status="ready").execute()
```

## 写入数据

```python
ctx.db.into("accounts").replace(
    [
        {"account_id": "A001", "status": "ready"},
        {"account_id": "A002", "status": "blocked"},
    ]
)
```

读取数据：

```python
rows = (
    ctx.db.from_("accounts")
    .select("account_id", "status")
    .where_eq("status", "ready")
    .order_by("account_id")
    .limit(50)
    .execute()
)
```

## 宿主保留字段

不要把这些字段声明为模块业务列：

- `created_at`
- `updated_at`
- `create_at`
- `update_at`

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
- query output schema

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
- 命名查询
- SQL 占位符
- 输出 schema
- 保留字段诊断结果

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
  "data_queries": [
    {
      "name": "ready_accounts",
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
- `ctx.db.named(...).bind(...).execute()`
- `ctx.db.into(...).replace(...)`
- `ctx.db.audit(...).append(...)`

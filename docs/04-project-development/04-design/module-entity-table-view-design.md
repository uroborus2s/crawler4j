# 模块实体表视图与分析查询设计

**项目名称：** 蛛行演略（crawler4j）  
**文档状态：** 已批准  
**负责人：** 当前仓库维护者  
**主要读者：** 架构 | Core 开发 | SDK 开发 | QA | 模块开发者  
**上游输入：** `api-design.md` | `module-config-runtime-data-contract.md` | `module-hosted-ui-framework.md` | `CR-012` 已落地的 `module_data_resources` / `custom_table` 实体表能力  
**下游输出：** `docs/04-project-development/05-development-process/implementation-plan.md` | `docs/04-project-development/06-testing-verification/test-plan.md` | 后续 `docs/03-developer-guide/` 实体表视图开发者指南  
**关联 ID：** `API-005`, `API-008`, `API-009`, `CR-014`, `TASK-028`  
**最后更新：** 2026-04-23

> 注：本设计文档的“运行时声明视图”方案已被后续破坏性升级收口为 manifest 驱动实现。当前正式事实源以 `api-design.md` 和 `module-config-runtime-data-contract.md` 为准：表、视图、命名查询统一登记在 `module.yaml.data`，SQL 位于 `data/sql/*`，运行时只保留 `db.query_view` / `db.run_query`，不再接受 `db.declare_db_view`。

## 1. 背景

`CR-012` 已把模块数据资源收口成两种正式模式：

- `managed_dataset`：低频稳定记录，实际落在 `module_datasets`
- `custom_table`：模块自定义实体表，真实列由 `module_data_resources.schema_version/schema_json/indexes_json` 驱动

这解决了“数据存哪”和“实体表怎么建”的问题，但还没有解决“如何在实体表之上做安全的统计查询和数据库视图”的问题。

典型业务需求如下：

- `labor_billing_entries`：按天保存劳保账号任务计费明细
- `labor_billing_stats`：按 `execution_date`、`labor_account`、`bill_batch` 聚合统计数量和金额
- 客户端需要对统计视图做条件查询、排序和分页，而不是把所有明细先拉回 Python 再算

当前缺口有 3 个：

- 缺少“数据库视图”这一层正式事实源
- 缺少面向只读统计表的查询接口
- 缺少让 hosted page 通过 `ui.declare_page + inline DataTable/query_handler` 以只读方式绑定数据库视图的正式契约

## 2. 设计目标

### 2.1 必达目标

- 在 `custom_table` 实体表之上提供宿主管理的数据库视图能力
- 明确区分三层对象：
  - 存储资源：`module_data_resources`
  - 数据库视图：`module_db_views`
  - 宿主页 schema：`module_pages` 中的 `Page / inline DataTable`
- 模块登记的是受控 `SELECT` 视图定义，不是完整 `CREATE VIEW` 脚本
- 宿主统一负责命名、校验、创建、查询、卸载清理
- 提供只读查询能力，支持受控过滤、排序、分页
- Hosted UI 页面通过 `ui.declare_page` 声明，并在页面内联 `DataTable(query_handler)` 展示只读统计表

### 2.2 非目标

- 不开放任意 SQL 执行工具
- 不支持通过视图做写入、更新、删除
- 不支持跨模块数据联表
- V1 不实现自动物化、增量刷新和查询缓存
- V1 不开放通用查询 DSL、任意函数白名单或用户自定义 where/order SQL

## 3. 核心决策

### 3.1 三层边界固定分离

| 层级 | 事实源 | 作用 |
|---|---|---|
| 存储资源 | `module_data_resources` | 管理 `managed_dataset` / `custom_table` 的生命周期、schema、indexes、cleanup |
| 数据库视图 | `module_db_views` | 管理实体表之上的数据库视图定义、源资源引用、列能力和卸载清理 |
| 宿主页 schema | `module_pages` | 管理 `Page / Section / Text / Button / DataTable` 结构；内联 `DataTable` 通过 `query_handler` 调 `db.query_view` |

结论：

- `module_data_resources` 不负责登记数据库视图
- `module_pages` 只负责页面结构与查询回调绑定，不负责数据库对象生命周期
- `module_db_views` 成为“数据库视图”唯一正式事实源

### 3.2 登记的是 `SELECT` 模板，不是完整 `CREATE VIEW`

模块不直接提交完整 DDL：

```sql
CREATE VIEW my_view AS ...
```

模块只登记受控查询模板：

```sql
SELECT ...
FROM {{resource:labor_billing_entries}}
GROUP BY ...
```

宿主负责：

- 生成物理视图名
- 把 `{{resource:<resource_id>}}` 解析为真实物理表名
- 校验 SQL 只包含允许的查询语义
- 执行 `CREATE VIEW`
- 卸载时执行 `DROP VIEW`

这样可以避免模块绕过命名约束、直接依赖物理表名或注入 DDL/DML。

### 3.3 数据库视图只建立在同模块 `custom_table` 之上

V1 只允许数据库视图引用：

- 当前模块名下
- 已登记在 `module_data_resources`
- `storage_mode = custom_table`

不允许直接引用：

- `module_datasets`
- 其他模块的资源
- 系统表
- 其他数据库视图

这样可以避免 V1 一开始就引入跨模块耦合、依赖图排序和级联失效复杂度。

### 3.4 Hosted UI 页面内联表格只读绑定数据库视图

正式页面链路固定为：

- `declare_ui()` 调用 `ui.declare_page`
- 页面 schema 在 `children[]` 中内联 `DataTable`
- `DataTable.data_source.type = "query_handler"`
- `query_handler(context, table_id, query, params=None)` 内部调用 `db.query_view`

V1 仅支持只读统计表：

- 读取：走 `db.query_view`
- 过滤：由 `query_handler` 把受控字段过滤下推到 `db.query_view`
- 排序：由 `query_handler` 把受控字段排序下推到 `db.query_view`
- 分页：由宿主查询接口下推
- 不提供新增、编辑、删除

## 4. 数据模型设计

### 4.1 新增 `module_db_views`

```sql
CREATE TABLE IF NOT EXISTS module_db_views (
    module_name TEXT NOT NULL,
    view_id TEXT NOT NULL,
    view_kind TEXT NOT NULL CHECK (view_kind IN ('sql_view')),
    physical_view_name TEXT NOT NULL,
    source_resource_ids_json TEXT NOT NULL DEFAULT '[]',
    select_sql_template TEXT NOT NULL,
    columns_json TEXT NOT NULL DEFAULT '[]',
    schema_version INTEGER NOT NULL DEFAULT 1,
    cleanup_policy TEXT NOT NULL CHECK (cleanup_policy IN ('drop_view', 'keep')),
    created_at INTEGER DEFAULT (strftime('%s', 'now')),
    updated_at INTEGER DEFAULT (strftime('%s', 'now')),
    PRIMARY KEY (module_name, view_id)
);

CREATE INDEX IF NOT EXISTS idx_module_db_views_module
ON module_db_views(module_name);
```

### 4.2 字段语义

| 字段 | 含义 |
|---|---|
| `module_name` | 所属模块 |
| `view_id` | 逻辑视图标识，模块侧引用名 |
| `view_kind` | 视图类型；V1 只允许 `sql_view` |
| `physical_view_name` | 宿主生成的真实数据库对象名，推荐 `module_name_view_<view_id>` |
| `source_resource_ids_json` | 当前视图允许引用的实体表资源 ID 列表 |
| `select_sql_template` | 模块登记的 `SELECT` SQL 模板，使用 `{{resource:<resource_id>}}` 占位 |
| `columns_json` | 视图查询返回列定义与查询能力元数据 |
| `schema_version` | 视图定义版本 |
| `cleanup_policy` | 模块卸载时对视图对象的处理策略；V1 只允许 `drop_view` / `keep` |

### 4.3 `columns_json` 结构

建议结构：

```json
[
  {
    "name": "execution_date",
    "type": "text",
    "nullable": false,
    "filterable": true,
    "sortable": true
  },
  {
    "name": "labor_account",
    "type": "text",
    "nullable": false,
    "filterable": true,
    "sortable": true
  },
  {
    "name": "bill_batch",
    "type": "text",
    "nullable": false,
    "filterable": true,
    "sortable": true
  },
  {
    "name": "total_count",
    "type": "int",
    "nullable": false,
    "filterable": false,
    "sortable": true
  }
]
```

约束：

- `name` 必须 `snake_case`
- `type` 与实体表列类型体系保持一致：`text/int/number/bool/json`
- `filterable` / `sortable` 只表达宿主允许开放给查询层的能力，不等于 SQL 本身天然支持

## 5. SQL 模板契约

### 5.1 SQL 书写方式

模块登记：

```sql
SELECT
  execution_date,
  labor_account,
  bill_batch,
  COUNT(*) AS total_count,
  SUM(amount) AS total_amount
FROM {{resource:labor_billing_entries}}
GROUP BY execution_date, labor_account, bill_batch
```

宿主创建物理视图时，解析成：

```sql
CREATE VIEW demo_module_view_labor_billing_stats AS
SELECT
  execution_date,
  labor_account,
  bill_batch,
  COUNT(*) AS total_count,
  SUM(amount) AS total_amount
FROM demo_module_labor_billing_entries
GROUP BY execution_date, labor_account, bill_batch
```

### 5.2 校验规则

`select_sql_template` 必须满足：

- 只能是单条 `SELECT` / `WITH ... SELECT` 语句
- 不允许包含 `;`
- 不允许包含 `INSERT` / `UPDATE` / `DELETE` / `DROP` / `ALTER` / `ATTACH` / `DETACH` / `PRAGMA` / `CREATE` / `REPLACE`
- 必须只通过 `{{resource:<resource_id>}}` 引用来源实体表
- 占位资源必须存在于 `source_resource_ids_json`
- `source_resource_ids_json` 中的每个资源都必须：
  - 属于当前模块
  - 已登记
  - `storage_mode = custom_table`
- V1 不允许引用其他数据库视图

### 5.3 创建校验流程

宿主在 `db.declare_db_view` 时执行：

1. 解析并规范化 `view_id`、`source_resource_ids`、`columns_json`
2. 校验 SQL 模板语义和占位资源所有权
3. 将占位资源替换为真实物理表名，得到 resolved SQL
4. 在事务里创建临时视图或执行等价校验 SQL，确认语法有效
5. 校验视图实际返回列与 `columns_json` 一致
6. 落库 `module_db_views`
7. 原子 `DROP VIEW IF EXISTS + CREATE VIEW`

SQLite 不支持 `CREATE OR REPLACE VIEW`，所以必须走事务内 drop/create。

## 6. 运行时 API 设计

### 6.1 `db.declare_db_view`

```python
ctx.tools.call(
    "db.declare_db_view",
    view_id="labor_billing_stats",
    view_kind="sql_view",
    source_resource_ids=["labor_billing_entries"],
    select_sql_template="""
SELECT
  execution_date,
  labor_account,
  bill_batch,
  COUNT(*) AS total_count,
  SUM(amount) AS total_amount
FROM {{resource:labor_billing_entries}}
GROUP BY execution_date, labor_account, bill_batch
""",
    columns=[
        {"name": "execution_date", "type": "text", "filterable": True, "sortable": True},
        {"name": "labor_account", "type": "text", "filterable": True, "sortable": True},
        {"name": "bill_batch", "type": "text", "filterable": True, "sortable": True},
        {"name": "total_count", "type": "int", "filterable": False, "sortable": True},
        {"name": "total_amount", "type": "number", "filterable": False, "sortable": True},
    ],
    cleanup_policy="drop_view",
)
```

返回值建议：

```python
{
    "module_name": "demo_module",
    "view_id": "labor_billing_stats",
    "view_kind": "sql_view",
    "physical_view_name": "demo_module_view_labor_billing_stats",
    "source_resource_ids": ["labor_billing_entries"],
    "schema_version": 1,
    "columns": [...],
    "cleanup_policy": "drop_view",
}
```

### 6.2 `db.query_view`

```python
ctx.tools.call(
    "db.query_view",
    view_id="labor_billing_stats",
    filters={
        "execution_date": "2026-04-23",
        "labor_account": "acct-001",
        "bill_batch": "batch-001",
    },
    sort=[{"field": "total_count", "direction": "desc"}],
    limit=50,
    offset=0,
)
```

返回值建议：

```python
{
    "rows": [...],
    "total": 123,
    "limit": 50,
    "offset": 0,
}
```

V1 约束：

- 过滤只支持等值匹配
- 只能过滤 `columns_json.filterable = true` 的字段
- 只能排序 `columns_json.sortable = true` 的字段
- `direction` 只支持 `asc/desc`

### 6.3 后续可扩展项

保留但 V1 不实现：

- 范围过滤、`IN`、时间区间
- 视图依赖其他视图
- 查询缓存和预聚合

## 7. Hosted UI 接入

### 7.1 正式页面链路

正式页面链路如下：

- `declare_ui()` 只调用 `ui.declare_page`
- `ui.declare_page` 产出的 `Page.children[]` 内联 `DataTable`
- `DataTable.data_source.type = "query_handler"`
- `query_handler` 内部把 `query.filters / query.sort / query.limit / query.offset` 路由到 `db.query_view`

V1 规则：

- 不再存在单独的 `ui.declare_data_table`
- 数据库视图表固定只读
- 不允许宿主新增/编辑/删除按钮

### 7.2 `query_handler` 在 db view 模式下的行为

- 首次加载和翻页时，宿主调用页面内联 `DataTable` 的 `query_handler`
- `query_handler` 再调用 `db.query_view`
- 顶部过滤条只下推 `columns_json.filterable = true` 的字段
- 排序只下推 `columns_json.sortable = true` 的字段
- 页面参数或导航参数需要参与筛选时，也由 `query_handler` 统一合并到 `db.query_view.filters`
- 数据表行为固定只读

### 7.3 UI 绑定示例

```python
ctx.tools.call(
    "ui.declare_page",
    page_id="billing_stats",
    schema={
        "type": "Page",
        "title": "劳保账号统计",
        "load_handler": "load_billing_stats_page",
        "children": [
            {
                "type": "DataTable",
                "table_id": "billing_stats",
                "title": "劳保账号统计",
                "columns": [
                    {"key": "execution_date", "label": "执行日期"},
                    {"key": "labor_account", "label": "劳保账号"},
                    {"key": "bill_batch", "label": "账单批次"},
                    {"key": "total_count", "label": "数量", "type": "int"},
                    {"key": "total_amount", "label": "金额", "type": "number"},
                ],
                "data_source": {
                    "type": "query_handler",
                    "handler": "query_billing_stats",
                },
            }
        ],
    },
)


def query_billing_stats(context, table_id, query, params=None):
    return context.tools.call(
        "db.query_view",
        view_id="labor_billing_stats",
        filters=query.get("filters") or {},
        sort=query.get("sort") or [{"field": "total_count", "direction": "desc"}],
        limit=query.get("limit", 50),
        offset=query.get("offset", 0),
    )
```

## 8. 生命周期与卸载

### 8.1 创建与更新

- 同一 `view_id` 重复声明时，宿主按幂等更新处理
- 若 SQL、列定义或来源资源变化，宿主重新校验并事务内重建物理视图

### 8.2 源实体表变化

- 若源 `custom_table` schema 改变，依赖视图必须重新 `declare`
- 宿主不做隐式 SQL 重写或静默修复
- 校验失败时保留显式错误，不允许 silent fallback

### 8.3 模块卸载

卸载模块时：

1. 先读取 `module_db_views`
2. 按 `cleanup_policy` 执行：
   - `drop_view` -> `DROP VIEW`
   - `keep` -> 保留数据库对象，只删除 manifest
3. 再删除 `module_db_views` 行
4. 客户端醒目提示中列出将被删除的数据库视图

## 9. 示例：劳保账号统计视图

### 9.1 源实体表

资源：

- `resource_id = labor_billing_entries`
- `storage_mode = custom_table`

字段：

- `entry_id`
- `execution_date`
- `labor_account`
- `bill_batch`
- `task_id`
- `amount`
- `created_at`
- `updated_at`

### 9.2 统计视图

逻辑视图：

- `view_id = labor_billing_stats`

SQL 模板：

```sql
SELECT
  execution_date,
  labor_account,
  bill_batch,
  COUNT(*) AS total_count,
  SUM(amount) AS total_amount
FROM {{resource:labor_billing_entries}}
GROUP BY execution_date, labor_account, bill_batch
```

查询入口：

- 过滤：`execution_date`、`labor_account`、`bill_batch`
- 排序：`total_count DESC`

这正对应业务侧“劳保账号统计视图按执行日期、劳保账号、账单批次查询并按数量排序”的要求。

## 10. 分阶段落地建议

### 10.1 V1

- `module_db_views`
- `db.declare_db_view`
- `db.query_view`
- `ui.declare_page + inline DataTable/query_handler`
- 过滤/排序/分页
- 卸载清理

### 10.2 V2

- 更多过滤操作符
- 视图依赖视图
- 查询缓存和统计预聚合

## 11. 设计结论

- 实体表视图必须新增独立事实源 `module_db_views`
- 模块登记的是受控 `SELECT` SQL 模板，不是完整 `CREATE VIEW`
- 数据库存储层、数据库视图层、UI 展示层必须继续分离
- V1 先做 `sql_view + query_view + ui.declare_page + inline DataTable/query_handler`，不要把物化视图和任意 SQL 一起带进首版

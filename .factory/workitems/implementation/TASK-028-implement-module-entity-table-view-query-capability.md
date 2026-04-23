# TASK-028 实现模块实体表视图与分析查询能力

- 状态：DONE
- 负责人：Codex
- 优先级：P0
- 估算：4.0 人/天
- 关联 ID：`TASK-028`, `CR-014`, `API-009`

## 目标

- 在 `custom_table` 实体表能力之上新增数据库视图能力。
- 为模块提供安全的统计查询入口，而不是开放任意 SQL。
- 让 Hosted UI 可以只读展示统计视图结果。

## 范围

- 持久层：`module_db_views`、物理视图创建/更新/删除、视图 SQL 模板校验。
- 运行时：`db.declare_db_view`、`db.query_view`。
- Hosted UI：`core:data_table` 只读统计表模式、过滤/排序/分页查询路由。
- SDK / schema：`ui.declare_data_table` 新增 `data_source_kind=db_view` / `db_view_id` 契约。
- 测试与文档：补持久层、runtime、MMS、SDK、integration/acceptance 与正式设计/开发者文档。

## 非目标

- 不实现任意 SQL 工具。
- 不实现数据库视图写入。
- 不实现 `materialized_view` 刷新和缓存。

## 验收标准

- `module_db_views` 可初始化并登记数据库视图 manifest。
- 视图 SQL 只允许受控 `SELECT` 模板与 `{{resource:<resource_id>}}` 占位。
- `db.query_view` 支持受控过滤、排序、分页。
- `core:data_table` 在 `db_view` 模式下禁用 CRUD，并正确展示统计视图结果。
- 卸载模块时，宿主能列出并清理相关数据库视图。
- 定向 pytest、integration/acceptance 与 ruff 通过。

## 完成记录

- 持久层已新增 `module_db_views`、视图 SQL 模板校验、物理视图重建与模块卸载清理链路。
- 运行时已新增 `db.declare_db_view`、`db.query_view`，SDK `check full` 已接受 `db_view` 数据源声明。
- Hosted UI `core:data_table` 已新增 `db_view` 只读统计模式、过滤栏、排序栏与分页导航，并在该模式下禁用 CRUD。
- 本地定向验证已通过：`122 passed` + 目标文件 `ruff check` 通过。

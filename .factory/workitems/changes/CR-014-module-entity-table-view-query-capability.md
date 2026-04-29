# CR-014 模块实体表视图与分析查询能力

- 状态：DONE
- 类型：CR
- 优先级：P0
- 估算：4.0 人/天
- 关联 ID：`CR-014`, `API-009`, `TASK-028`
- 提出日期：2026-04-23

## 变更动机

- `CR-012` 已建立 `managed_dataset` / `custom_table` 两种正式存储模式，但还缺少数据库视图能力。
- 业务需要在模块自定义实体表上做统计汇总，例如“劳保账号计费明细 -> 劳保账号统计视图”。
- 现有 `db.list_records` / `db.replace_records` 主要是全量快照语义，不适合做分析查询。
- 需要把“实体表 / 数据库视图 / UI 视图”明确拆层，避免继续把统计需求误塞回 `module_data_table_views` 或 `module_data_resources`。

## 变更范围

- 新增 `module_db_views` 作为数据库视图正式事实源。
- 新增 `db.declare_db_view` / `db.query_view` 运行时能力。
- 视图只登记受控 `SELECT` SQL 模板，不登记完整 `CREATE VIEW`。
- `core:data_table` 新增只读统计表模式，可绑定数据库视图并支持受控过滤、排序、分页。
- 模块卸载时按 `module_db_views` 清理视图对象并在客户端醒目提示。

## 非目标

- 不开放任意 SQL 执行工具。
- 不支持数据库视图写入。
- V1 不实现 `materialized_view`、刷新调度和查询缓存。
- V1 不支持跨模块联表与数据库视图依赖数据库视图。

## 完成判定

- 模块可基于当前模块 `custom_table` 声明宿主管理的数据库视图。
- 视图 SQL 只允许受控 `SELECT` 模板和资源占位引用。
- 宿主可按过滤、排序、分页查询视图。
- `core:data_table` 可只读展示统计视图，且卸载清理有统一事实源。

## 完成记录

- 2026-04-23 已落地 `module_db_views`、`db.declare_db_view`、`db.query_view` 与 `core:data_table(data_source_kind="db_view")` 只读统计表模式。
- V1 当前正式支持 `sql_view`；`materialized_view` 保留在契约中，但运行时明确拒绝。
- 定向回归已通过：`uv run pytest packages/crawler4j/tests/unit/test_core/test_persistence/test_module_data_store.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py packages/crawler4j/tests/unit/test_core/test_mms/test_module_list_widget.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py packages/crawler4j/tests/unit/test_core/test_mms/test_module_data_table_page_views.py packages/crawler4j/tests/unit/test_sdk/test_cli_scaffold.py -q` => `122 passed`，目标文件 `uv run ruff check` 通过。

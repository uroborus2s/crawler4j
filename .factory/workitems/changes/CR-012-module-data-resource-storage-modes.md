# CR-012 模块数据资源统一登记与存储模式扩展

- 状态：DONE
- 类型：CR
- 优先级：P0
- 估算：3.0 人/天
- 关联 ID：`CR-012`, `API-005`, `API-006`, `TASK-026`
- 提出日期：2026-04-23

## 变更动机

- `module_datasets` 当前只适合低频、当前快照型数据；即使底层已按 record 逐行持久化，公开写入语义仍是 `db.replace_records` 全量覆盖。
- 账号表这类稳定数据需要标准化 `run_status` 与 `record_status`，并需要稳定 `record_key` 承载原子占用、释放和状态更新。
- 计费审计、运行审计等高频计算型数据需要模块独立物理表，不能继续挤进统一 `module_datasets`。
- 模块卸载时需要统一列出并清理所有模块数据资源，让客户端给出醒目的风险提示。

## 变更范围

- 新增统一数据资源登记表 `module_data_resources`，统一登记 `managed_dataset` 与 `custom_table` 两种存储模式。
- `module_datasets` 升级为支持 `record_key`、`run_status`、`record_status` 的托管数据记录表。
- `module_data_table_views` 继续只承担 UI 视图 schema，不作为数据生命周期事实源。
- 自定义表使用受控物理表名 `module_name_resource_id`，由资源登记中的 `schema_version` / `schema_json` / `indexes_json` 驱动真实实体表创建、读写校验与卸载清理。
- SDK / Core / Hosted UI 支持在数据表 schema 中声明 `storage_mode`、`resource_id`、`record_key_field` 与 `cleanup_policy`。
- 卸载模块时基于 `module_data_resources` 统一清理数据并在客户端提示风险。

## 非目标

- 本轮不开放任意 SQL 执行工具。
- 本轮不实现数据库视图、聚合查询 DSL 或物化统计表；先把自定义实体表和生命周期闭环落稳。
- 本轮不迁移既有业务模块数据到自定义表；迁移脚本单独评估。

## 完成判定

- `managed_dataset` 与 `custom_table` 都会登记到 `module_data_resources`。
- 低频账号类 dataset 可通过 `record_key`、`run_status`、`record_status` 表达稳定身份、运行占用与业务状态。
- 高频自定义表由宿主按声明 schema/indexes 受控创建和清理，卸载时不会遗留无登记物理表。
- SDK check、Core runtime、MMS 数据表页、持久层和文档均同步到新契约。

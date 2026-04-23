# TASK-026 实现模块数据资源统一登记与存储模式

- 状态：DONE
- 负责人：Codex
- 优先级：P0
- 估算：3.0 人/天
- 关联 ID：`TASK-026`, `CR-012`, `API-005`, `API-006`

## 目标

- 用一张统一资源登记表管理模块所有业务数据资源。
- 支持 `module_datasets` 托管低频稳定数据，并补齐记录级状态字段。
- 支持模块自定义物理表承载高频、计算型数据。
- 让模块卸载清理和客户端提示有统一事实源。

## 范围

- 持久层：`module_data_resources`、`module_datasets` V3、schema 驱动 custom entity table 生命周期和清理策略。
- 运行时：`db.list_records` / `db.replace_records` 保持兼容，并按资源模式路由。
- SDK / UI schema：`ui.declare_data_table` 支持 `storage_mode`、`resource_id`、`record_key_field`、`cleanup_policy`。
- MMS UI：`core:data_table` 能继续管理托管 dataset，并能通过资源 ID 管理 custom table 的通用记录。
- 卸载：清理配置、托管数据、自定义物理表、视图 schema 和页面 schema，并为客户端风险提示提供可列举资源。
- 测试与文档：补持久层、runtime、SDK check、MMS UI、开发者文档与 `.factory/memory/`。

## 非目标

- 不新增模块任意 SQL 执行能力。
- 不把 `module_data_table_views` 改造成生命周期 manifest。
- 不承诺本轮完成历史业务数据自动迁移。

## 验收标准

- 新库可初始化 `module_data_resources` 与 `module_datasets` V3。
- V2 `module_datasets` 可原地升级到 V3；legacy `records_json` 仍 fail-fast。
- `managed_dataset` 写入会登记资源并 roundtrip `record_key` / `run_status` / `record_status`。
- `custom_table` 会按 `module_data_resources.schema_version/schema_json/indexes_json` 生成受控实体表，读写和卸载清理受 `module_data_resources.cleanup_policy` 控制。
- `ui.declare_data_table` 继续只声明 UI 视图字段；若需要真实实体表列定义，模块需显式调用 `db.declare_data_resource`。
- 定向 pytest 与 ruff 通过。

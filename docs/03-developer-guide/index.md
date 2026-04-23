# 开发者指南

当前模块开发主线只有一套协议：`core-native-v1`。

关键边界：

- Core 是唯一运行时 owner
- 模块运行时代码只依赖 `crawler4j-contracts`
- `crawler4j-sdk` 只保留 CLI、脚手架、校验和开发辅助
- Core 通过扫描模块目录生成 runtime descriptor
- 模块数据契约固定为 `module.yaml.data` + `data/sql` + `data/seeds`
- `managed_dataset` / `custom_table` 都必须先在 `module.yaml.data.resources[]` 注册；未注册资源会直接 fail-fast
- 不保留 `module_runtime.py`、`declare_ui()`、根模块 `run()` 的兼容桥

推荐阅读顺序：

1. [核心概念](./core-concepts.md)
2. [模块结构](./module-structure.md)
3. [快速开始](./quickstart.md)
4. [构建模块](./build-modules.md)
5. [SDK 与 CLI 参考](./reference-sdk-and-cli.md)
6. [Core 能力参考](./reference-core-capabilities.md)
7. [UI 与数据表](./ui-and-data-table.md)
8. [调试](./debugging.md)
9. [交付](./shipping.md)
10. [排障](./troubleshooting.md)

最重要的事实：

- `module.yaml.runtime_api` 必须是 `core-native-v1`
- `module.yaml.data` 必须存在，`resources/views/queries/seeds` 是唯一数据契约入口
- `db.get_record` / `db.list_records` / `db.replace_records` 只能访问已注册 `resource_id`
- `tasks/*.py` 导出 `TASK` 和 `execute`
- `workflows/*.py` 导出 `WORKFLOW` 和 `run`
- `hooks/*.py` 导出 `handle`
- `env_selectors/*.py` 导出 `SELECTOR` 和 `select`
- `pages/*.py` 导出 `PAGE` 和页面处理函数

如果你看到任何 `TaskScript`、`TaskFlow`、`ModuleAssembler`、`module_runtime.py`、`declare_ui()`、`@env_selector(...)`、`db.declare_data_resource(...)`、`db.declare_db_view(...)` 的旧写法，应视为历史资料，而不是当前正式协议。

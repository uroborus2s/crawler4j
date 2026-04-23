# TASK-029 重构共享表格组件 SkyDataTable

- 状态：IN_PROGRESS
- 负责人：Codex
- 优先级：P0
- 估算：4.0 人/天
- 关联 ID：`TASK-029`, `CR-015`, `API-010`

## 目标

- 建立唯一正式共享表格组件 `SkyDataTable`。
- 让宿主表格和模块 Hosted UI 表格统一走“纯 UI 组件 + 外部查询 provider”边界。
- 删除旧表格业务 API 与旧 schema。

## 范围

- 共享组件：重写 `packages/crawler4j/src/ui/components/data_table.py`。
- 组件清理：删除 `packages/crawler4j/src/ui/components/table.py` 与旧 `set_render_callback` 用法。
- 宿主迁移：模块列表、任务列表、环境列表、IP 池、任务详情等正式表格页面统一改用新组件。
- Hosted UI：`hosted_ui.py`、`runtime_capabilities.py`、`managed_page_renderer.py`、`module_data_table_page.py` 切到新 DataTable 契约。
- 测试与文档：补组件、宿主页面、Hosted UI 定向回归，并同步正式文档与 `.factory/memory/`。

## 非目标

- 不兼容旧 `ui.declare_data_table` schema。
- 不保留 `SkyTableWidget` 作为业务可直接使用的组件。
- 不在组件内部实现任何数据库查询。

## 验收标准

- `SkyDataTable` 支持搜索、排序、分页、loading/error/empty、行点击和行级动作。
- 新组件通过统一 `query_requested -> apply_result/apply_error` 契约工作。
- 宿主内部正式表格与模块 Hosted UI 表格全部切到新组件。
- 旧 `SkyDataTable` API 与 `SkyTableWidget` 业务使用全部删除。
- 定向 pytest、acceptance 相关回归与 `ruff check` 通过。

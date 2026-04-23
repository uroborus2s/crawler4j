# CR-015 统一共享表格组件 SkyDataTable

- 状态：IN_PROGRESS
- 类型：CR
- 优先级：P0
- 估算：4.0 人/天
- 关联 ID：`CR-015`, `API-010`, `TASK-029`
- 提出日期：2026-04-23

## 变更动机

- 当前宿主内表格和模块 Hosted UI 表格分裂为两套实现：宿主页面主要使用旧 `SkyDataTable + set_render_callback`，模块页仍直接拼 `SkyTableWidget`。
- 旧表格组件把搜索、分页和渲染回调耦合在同一个实现里，边界不清晰，也缺少正式排序能力。
- 模块表格还没有统一的“查询请求 / 查询结果”契约，无法把搜索、排序、分页收口成纯 UI 组件。
- 需要建立一套正式共享表格组件 `SkyDataTable`，并删除旧表格业务 API 和旧底层业务组件。

## 变更范围

- 重写共享组件 `SkyDataTable`，保留组件名，不保留旧 API。
- 删除旧 `SkyTableWidget` 业务组件与 `SkyDataTable` 的 `set_data` / `set_render_callback` / `add_widget_to_toolbar` 用法。
- 宿主内部正式表格统一迁移到新 `SkyDataTable`。
- `core:data_table` 与 `core:page` 内联 `DataTable` 统一迁移到新组件。
- Hosted UI `DataTable` 契约改为新 schema，不兼容旧字段。
- 同步测试、设计、实施计划、测试计划与 `.factory/memory/`。

## 非目标

- 不保留旧 schema 兼容层。
- 不保留旧 `SkyDataTable` / `SkyTableWidget` 业务 API。
- 不在表格组件内直接查询数据库或调用模块 runtime。
- 本轮不实现数据库视图分析查询；该能力仍由 `CR-014 / TASK-028` 单独推进。

## 完成判定

- 仓库内正式用户可见表格统一使用同一套 `SkyDataTable`。
- `SkyDataTable` 仅负责搜索、排序、分页、行事件和结果渲染，查询由外部 provider / adapter 负责。
- 宿主和模块表格使用统一的查询输入 / 结果输出 / 列定义契约。
- 旧表格组件和旧 schema 解析路径被删除。
- 定向 pytest 与 `ruff check` 通过。

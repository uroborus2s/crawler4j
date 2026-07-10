# CR-019 Hosted UI 行按钮打开页面

- 状态：HUMAN_APPROVED
- 类型：CR
- 优先级：P0
- 关联 ID：`CR-019`, `CR-013`, `TASK-038`
- 提出日期：2026-07-10

## 变更动机

- `DataTable` 整行点击已经支持 `row_action.type="open_page"`，但 `actions` 列中的显式行按钮除 CRUD 外只能调用 `@ui_action`。
- 多选表格需要把整行单击保留给选择；详情导航必须放到“操作”列的显式按钮，避免一次单击同时选择并跳页。

## 需求

- 行按钮 action spec 增加 `type="open_page"`，并复用既有 `page_id` 与受控 `params` 行字段绑定。
- 未声明 `type` 的既有行按钮继续默认调用同名或 `name` 指定的 `@ui_action`。
- 点击详情按钮只导航，不调用 `@ui_action`，也不刷新源表。

## 非目标

- 不改变整行 `row_action` 行为。
- 不改变 `SkyDataTable` 的按钮渲染与信号契约。
- 不增加新的 SDK 静态扫描规则或数据库/API。

## 验收标准

- `actions` 列按钮可用 `type="open_page"` 打开目标页，并从当前行解析 `params`。
- 既有 CRUD 与自定义 `@ui_action` 行按钮回归通过。
- 0.4.0 模块开发文档包含行按钮导航示例。


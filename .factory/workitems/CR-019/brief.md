# Hosted UI DataTable 行按钮 open_page 需求简报

- 项目：crawler4j
- Work item：`CR-019`
- 状态：`requirements_ready`（用户已明确确认采用操作列详情按钮）
- 场景：`change_requirement`
- 版本：`0.1.0`
- 日期：2026-07-10
- 上游：`CR-013`

## 目标与主流程

作为 Hosted UI 用户，我希望多选表格的整行单击只负责选择，并通过“操作”列的详情按钮打开目标页，以免选择和跳转冲突。

模块在行数据的 actions 项中声明 `type="open_page"`、`page_id` 和可选 `params`；Core 点击按钮后从当前行解析参数并调用既有页面导航回调。

## 规则与异常

- 未声明 `type` 时保持既有 `ui_action` 行为。
- `open_page` 不调用 `ui_action`，成功导航后不刷新源表。
- 参数继续只支持既有 `binding` / `value` 受控解析；没有 `params` 时传 `None`。
- CRUD 内置编辑、删除优先级不变。

## 验收标准

- `AC-019-001`：行按钮 `type="open_page"` 能以当前行绑定参数打开目标页。
- `AC-019-002`：点击该按钮不触发同 ID 的 `@ui_action`，也不请求源表刷新。
- `AC-019-003`：未声明 `type` 的自定义行按钮和 CRUD 行按钮行为不变。
- `AC-019-004`：开发者文档给出可复制的 schema 示例。

## baseline 影响分析

- 领域：仅影响 Core MMS Hosted UI renderer。
- 架构：复用既有 DataTable signal、受控参数解析和页面路由，不改变 owner 边界。
- 数据库/API：无影响。
- UI：把 CR-013 的详情导航从整行点击扩展到显式行按钮；不改变表格选择模型。

## 风险、回滚与未决问题

- 风险：错误地把旧行按钮改成强制声明类型；以默认 `ui_action` 回归测试约束。
- 回滚：删除 renderer 的 `open_page` 分支即可，无数据迁移。
- 未决问题：无。


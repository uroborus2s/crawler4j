# TASK-025 实现模块宿主管理页框架 V1

- 状态：DONE
- 负责人：Codex
- 优先级：P0
- 估算：2.0 人/天
- 关联 ID：`TASK-025`, `CR-011`, `API-008`, `REQ-002`, `REQ-003`

## 目标

- 把模块 UI 从旧 `micro_app` / `ui:*` / `QWidget` 注入切换到宿主管理页 schema。
- 让宿主通过 `ui.declare_page` / `ui.declare_data_table` 统一持久化并渲染 hosted page V1。
- 让 SDK CLI、测试夹具和开发者文档同步切到新契约，避免继续生成废弃页面骨架。

## 范围

- `ui_extension.pages[]` manifest 契约、scanner 校验和数据模型改造。
- `ui.declare_page` / `ui.get_page` runtime capability、page schema 存储与 `ManagedPageRenderer`。
- 模块详情页只支持 `core:page:<page_id>` 与 `core:data_table:<view_id>` 两类入口。
- SDK CLI `page create` / `data-table create` / `check full`、unit/integration/acceptance 与开发者文档同步。

## 非目标

- 不保留旧 `ui:*` 兼容层。
- 不支持模块向宿主返回真实 `QWidget`。
- 不扩展 V1 之外的新组件协议或复杂动作类型。

## 验收标准

- `page create` 只生成 `module_runtime.py` 内的 hosted page schema / load handler 骨架，不再创建 `ui/` 页面类。
- `ui.declare_page` 声明的 schema 可被宿主持久化并通过模块详情页真实渲染。
- `Button.action` 只开放 `reload` / `open_page`，`core:data_table` 与 hosted page 可互跳。
- 旧 `micro_app` / `ui:*` 声明会被 scanner / CLI gate 拒绝。
- 定向回归覆盖 Core、SDK、integration、acceptance 与 renderer。

## 完成说明

- 已新增 `ManagedPageRenderer`、`ModuleUIRuntimeBridge`、`module_pages` 持久化表与 `ui.declare_page` / `ui.get_page` 能力。
- `ModuleDetailPage` 已删除旧 `ui_loader` 路径，只消费宿主持久化的 hosted page / data-table 入口。
- SDK CLI `page create` / `data-table create` / `check full` 已统一切到 `ui_extension.pages[] + declare_ui()` 契约。
- 开发者文档、测试计划、实施方案、接口矩阵和 `.factory/memory/` 已同步更新到 hosted UI V1 口径。

# CR-011 模块 UI V1 改为宿主管理页框架

- 状态：DONE
- 类型：CR
- 优先级：P0
- 估算：2.0 人/天
- 关联 ID：`CR-011`, `API-008`, `TASK-025`, `REQ-002`, `REQ-003`
- 提出日期：2026-04-22

## 变更动机

- 旧 `micro_app` / `ui:*` / `PyQt6 QWidget` 注入模型要求宿主直接执行外部 UI 代码，导致 trust gate、allowlist 和兼容层不断膨胀。
- 设计文档 `module-hosted-ui-framework.md` 已明确 V1 必须把模块 UI 收口为宿主管理页 schema，由宿主统一渲染和持久化。
- SDK CLI、模块详情页、测试夹具和开发者文档需要在同一波次同时切到新契约，否则模块作者会继续生成已被宿主废弃的页面骨架。

## 变更范围

- 将模块清单 UI 契约切到 `ui_extension.pages[]`。
- 新增 `ui.declare_page` / `ui.get_page`，并在宿主持久层补齐页面 schema 存储。
- 在模块详情页引入 `ManagedPageRenderer`，只消费 `core:page:<page_id>` 与 `core:data_table:<view_id>`。
- 删除 `micro_app`、`ui:*`、`ui_loader`、trust gate / allowlist / `trusted` 相关运行时路径。
- 同步更新 SDK CLI、验收夹具、开发者文档、测试计划、实施计划与 `.factory/memory/`。

## 非目标

- 本轮不为旧 `ui:*` 页面提供兼容层或自动迁移器。
- 本轮不扩展 V1 以外的新宿主控件集。
- 本轮不为审计事件提供独立通用 UI，仅允许模块用 hosted page 自行组合展示。

## 当前进展

- 已完成：Core MMS / persistence / runtime capability 已切到 hosted page V1。
- 已完成：SDK CLI `page create`、`data-table create`、`check full` 与 acceptance 夹具已切到新契约。
- 已完成：开发者文档、测试计划、实施追踪和 `.factory/memory/` 已同步。
- 待完成：PR 收口与后续真实业务模块接入验证。

## 完成判定

- 模块详情页不再执行外部 `PyQt6` 页面类，只消费宿主持久化的 page/data-table schema。
- SDK CLI 不再生成 `ui/` 页面类骨架，`check full` 也不再依赖 `ui:PageClass`。
- `micro_app`、`ui:*`、trust gate / allowlist / `trusted` 在正式实现和正式文档中已退出当前契约。
- 定向回归已覆盖 Core、SDK、integration、acceptance 与 hosted page renderer。

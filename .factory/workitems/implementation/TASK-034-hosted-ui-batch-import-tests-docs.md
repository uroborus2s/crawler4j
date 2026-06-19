# TASK-034 完成批量导入测试、开发者说明和记忆收口

- 状态：PLANNED
- 负责人：Codex
- 优先级：P1
- 估算：1.5 人/天
- 关联 ID：`TASK-034`, `CR-016`, `REQ-010`, `NFR-010`, `API-019`, `TC-060`

## 目标

- 为 Hosted UI 批量导入建立完整测试入口。
- 同步开发者指南、测试计划、追踪矩阵和 `.factory/memory/`。

## 范围

- 单元测试：schema 规范化、解析限制、脱敏、分发、结果展示。
- 集成 / 验收：模块夹具声明导入按钮，提交 payload，返回结果并跳转明细页。
- 文档：开发者指南、PRD、设计、测试计划、追踪矩阵、memory。

## 非目标

- 不补真实业务模块导入 E2E，除非后续任务单独要求。

## 验收标准

- `TC-060` 覆盖 toolbar schema、Excel/CSV/剪贴板解析、文件大小和最大行数限制、敏感字段脱敏、`@ui_action` / workflow 分发、结果展示和明细页跳转。
- 定向 pytest、acceptance 相关回归、`ruff check` 和 `git diff --check` 通过。
- 正式文档与 `.factory/memory/` 同步到同一口径。

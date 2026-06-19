# TASK-034 完成批量导入测试、开发者说明和记忆收口

- 状态：DONE
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

## 实现记录

- 2026-06-19 已新增 / 扩展测试：
  - Contracts / SDK：toolbar schema 规范化、非法动作拒绝、导入提交 handler / workflow 诊断。
  - Core parser：CSV、剪贴板 TSV、XLSX、手工 JSON、文件类型 / 大小 / 行数限制、重复表头、敏感字段脱敏。
  - Core renderer / ATM：`@ui_action` import payload 分发、workflow 任务创建、批次汇总跳转、`ctx.runtime["import_payload"]` 注入。
- 验证：
  - `uv run pytest packages/crawler4j/tests/unit -q` -> `1031 passed`
  - `uv run ruff check <本轮目标文件>` -> 通过
  - `git diff --check` -> 通过
  - `jq empty .factory/project.json` -> 通过

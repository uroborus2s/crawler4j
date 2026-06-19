# CR-016 Hosted UI 宿主托管批量导入

- 状态：DONE
- 类型：CR
- 优先级：P1
- 估算：8.0 人/天
- 关联 ID：`CR-016`, `REQ-010`, `NFR-010`, `API-019`, `TASK-030`, `TASK-031`, `TASK-032`, `TASK-033`, `TASK-034`
- 提出日期：2026-06-19

## 变更动机

- 模块 Hosted UI 中的账号、Cookie、劳保账号、携游账号等业务表需要批量导入能力，逐条录入效率太低。
- 模块运行时代码不应直接读取本地文件，也不应自行实现桌面文件选择、剪贴板读取和 Excel/CSV 解析。
- 当前 Hosted UI 按钮能力还不能表达页面 / 表格 toolbar 自定义按钮，也不能表达“打开宿主导入弹窗 -> 解析行数据 -> 提交给模块”的复合动作。
- 导入结果需要在宿主侧形成批次汇总，并能跳转到模块页面查看逐条成功 / 失败状态。

## 变更范围

- Hosted UI 页面和 `DataTable` 增加 toolbar 自定义按钮 schema。
- toolbar 按钮支持调用 `@ui_action`、调度 workflow 或打开宿主导入弹窗。
- 宿主导入弹窗支持 Excel/CSV 文件上传和剪贴板批量粘贴，手工 JSON / 表格行录入作为可选增强。
- 宿主负责读取来源、解析行数据、限制文件类型 / 大小 / 最大行数、脱敏敏感字段日志。
- 宿主向模块传递标准 import payload，模块不接收本地文件路径、文件句柄或原始二进制内容。
- 宿主展示模块返回的批次汇总，并可跳转 `import_data_records` 页面查看批次明细。
- 后续“从暂存表导入业务表”需要支持逐条状态展示。

## 非目标

- 不支持除 `.xlsx` / `.csv` 之外的任意文件类型。
- 不让宿主理解具体业务字段含义、去重规则或最终业务落库规则。
- 不强制提供宿主统一业务暂存表；暂存表由模块通过 `@data_table` / `ctx.db` 实现。
- 不把 Hosted UI 用户导入动作接到 `@page_action`。

## 完成判定

- 模块可通过 schema 声明导入按钮并在页面 / 表格 toolbar 中渲染。
- 宿主可解析 `.xlsx/.csv` 和剪贴板文本为标准 import payload。
- `@ui_action` 和 workflow 都能接收导入 payload。
- 宿主能展示 `batch_id/total_rows/staged_rows/failed_rows` 汇总并跳转批次明细页。
- 敏感字段不在宿主日志、错误摘要或任务消息中明文输出。
- `TC-060` 和相关定向回归通过。

## 实现记录

- 2026-06-19 已完成 Contracts / SDK / Core / UI 实现：
  - `Page.toolbar.actions[]` 与 `DataTable.toolbar.actions[]` 支持 `ui_action`、`workflow`、`open_import_dialog`。
  - 宿主新增 `hosted_import.py`，统一解析 `.csv/.xlsx` 文件、剪贴板 TSV/CSV 和手工 JSON，并执行文件类型、文件大小、最大行数、重复表头和敏感字段脱敏约束。
  - `ManagedPageRenderer` 已渲染页面 / 表格 toolbar，导入 payload 可提交给模块 `@ui_action` 或 ATM workflow；workflow payload 会写入 `creation.params.import_payload` 并由 `ExecutionRunner` 提升到 `ctx.runtime["import_payload"]`。
  - 模块返回批次汇总后，宿主展示导入结果，并可携带 `batch_id/target_type` 跳转 `import_data_records` 页面。
- 验证：`uv run pytest packages/crawler4j/tests/unit -q` 通过 `1031 passed`；目标 `ruff check`、`git diff --check` 和 `.factory/project.json` JSON 校验通过。

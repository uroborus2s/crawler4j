# TASK-031 实现宿主导入弹窗与来源解析

- 状态：DONE
- 负责人：Codex
- 优先级：P1
- 估算：2.0 人/天
- 关联 ID：`TASK-031`, `CR-016`, `REQ-010`, `NFR-010`, `API-019`, `TC-060`

## 目标

- 提供宿主导入弹窗。
- 支持 `.xlsx/.csv` 文件上传和剪贴板批量粘贴。
- 在宿主侧完成解析、预览、限制和敏感字段脱敏。

## 范围

- UI：文件选择、剪贴板粘贴、预览、列映射、提交确认。
- 解析：Excel、CSV、剪贴板 TSV/CSV 文本。
- 限制：文件类型、文件大小、最大行数、表头重复 / 缺失。
- 安全：日志脱敏，不输出原始 rows 和敏感值。

## 非目标

- 不做业务字段校验和业务去重。
- 不落地原始文件。
- 手工 JSON / 表格行录入为可选增强，不阻塞主链路。

## 验收标准

- `.xlsx/.csv` 可被解析为标准 import payload rows。
- 剪贴板表格文本可被解析为标准 import payload rows。
- 超出文件类型、文件大小或最大行数限制时提交前阻断。
- 解析错误显示来源、行号或列名等可定位信息。
- token/cookie/password/secret 等敏感字段不在日志中明文出现。

## 实现记录

- 2026-06-19 已新增宿主导入解析层 `src.core.mms.ui.hosted_import`：
  - 支持 `.csv`、`.xlsx` 首个工作表、剪贴板 CSV/TSV 和手工 JSON 对象数组。
  - 统一生成 `source_type/source_name/target_type/rows[]` 标准 payload，保留 `source_row_no`、`business_key`、标准化 `payload` 与 `raw_payload`。
  - 执行 `.xlsx/.csv` 文件类型、文件大小、最大行数、重复 / 空表头校验。
  - `redact_import_payload()` 会递归屏蔽 `token/cookie/password/secret/authorization/credential/passwd` 等字段。
- 宿主弹窗 `HostedImportDialog` 已接入文件选择、剪贴板粘贴和可选手工 JSON 标签页；模块只接收解析后的 JSON-compatible payload。
- 验证：`test_hosted_import.py` 覆盖 CSV、TSV、最小 XLSX、手工 JSON、限制错误和脱敏。

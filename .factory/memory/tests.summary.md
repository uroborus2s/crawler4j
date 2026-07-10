# Tests Summary

更新时间：2026-07-10。只保留最近验证门，不复制完整测试历史。

## 最近验证

- 全量 unit：`uv run pytest packages/crawler4j/tests/unit -q -p no:cacheprovider` -> `1135 passed`。
- 版本/打包聚焦回归：`65 passed`。
- 静态与工程门：Ruff、`uv lock --check`、`.factory/project.json` JSON、docs 校验、`git diff --check` -> passed。
- 运行与产物门：UI smoke、root build、wheel METADATA 版本核对 -> passed。
- SDK / Contracts：构建、PyPI 发布、JSON API 哈希核对、隔离安装 -> passed。

## 未闭环项

- `ctrip` 真实站点 DevLink / ZIP E2E。
- Windows 真机签名、安装、自更新。
- 0.4.30 桌面安装包和完整跨平台交付批次。

## 证据索引

- 客户端版本：`.factory/workitems/TASK-039/evidence/verification.md`
- Contracts / SDK 发布：TASK-037 ledger 与 release evidence
- Hosted UI 批量编辑：`.factory/workitems/CR-018/evidence/`
- 行按钮：`.factory/workitems/CR-019/evidence/`
- 正式测试事实源：`docs/04-project-development/06-testing-verification/`

历史测试命令和逐项结果默认不读；需要时按 work item evidence 精确回源。

# Tests Summary

更新时间：2026-07-15。只保留最近验证门，不复制完整测试历史。

## 最近验证

- CR-022 renderer 视觉增量：共享 label/input 物理列 TDD RED `4 failed`，GREEN `4 passed`；独立 review 补充超大 gap geometry 与合法中等 gap 保留两组 RED/GREEN；最终 renderer `36 passed`，七文件 `202 passed`，SDK/MMS/UI `586 passed`，全仓 Ruff/lock/docs/diff/scope 通过；全量 `1234 passed`，另有 13 项既有沙箱/只读 DB 环境基线。证据：`.factory/workitems/CR-022/evidence/shared-form-columns-final-verification.md`。
- CR-022 隐藏式滚动增量：TDD RED `1 failed`、GREEN `1 passed`；renderer `36 passed`、七文件 `202 passed`、SDK/MMS/UI `586 passed`，Ruff/lock/docs/diff 通过；全量 `1234 passed`，另有相同 13 项既有沙箱/只读 DB 环境基线。证据：`.factory/workitems/CR-022/evidence/hidden-form-scrollbar-final-verification.md`。
- CR-022 Hosted UI Form：目标集双方 `199 passed`；SDK/MMS/UI 相关套件 `583 passed`；全量 unit `1231 passed`、另有 13 项稳定的范围外沙箱/只读 DB 基线失败；全仓 Ruff、lock、docs、diff gate 通过。独立 review `approved`（98/100）。
- CR-020 目标测试：`122 passed`；REM/ATM 相邻回归：`517 passed`。
- 全量 unit：`uv run pytest packages/crawler4j/tests/unit -q -p no:cacheprovider` -> `1191 passed`。
- CR-020 实际接口：生产 `VirtualBrowserClient` 在一次性环境完成 A+B、仅 A、空集合三轮写入，证明全量替换、删除遗漏项和清空语义；环境已删除。
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
- 环境 Cookie 原子能力：`.factory/workitems/CR-020/evidence/`
- Hosted UI 字段 change / Form reset / 多列布局：`.factory/workitems/CR-022/evidence/`
- 正式测试事实源：`docs/04-project-development/06-testing-verification/`

历史测试命令和逐项结果默认不读；需要时按 work item evidence 精确回源。

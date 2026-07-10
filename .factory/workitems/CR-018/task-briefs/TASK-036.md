# 任务简报

## 工作项

- 工作项：`CR-018`
- 任务：`TASK-036`
- 状态：`approved`
- 上游计划：`.factory/workitems/CR-018/plan.md`
- 流水账：`.factory/workitems/CR-018/ledger.jsonl`

## 目标

交付 Hosted UI 当前页多选批量编辑通用能力，使 `managed_dataset` 模块 handler 收到保序去重的 `primary_keys` 与空白 update 表单 `payload`，并保持旧模块兼容。

## 输入

- 已批准规格：用户指定的 bulk update request。
- 必读文件：`hosted_ui.py`、`v2_scanner.py`、`managed_page_renderer.py` 及三个目标测试文件。
- 可选参考：`data_table.py` 和现有 CRUD / batch import 测试。

## 允许修改

- `packages/crawler4j-contracts/src/crawler4j_contracts/hosted_ui.py`
- `packages/crawler4j-sdk/src/v2_scanner.py`
- `packages/crawler4j/src/core/mms/ui/managed_page_renderer.py`
- 对应目标测试、`docs/04-project-development/`、`.factory/workitems/CR-018/` 与相关 `.factory/memory/`。

## 禁止修改

- 与本任务无关的文件和用户已有脏改动。
- `managed_dataset` 物理表结构、`ctx.db` API 或业务模块。
- 跨分页选择、批量删除或业务分组逻辑。

## 实施步骤

1. 按 plan 的任务 1 / 2 分别写 RED 测试并确认失败。
2. 用现有 schema、scanner、表单和 action 调用链完成最小 GREEN。
3. 运行定向、邻近和全量 unit；执行目标 ruff 与 diff check。
4. 独立 review 后写 evidence、implementation report、ledger 和 memory。

## 失败断言

- 缺测试设计、异步路径调用 `exec()`、Core 直接写数据库、单条动作在多选时默取首行或出现占位语均失败。

## 验证命令

```bash
uv run pytest packages/crawler4j/tests/unit/test_sdk/test_hosted_ui_card.py packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py -q -p no:cacheprovider
QT_QPA_PLATFORM=offscreen uv run pytest packages/crawler4j/tests/unit/test_ui/test_data_table.py packages/crawler4j/tests/unit/test_core/test_mms/test_managed_page_renderer.py -q -p no:cacheprovider
```

期望输出：目标测试全部通过，无新增 warning / error。

## 输出报告

- 验证证据：`.factory/workitems/CR-018/evidence/verification.md`
- 实现报告：`.factory/workitems/CR-018/reports/implementation.md`
- 评审：`.factory/workitems/CR-018/reviews/code-review.md`
- 流水账：`.factory/workitems/CR-018/ledger.jsonl`

## 完成口径

实现者只能写 `ready_for_review`；`approved` 必须来自独立评审。

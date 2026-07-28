# TASK-044 任务简报

## 工作项

- 工作项：`CR-024`
- 任务：`TASK-044`
- 状态：`verification_passed`
- 类型：`implementation`
- 流水账：`.factory/workitems/CR-024/ledger.jsonl`

## 目标

新增标准 Cheese 自动化示例模块，内置 Android 设置页冒烟脚本，并验证模块完整校验、打包和 ZIP 资源包含关系。

## 允许修改

- `.factory/workitems/CR-024/**`
- `.factory/memory/agent-session.md`
- `.factory/memory/current-state.md`
- `.factory/memory/tasks.summary.md`
- `.factory/memory/tests.summary.md`
- `.factory/memory/review-ledger.jsonl`
- `examples/cheese_automation/**`
- `packages/crawler4j/tests/integration/test_sdk_cli_module_mode.py`

## 禁止修改

- crawler4j Core、Contracts、SDK 公共契约与依赖
- 其他 work item 和用户改动
- 真实设备、外部发布、push、PR、merge

## 当前 Gate

`local_commit`

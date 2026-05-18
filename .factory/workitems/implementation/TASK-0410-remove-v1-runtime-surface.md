# TASK-0410 清理 v1 runtime surface 与兼容代码

- 状态：IN_PROGRESS
- 负责人：全开发团队
- 优先级：P0
- 估算：持续门禁
- 关联 ID：`TASK-0410`, `TASK-0400`, `REQ-0400`, `API-012`

## 目标

- 0.4.0 不兼容 0.3.0。
- 与 v2 架构冲突的 v1 代码、测试和文档口径一律清理。
- 不做兼容适配层。

## 当前记录

- `crawler4j-contracts` 根导出已移除 `TaskSpec` / `WorkflowSpec` / `EnvSelectorSpec`。
- legacy spec 暂保留在 `crawler4j_contracts.specs`，仅供 Core 内部旧代码清理过渡与迁移工具引用；后续收口必须继续删除运行路径依赖。
- SDK CLI 主路径已清理旧 `task` 别名、旧 manifest data resource/view/seed 命令、Hook/env-selector 脚手架和 workflow 默认配置写入入口。
- SDK v2 `check full` 的 legacy AST 扫描范围已收口到 v2 runtime surface：模块根 `__init__.py` 与 `interfaces/objects/workflows/tasks/data`。
- Core `ModuleScanner` / DevLink / install preflight 已切到 `core-native-v2`，不再要求 `module.yaml.data/workflows/default_workflow`。
- Acceptance 中旧 `env-selector` enrich helper 和 `core-native-v1` 断言已迁移为 v2 scaffold/package 语义。

## 验证记录

- `uv run pytest packages/crawler4j/tests/acceptance packages/crawler4j/tests/unit/test_sdk packages/crawler4j/tests/unit/test_core/test_mms/test_runtime_descriptor_v2.py packages/crawler4j/tests/unit/test_core/test_mms/test_object_container_v2.py -q`：202 passed
- `uv run ruff check packages/crawler4j-contracts/src packages/crawler4j-sdk/src packages/crawler4j/src/core/mms packages/crawler4j/tests/unit/test_sdk packages/crawler4j/tests/unit/test_core/test_mms packages/crawler4j/tests/acceptance`：passed
- `git diff --check`：passed

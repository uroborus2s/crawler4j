# TASK-0404 建立 SDK v2 CLI 模板与 manifest lock

- 状态：DONE
- 负责人：Codex SDK worker
- 优先级：P0
- 估算：2.0 人/天
- 关联 ID：`TASK-0404`, `TASK-0400`, `REQ-0400`, `API-012`, `TC-0400-003`

## 目标

- `module init` 生成 `core-native-v2` 标准目录和装饰器模板。
- 新增/收口 interface、component、page action、data table、data view 与 manifest lock 命令。
- 清理旧 task/workflow parameters/data manifest 兼容校验。

## 当前状态

- 已完成 SDK v2 CLI 模板与 manifest lock 最小闭环。
- `module init` 生成 `core-native-v2` 标准目录：`interfaces/`、`objects/`、`workflows/`、`tasks/`、`data/`、`pages/`、`tests/`、`.crawler4j/`。
- 默认脚手架生成示例 `@interface`、`@component`、`@workflow`、`@page_action`、`@data_table`、`@data_view`，并立即写入 `.crawler4j/manifest.lock.json`。
- `module.yaml` 不再写入 `default_workflow`、`workflows`、`data`、`objects`、`interfaces`、`tasks` 等 v1 运行能力字段。
- `check full` 使用 v2 scanner、Hosted page 校验和 manifest lock 一致性校验；lock 缺失或过期会阻断 `check full`、`package build`、`package verify`。
- CLI scaffold 单测已按 0.4.0 v2 语义重写，删除 v1 兼容断言。
- 旧 `task` CLI 别名、旧 `data resource/view/seed`、`env-selector`、`hook` 和 workflow 默认配置写入入口已从 parser 与实现中清理；`templates.py` 不再保留 Hook/env-selector 脚手架模板。

## 验证记录

- `uv run pytest packages/crawler4j/tests/unit/test_sdk/test_cli_scaffold.py -q`：13 passed
- `uv run pytest packages/crawler4j/tests/unit/test_sdk/test_v2_scanner_diagnostics.py packages/crawler4j/tests/unit/test_sdk/test_contracts_v2_decorators.py packages/crawler4j/tests/unit/test_sdk/test_contracts_exports.py -q`：16 passed
- `uv run pytest packages/crawler4j/tests/unit/test_sdk -q`：164 passed
- `uv run pytest packages/crawler4j/tests/acceptance packages/crawler4j/tests/unit/test_sdk packages/crawler4j/tests/unit/test_core/test_mms/test_runtime_descriptor_v2.py packages/crawler4j/tests/unit/test_core/test_mms/test_object_container_v2.py -q`：202 passed
- `uv run ruff check packages/crawler4j-sdk/src/cli/commands.py packages/crawler4j-sdk/src/cli/templates.py packages/crawler4j/tests/unit/test_sdk/test_cli_scaffold.py`：passed
- `git diff --check`：passed

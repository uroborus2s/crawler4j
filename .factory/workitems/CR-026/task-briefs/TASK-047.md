# TASK-047 宿主注册、配置与 UI/ATM 集成

## 工作项

- 工作项：`CR-026`
- 任务：`TASK-047`
- 状态：`active`
- 优先级：`P0`
- 任务层级：`cross_cutting`
- 关联目标：`CR-026-REQ-001`、`CR-026-REQ-005`、`CR-026-REQ-006`、`CR-026-REQ-007`
- 强关系：`IMPLEMENTS`
- 上游计划：`.factory/workitems/CR-026/plan.md`
- 流水账：`.factory/workitems/CR-026/ledger.jsonl`

## 目标

把 `hubstudio` 接入 Provider registry、ConfigCenter、ExternalApp、REM 管理、已有环境导入、ATM 配置和 REM UI，不改旧 Provider 默认值、环境行或列 schema。

## 允许修改

- `packages/crawler4j/src/core/rem/provider.py`
- `packages/crawler4j/src/core/rem/__init__.py`
- `packages/crawler4j/src/core/rem/manager.py`
- `packages/crawler4j/src/core/rem/import_job_service.py`
- `packages/crawler4j/src/core/rem/ui/env_list_widget.py`
- `packages/crawler4j/src/core/rem/ui/edit_env_dialog.py`
- `packages/crawler4j/src/core/atm/ui/run_profile_dialog.py`
- `packages/crawler4j/src/core/system/config_center.py`
- `packages/crawler4j/src/core/system/external_app_service.py`
- `packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py`
- `packages/crawler4j/tests/unit/test_core/test_rem/test_import_job_service.py`
- `packages/crawler4j/tests/unit/test_core/test_rem/test_env_list_widget.py`
- `packages/crawler4j/tests/unit/test_core/test_rem/test_edit_env_dialog.py`
- `packages/crawler4j/tests/unit/test_core/test_atm/test_run_profile_dialog.py`
- `packages/crawler4j/tests/unit/test_core/test_system/test_config_center.py`
- `packages/crawler4j/tests/unit/test_core/test_system/test_external_app_service.py`

## 禁止修改

- `packages/crawler4j/src/core/rem/hubstudio_provider.py`
- `packages/crawler4j/tests/unit/test_core/test_rem/test_hubstudio_provider.py`
- 其他文件、公共环境接口、数据库和环境列表列 schema。

## 实施步骤

1. 先新增 HubStudio 注册、配置、就绪检查、导入类型、UI 选项和限制提示失败测试。
2. 用现有常量集合、枚举、ConfigSpec 和显示映射完成最小实现。
3. `hubstudio -> EnvType.VIRTUAL_BROWSER`；不新增 EnvType。
4. HubStudio 缓存按钮可见；location repair 仍只属于 VirtualBrowser；刷新指纹对话标明厂商限制。
5. 运行 task brief 指定测试与 Ruff。

## 验证命令

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py packages/crawler4j/tests/unit/test_core/test_rem/test_import_job_service.py packages/crawler4j/tests/unit/test_core/test_rem/test_env_list_widget.py packages/crawler4j/tests/unit/test_core/test_rem/test_edit_env_dialog.py packages/crawler4j/tests/unit/test_core/test_atm/test_run_profile_dialog.py packages/crawler4j/tests/unit/test_core/test_system/test_config_center.py packages/crawler4j/tests/unit/test_core/test_system/test_external_app_service.py -q
uv run ruff check packages/crawler4j/src/core/rem/provider.py packages/crawler4j/src/core/rem/manager.py packages/crawler4j/src/core/rem/import_job_service.py packages/crawler4j/src/core/rem/ui/env_list_widget.py packages/crawler4j/src/core/rem/ui/edit_env_dialog.py packages/crawler4j/src/core/atm/ui/run_profile_dialog.py packages/crawler4j/src/core/system/config_center.py packages/crawler4j/src/core/system/external_app_service.py
```

## 完成口径

返回 `DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT`，列出实现、真实测试结果、文件和 concerns；不自批 approved。

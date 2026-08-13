# TASK-048 HubStudio 集中质量门

## 工作项

- 工作项：`CR-026`
- 任务：`TASK-048`
- 状态：`draft`
- 优先级：`P0`
- 任务层级：`system`
- 关联目标：`CR-026`
- 强关系：`DEPENDS_ON`
- 依赖：`TASK-046`、`TASK-047`
- 上游计划：`.factory/workitems/CR-026/plan.md`
- 流水账：`.factory/workitems/CR-026/ledger.jsonl`

## 目标

对完整 HubStudio 候选执行一次集中测试和独立只读代码审核，产出唯一 evidence/report/review-input。

## 允许修改

- 测试者和 reviewer：不允许修改源码/测试。
- 主控收口：`.factory/workitems/CR-026/evidence/**`、`reports/**`、`reviews/**`、`ledger.jsonl`。

## 验证

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_hubstudio_provider.py packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py packages/crawler4j/tests/unit/test_core/test_rem/test_import_job_service.py packages/crawler4j/tests/unit/test_core/test_rem/test_env_list_widget.py packages/crawler4j/tests/unit/test_core/test_rem/test_edit_env_dialog.py packages/crawler4j/tests/unit/test_core/test_atm/test_run_profile_dialog.py packages/crawler4j/tests/unit/test_core/test_system/test_config_center.py packages/crawler4j/tests/unit/test_core/test_system/test_external_app_service.py -q
uv run ruff check packages/crawler4j/src/core/rem/hubstudio_provider.py packages/crawler4j/src/core/rem/provider.py packages/crawler4j/src/core/rem/manager.py packages/crawler4j/src/core/rem/import_job_service.py packages/crawler4j/src/core/rem/ui/env_list_widget.py packages/crawler4j/src/core/rem/ui/edit_env_dialog.py packages/crawler4j/src/core/atm/ui/run_profile_dialog.py packages/crawler4j/src/core/system/config_center.py packages/crawler4j/src/core/system/external_app_service.py packages/crawler4j/tests/unit/test_core/test_rem/test_hubstudio_provider.py
git diff --check
```

## 审核要点

- `containerCode/browserID` 未混用。
- 旧 Provider 行为、默认选择、RunProfile 序列化和环境列表列 schema 未变。
- API 失败不被吞掉，敏感数据不进入日志。
- Cookie 时间/SameSite/布尔转换、代理协议映射和 CDP URL 正确。
- 厂商限制被明确标记，未伪造指纹回读或 location 修复。

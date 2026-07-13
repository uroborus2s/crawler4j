# TASK-040 任务简报

## 工作项

- 工作项：`CR-020`
- 任务：`TASK-040`
- 状态：`ready_for_review`
- 上游计划：`.factory/workitems/CR-020/plan.md`
- 流水账：`.factory/workitems/CR-020/ledger.jsonl`

## 目标

实现并验证 full runtime `env.cookie.ensure`：Core 对当前环境串行完成 Cookie 持久化、必要重启、CDP 重连、运行态验证和 TaskContext/tools 回绑，且不向模块泄漏 VirtualBrowser API 或敏感值。

## 输入

- 需求：`.factory/workitems/CR-020/brief.md`
- 计划：`.factory/workitems/CR-020/plan.md`
- 必读文件：`runtime_capabilities.py`、`rem/manager.py`、`rem/provider.py`、`rem/handle.py` 及四个目标测试文件。
- 必读实测证据：`.factory/workitems/CR-020/evidence/virtualbrowser-cookie-api-probe.md`。

## 允许修改

- `.factory/workitems/CR-020/**`
- `.factory/workitems/changes/CR-020-env-cookie-ensure.md`
- `.factory/workitems/implementation/TASK-040-env-cookie-ensure.md`
- `packages/crawler4j/src/core/atm/runtime_capabilities.py`
- `packages/crawler4j/src/core/rem/cookie_service.py`
- `packages/crawler4j/src/core/rem/manager.py`
- `packages/crawler4j/src/core/rem/provider.py`
- `packages/crawler4j/src/core/rem/handle.py`，仅在 CDP 关闭/重连需要时修改
- 四个目标测试文件
- `docs/03-developer-guide/v0.4.0/reference-core-capabilities.md`
- `docs/04-project-development/04-design/api-design.md`
- `.factory/memory/api.summary.md`
- `.factory/memory/tasks.summary.md`

## 禁止修改

- 模块代码、SDK scanner、module.yaml 和 manifest 契约。
- 与本任务无关的文件或用户已有脏改动。
- 将 VirtualBrowser API、API Key 或 Cookie value 暴露到模块、日志、异常或结果。

## 实施步骤

1. 按计划写失败测试并记录 RED。
2. 实现 Cookie 完整集合 helpers 与 VirtualBrowser 实测 API 适配。
3. 实现按环境加锁的 REM ensure 编排和严格停止等待。
4. 注册 full runtime 工具并回绑 TaskContext/tools。
5. 运行目标、相邻、全量测试和 Ruff。
6. 同步文档、memory、证据、报告和 ledger。
7. 生成任务评审输入；实现者只写 `ready_for_review`。

## 验证命令

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_env_cookie_service.py packages/crawler4j/tests/unit/test_core/test_rem/test_virtualbrowser_client.py packages/crawler4j/tests/unit/test_core/test_rem/test_provider.py packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py -q -p no:cacheprovider
uv run pytest packages/crawler4j/tests/unit/test_core/test_rem packages/crawler4j/tests/unit/test_core/test_atm -q -p no:cacheprovider
uv run ruff check packages/crawler4j/src/core/rem packages/crawler4j/src/core/atm/runtime_capabilities.py packages/crawler4j/tests/unit/test_core/test_rem packages/crawler4j/tests/unit/test_core/test_atm/test_runtime_capabilities.py
uv run pytest packages/crawler4j/tests/unit -q -p no:cacheprovider
git diff --check
```

期望：全部命令 exit code 0，pytest failures/errors 为 0。

## 输出报告

- 验证证据：`.factory/workitems/CR-020/evidence/TASK-040.md`
- 实现报告：`.factory/workitems/CR-020/reports/TASK-040.md`
- 评审输入：`.factory/workitems/CR-020/reviews/TASK-040-review-input.md`
- 流水账：`.factory/workitems/CR-020/ledger.jsonl`

## 完成口径

实现者只能写 `ready_for_review`；`approved` 必须来自独立评审。

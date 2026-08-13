# TASK-046 HubStudio API 适配与 Provider

## 工作项

- 工作项：`CR-026`
- 任务：`TASK-046`
- 状态：`active`
- 优先级：`P0`
- 任务层级：`requirement`
- 关联目标：`CR-026-REQ-002`、`CR-026-REQ-003`、`CR-026-REQ-004`、`CR-026-NFR-001`
- 强关系：`IMPLEMENTS`
- 上游计划：`.factory/workitems/CR-026/plan.md`
- 流水账：`.factory/workitems/CR-026/ledger.jsonl`

## 目标

新增独立 HubStudio Client/Provider，通过 mock API 契约测试证明生命周期、管理操作、Cookie、导入和稳定/运行时 ID 隔离。

## 必读

- `.factory/workitems/CR-026/task-briefs/TASK-046.md`
- `packages/crawler4j/src/core/rem/provider.py` 中 `BaseProvider` 和现有 Provider 行为
- `packages/crawler4j/src/core/rem/handle.py`
- `packages/crawler4j/src/core/rem/models.py`
- HubStudio 官方端点：env list/create/update/proxy/cookie/delete/cache/refresh 及 browser start/stop/status

## 允许修改

- `packages/crawler4j/src/core/rem/hubstudio_provider.py`
- `packages/crawler4j/tests/unit/test_core/test_rem/test_hubstudio_provider.py`

## 禁止修改

- 其他所有文件。
- 不改公共环境接口、schema 或旧 Provider。
- 不在日志/异常中包含 API Key、代理密码或 Cookie 内容。

## 实施步骤

1. 先写失败测试，覆盖 API 校验和 ID 隔离。
2. 实现单模块 Client/Provider，复用 `BaseProvider` 与 `BrowserHandle.safe_connect()`。
3. 对无缓存 `browserID` 的缓存清理路径，临时启动后关闭，再清理指定 `browserID`。
4. 完成定向 pytest 和 Ruff。

## 验证命令

```bash
uv run pytest packages/crawler4j/tests/unit/test_core/test_rem/test_hubstudio_provider.py -q
uv run ruff check packages/crawler4j/src/core/rem/hubstudio_provider.py packages/crawler4j/tests/unit/test_core/test_rem/test_hubstudio_provider.py
```

## 完成口径

返回 `DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT`，列出实现、真实测试结果、文件和 concerns；不自批 approved，不生成独立 evidence/report/review input。

# TASK-037 发布 Contracts 0.4.3 与 SDK 0.4.4

- 状态：DONE
- 负责人：Codex
- 优先级：P0
- 关联 ID：`TASK-037`, `CR-018`, `TASK-036`, `REQ-012`, `API-021`, `TC-069`

## 目标

- 将 `crawler4j-contracts` 升级到 `0.4.3`，将 `crawler4j-sdk` 升级到 `0.4.4`。
- SDK 依赖下限同步到 `crawler4j-contracts>=0.4.3,<0.5.0`。
- 完成测试、构建、产物元数据检查，并按 Contracts -> SDK 顺序发布到 PyPI。

## 范围

- Contracts / SDK 版本、依赖范围、README、锁文件与发布事实源。
- 发布前定向/SDK 回归、Ruff、构建、wheel/sdist 校验和 PyPI 在线验证。
- 根应用保持现有 `0.4.29`，本任务不构建或发布客户端。

## Gate

- PyPI 官方 JSON API 确认目标版本未占用。
- Contracts 发布并在线可见后，才允许发布 SDK。
- 只有两个目标版本都在线可见，才能标记完成。

## 当前证据

- 全量 unit `1134 passed`，Ruff、lock、project JSON、docs 与 diff gate 通过。
- 两个包的 wheel/sdist 已构建，版本和 SDK 依赖元数据符合预期。
- 两个包的 `uv publish --dry-run` 与正式发布均通过；PyPI wheel/sdist 哈希与本地一致。
- 隔离环境从 PyPI 安装 SDK 0.4.4，自动解析 Contracts 0.4.3 且两个包均可导入。

# TASK-042 发布 CR-022 Contracts / SDK 并升级客户端

- 状态：PYPI_PUBLISHED_PENDING_REMOTE_PUSH
- 负责人：Codex
- 优先级：P0
- 关联 ID：`TASK-042`, `CR-022`, `REQ-013`, `API-023`

## 目标

- 将 `crawler4j-contracts` 升级到 `0.4.4`，将 `crawler4j-sdk` 升级到 `0.4.5`。
- SDK 与根应用的 Contracts 依赖下限同步到 `crawler4j-contracts>=0.4.4,<0.5.0`。
- 将客户端 / Core 源码版本升级到 `crawler4j 0.4.39` 并完成 root wheel/sdist 构建。
- 完成测试、构建、产物元数据检查，并按 Contracts -> SDK 顺序发布到 PyPI。
- 提交并推送当前 `0.4.0` 分支全部本地提交到 `origin/0.4.0`。

## 范围

- Contracts / SDK / 客户端版本、依赖范围、README、锁文件与发布事实源。
- Contracts / SDK PyPI wheel/sdist 发布、在线哈希与隔离安装验证。
- root `crawler4j` 只升级版本并构建；PyPI 当前不存在该项目，本任务不擅自创建新 PyPI 命名空间。
- 不创建 Git tag、GitHub Release、macOS/Windows 安装包或 Sparkle/Velopack 发布资产。

## Gate

- PyPI 官方 JSON API 确认 `crawler4j-contracts 0.4.4` 与 `crawler4j-sdk 0.4.5` 未占用。
- Contracts 发布并在线可见、文件哈希匹配后，才允许发布 SDK。
- SDK 在线依赖必须包含 `crawler4j-contracts>=0.4.4,<0.5.0`。
- 两包隔离安装通过、release commit 完成后，才允许推送远端分支。

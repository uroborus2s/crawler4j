# TASK-039 升级客户端 0.4.30 并推送

- 状态：VERIFICATION_PASSED / READY_TO_PUSH
- 负责人：Codex
- 优先级：P0
- 关联 ID：`TASK-039`, `TASK-004`, `CR-018`, `CR-019`

## 目标

- 将根应用 / 运行时源码版本从 `0.4.29` 提升到 `0.4.30`。
- 同步锁文件、README、发布文档与 `.factory` 当前版本事实。
- 运行版本、全量 unit、构建与文档门禁，使用中文提交并推送 `0.4.0` 分支。

## 边界

- SDK 保持 `0.4.4`，Contracts 保持 `0.4.3`。
- 不构建或上传 macOS / Windows 桌面安装包，不创建 tag、GitHub release 或 PR。

## 验证结果

- 版本服务与打包配置：`65 passed`。
- 完整 unit：`1135 passed`。
- 全仓 Ruff、lock、project JSON、docs-stratego、UI smoke 和 diff check 通过。
- root wheel/sdist 构建通过；wheel `Version` 与内嵌 README 均为 `0.4.30`。

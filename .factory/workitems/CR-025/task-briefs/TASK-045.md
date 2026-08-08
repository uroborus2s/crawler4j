# TASK-045 环境候选异步与候选上下文

- work_item：`CR-025`
- priority：`P0`
- task_scope：`cross_cutting`
- relations：`IMPLEMENTS REQ-017, REQ-018, REQ-019, REQ-020, REQ-021, REQ-022, NFR-015`
- 状态：`client_version_alignment_authorized`
- 依赖：用户已确认的需求输入

## 验收结果

- 旧同步候选完全兼容。
- async/awaitable 候选只调用一次并在超时边界内完成。
- 结构化 context 经 JSON/64 KiB 校验后只注入最终 workflow。
- 固定环境、创建环境、旧候选无 context；空候选不启动 workflow。
- SDK manifest 与包验收接受 async candidates，cleanup 仍只接受 sync。
- Contracts/SDK 源码 patch 版本分别为 `0.4.5` / `0.4.6`，SDK 与模块最低 Contracts 版本为 `0.4.5`。
- 根应用 / 客户端源码 patch 版本为 `0.4.41`，root wheel/sdist 构建通过。

## 允许与禁止

按 `plan.md` 授权执行包执行；不得修改业务模块。用户已授权验证通过后提交、创建并合并 PR 到 `main`，并发布 Contracts `0.4.5` 与 SDK `0.4.6`。

## 验证

先运行新增定向 pytest 取得 RED；实现后运行同组 GREEN。批次末运行完整 unit、相关 integration/acceptance、ruff、lock、JSON、docs 与 diff check。仓库未配置 mypy，不虚构 type-check gate。

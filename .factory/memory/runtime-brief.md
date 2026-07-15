# 项目压缩运行卡

- 更新时间：2026-07-15
- 项目：crawler4j
- 当前阶段：IMPLEMENTATION
- 当前模式：Default
- 技术栈：Python + uv + crawler4j Core + Contracts + SDK CLI
- 记忆入口：`.factory/memory/memory-index.md`
- 当前版本：根应用 / runtime `0.4.39`；SDK `0.4.5` 发布候选；Contracts `0.4.4` 发布候选
- 当前正式 Git tag：`v0.2.0`

## 当前工作状态

- `TASK-042`：Contracts 0.4.4 / SDK 0.4.5 / 客户端 0.4.39 发布候选已完成版本、依赖、三包 build、hash、dry-run 与发布前 gate；下一动作是正式 PyPI 上传、在线验证和远端推送。
- `CR-022`：Hosted UI 公共字段 change、安全 Form Handle、通用 `ui.form.reset`、create/update 初始化、隐藏式滚动与 1–3 列 Form 布局已实现并验证。
- `TASK-039`：客户端 `0.4.30` 版本事实已完成验证，ledger 的下一动作为 `none`；桌面安装包、Git tag / GitHub release 和 Windows 真机证据不在本轮范围。
- `TASK-036` / `CR-018`：Hosted UI DataTable 批量字段修改的 Contracts / SDK / Core 通用实现已 review、确认并发布；具体业务模块接线与 E2E 仍是后续工作。
- `CR-019` / `TASK-038`：行按钮 `open_page` 已完成 review、人工确认、提交和远端推送；远端 HEAD 为 `a0f96cc8`。
- `TASK-037`：Contracts `0.4.3` -> SDK `0.4.4` 已按依赖顺序发布到 PyPI，哈希和隔离安装验证通过。

## 当前边界与硬约束

- 当前分支只支持 Core `0.4.0` / `core-native-v2`；不要恢复 0.3.x 或旧 v1 运行时兼容面。
- 模块运行时代码依赖 `crawler4j-contracts`；SDK 负责 CLI、脚手架、扫描、校验和 manifest lock。
- Hosted UI 使用 `@page` / `@ui_action`；浏览器页面操作使用 `@page_action`；数据资源使用 `@data_table` / `@data_view`。
- 正式事实优先级：docs 与 work item ledger/evidence 高于 memory summary；不要把计划写成完成。
- 代码任务必须保留验证、独立 review、人工确认和 memory sync 证据。

## 最新验证与发布事实

- 2026-07-15：版本/打包聚焦 `175 passed`；全量 unit `1235 passed`，另有 13 项既有沙箱/只读数据库环境基线；root sdist 临时 desktop bundle 污染已完成 TDD 修复和内容 gate。
- 2026-07-15：全仓 Ruff、lock、JSON、docs、UI smoke、三包 build、METADATA/哈希、两包 publish dry-run 和 diff check 通过。
- 2026-07-10：unit `1135 passed`；聚焦版本/打包回归 `65 passed`。
- 2026-07-10：Ruff、`uv lock --check`、项目 JSON、docs 校验、UI smoke、root build、wheel METADATA 和 `git diff --check` 通过。
- Contracts `0.4.4` / SDK `0.4.5` 尚待正式 PyPI 上传；客户端源码版本已到 `0.4.39`，不等于桌面安装包已发布。

## 开放风险

- `ctrip` 真实站点 DevLink / ZIP E2E 仍未闭环。
- Windows 签名、安装、自更新真机证据仍缺。
- 0.4.39 客户端桌面包、Git tag / GitHub release 资产和正式交付批次仍需单独收口。

## 最小读取顺序

1. `.factory/memory/memory-index.md`
2. `.factory/memory/agent-session.md`
3. 本文件
4. 仅按任务读取 `current-state.md`、`tasks.summary.md`、`tests.summary.md` 或专题摘要
5. 需要具体事实时读取对应 work item ledger、evidence、review 或 docs 单文件

默认排除：历史 state、逐条变更日志、全量测试历史、整个 `docs/` 和整个 `.factory/workitems/`。
